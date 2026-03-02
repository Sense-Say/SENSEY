import cv2
import depthai as dai
import numpy as np
import sys, os, time, math, json, threading, subprocess
import sounddevice as sd
import vosk
from hailo_platform import HEF, VDevice, HailoStreamInterface, InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams, FormatType
from gpiozero import Button

# --- ENV ---
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"
os.environ["HAILO_SCHEDULER"] = "1"
DOC_PATH = "/home/raspberrypi/Documents/"
REPO_ROOT = "/home/raspberrypi/hailo-apps"
sys.path.append(REPO_ROOT)
from hailo_apps.python.standalone_apps.object_detection.object_detection_post_process import inference_result_handler

# --- CONFIG ---
HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m.hef"
VOSK_MODEL_PATH = "/home/raspberrypi/Downloads/vosk-model-en-us-0.22-lgraph"
PIPER_EXE = "/home/raspberrypi/Documents/piper/piper"
PIPER_MODEL = "/home/raspberrypi/Documents/piper/en_US-lessac-medium.onnx"
LABELS = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"]
CONFIG_DATA = {"visualization_params": {"score_thres": 0.5, "max_boxes_to_draw": 50}}
ALLOWED_WORDS = ["record", "finish", "go", "to", "point", "saved", "front", "back", "door", "desk", "window", "stop", "navigate", "start", "yes", "no", "correct", "wrong", "update", "pause", "resume", "[unk]"]
MIN_Z_DELTA, MAX_Z_DELTA = 0.01, 0.30

# --- STATE ---
STATE = "IDLE" 
total_dist, current_yaw, last_wp_dist, current_x, current_z = 0.0, 0.0, 0.0, 0.0, 0.0
recorded_path, nav_path = [], []
current_route_filename, landmark_count, pending_command, previous_state = "", 0, "", "IDLE"
is_listening, is_speaking = False, False

class NavigationManager:
    def __init__(self):
        self.path, self.current_wp_index, self.active = [], 0, False
    def load_path(self, path_data):
        self.path, self.current_wp_index, self.active = path_data, 0, True
    def get_instruction(self, cur_x, cur_z, cur_yaw, is_on_demand=False):
        if not self.active or self.current_wp_index >= len(self.path): return None
        target = self.path[self.current_wp_index]
        dist = math.sqrt((target[0] - cur_x)**2 + (target[1] - cur_z)**2)
        if dist < 0.6:
            self.current_wp_index += 1
            if self.current_wp_index >= len(self.path):
                self.active = False
                return "Arrived at destination."
            next_t = self.path[self.current_wp_index]
            if "landmark" in str(next_t[2]) or "start" in str(next_t[2]):
                return f"Reached checkpoint. " + self.calculate_turn(cur_x, cur_z, cur_yaw, next_t[0], next_t[1])
            return None 
        if is_on_demand: return self.calculate_turn(cur_x, cur_z, cur_yaw, target[0], target[1])
        return None
    def calculate_turn(self, cx, cz, cyaw, tx, tz):
        dist = math.sqrt((tx - cx)**2 + (tz - cz)**2)
        turn = (math.degrees(math.atan2(tx - cx, tz - cz)) - cyaw) % 360
        if turn > 180: turn -= 360
        if turn > 20: s = f"Turn right {int(turn)} degrees and "
        elif turn < -20: s = f"Turn left {int(abs(turn))} degrees and "
        else: s = "Go straight and "
        return f"{s} walk {dist:.1f} meters."

nav_engine = NavigationManager()

def speak_offline(text):
    """Mouth: Uses Piper to speak, mutes the ear while talking."""
    global is_speaking
    if not text.strip(): return
    is_speaking = True
    print(f"🔊 Speaking: {text}")
    # Run Piper as a system command for stability
    cmd = f'echo "{text}" | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | aplay -r 22050 -f S16_LE -t raw > /dev/null 2>&1'
    subprocess.run(cmd, shell=True)
    time.sleep(0.1)
    is_speaking = False

def execute_action(cmd_to_run):
    """Handles logic after confirmation."""
    global STATE, recorded_path, nav_path, total_dist, current_yaw, last_wp_dist, current_route_filename, landmark_count, current_x, current_z, nav_engine
    
    if "record" in cmd_to_run:
        STATE = "RECORDING"
        # Extract the name from the command
        raw_name = cmd_to_run.replace("record", "").strip()
        if not raw_name: raw_name = f"path_{int(time.time())}"
        current_route_filename = raw_name.replace(" ", "_")
        
        # Reset variables for a fresh recording
        recorded_path = [[0.0, 0.0, "start"]]
        total_dist, current_yaw, current_x, current_z, last_wp_dist = 0.0, 0.0, 0.0, 0.0, 0.0
        landmark_count = 0
        speak_offline(f"Starting record {raw_name}. Anchor set.")

    elif "finish" in cmd_to_run or "stop" in cmd_to_run:
        if STATE == "RECORDING":
            # Save the JSON file based on the recorded name
            file_path = os.path.join(DOC_PATH, f"{current_route_filename}.json")
            with open(file_path, "w") as f:
                json.dump(recorded_path, f)
            speak_offline(f"Recording saved as {current_route_filename.replace('_', ' ')}.")
        elif STATE == "NAVIGATING":
            nav_engine.active = False
            speak_offline("Navigation stopped.")
        
        STATE = "IDLE"

    elif "go to" in cmd_to_run or "navigate" in cmd_to_run:
        target = cmd_to_run.replace("go to", "").replace("navigate", "").strip().replace(" ", "_")
        found = False
        for f in os.listdir(DOC_PATH):
            if f.endswith(".json") and target in f.replace(".json", ""):
                with open(os.path.join(DOC_PATH, f), "r") as jf: nav_path = json.load(jf)
                if "to" in target and target.split("_to_")[0] in f.split("_to_")[-1]:
                    nav_path.reverse(); speak_offline("Reversing route.")
                
                STATE = "NAVIGATING"
                total_dist, current_yaw, current_x, current_z = 0.0, 0.0, 0.0, 0.0
                nav_engine.load_path(nav_path)
                
                # Get the first instruction from the engine
                upd = nav_engine.get_instruction(0, 0, 0, is_on_demand=True)
                speak_offline(f"Navigating to {target.replace('_', ' ')}. {upd}")
                found = True; break
        if not found:
            STATE = "IDLE"
            speak_offline("Route not found.")

def handle_voice_command(cmd):
    """The State Machine for precise conversational logic."""
    global STATE, pending_command, is_listening, recorded_path, landmark_count, total_dist, current_yaw, current_x, current_z, previous_state
    
    cmd = cmd.lower().strip()
    if not cmd: return

    print(f"✅ Voice Input: '{cmd}' (Current State: {STATE})")

    # --- STATE: CONFIRMING START ---
    if STATE == "CONFIRM_START":
        if "yes" in cmd or "correct" in cmd:
            cmd_to_run = pending_command
            STATE = "IDLE" # Reset so execute_action can set the new state
            execute_action(cmd_to_run)
        else:
            STATE = "IDLE"
            speak_offline("Cancelled.")
        pending_command = ""

    # --- STATE: CONFIRMING FINISH ---
    elif STATE == "CONFIRM_FINISH":
        if "yes" in cmd or "correct" in cmd:
            cmd_to_run = pending_command
            STATE = "IDLE"
            execute_action(cmd_to_run)
        else:
            STATE = previous_state # Revert to Recording or Navigating
            if STATE == "RECORDING":
                speak_offline("Continuing recording.")
            else:
                speak_offline("Resuming navigation.")
        pending_command = ""

    # --- STATE: RECORDING ---
    elif STATE == "RECORDING":
        if "point" in cmd and "saved" in cmd:
            landmark_count += 1
            recorded_path.append([current_x, current_z, f"point_{landmark_count}"])
            speak_offline(f"Point {landmark_count} saved.")
        elif "finish" in cmd or "stop" in cmd:
            pending_command = cmd
            previous_state = "RECORDING"
            STATE = "CONFIRM_FINISH"
            speak_offline(f"You said stop recording. Is this correct?")
            is_listening = True # Automatically trigger mic for Yes/No

    # --- STATE: NAVIGATING ---
    elif STATE == "NAVIGATING":
        if "update" in cmd:
            upd = nav_engine.get_instruction(current_x, current_z, current_yaw, is_on_demand=True)
            if upd: speak_offline(upd)
        elif "finish" in cmd or "stop" in cmd:
            pending_command = cmd
            previous_state = "NAVIGATING"
            STATE = "CONFIRM_FINISH"
            speak_offline(f"You said stop navigating. Is this correct?")
            is_listening = True 

    # --- STATE: IDLE ---
    else:
        if "record" in cmd or "go to" in cmd or "navigate" in cmd:
            pending_command = cmd
            STATE = "CONFIRM_START"
            speak_offline(f"You said {cmd}. Is this correct?")
            is_listening = True 

def trigger_listening():
    """Entry point for the GPIO button."""
    global is_listening
    if not is_speaking and not is_listening:
        is_listening = True
        print("👂 Listening...")
        speak_offline("Listening")

# --- 5. OAK-D PIPELINE ---

def get_pipeline():
    p = dai.Pipeline()
    cam = p.create(dai.node.ColorCamera)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam.setInterleaved(False)
    # 🚀 FIX: Force Native BGR Output (This stops the "Blue Skin" permanently)
    cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    cam.setPreviewSize(640, 640)
    cam.setPreviewKeepAspectRatio(False) 
    cam.initialControl.setManualFocus(10)

    left = p.create(dai.node.MonoCamera); left.setBoardSocket(dai.CameraBoardSocket.CAM_B); left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    right = p.create(dai.node.MonoCamera); right.setBoardSocket(dai.CameraBoardSocket.CAM_C); right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    stereo = p.create(dai.node.StereoDepth); stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT); stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A); stereo.setOutputSize(1920, 1080)
    left.out.link(stereo.left); right.out.link(stereo.right)
    imu = p.create(dai.node.IMU); imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 100); imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 100); imu.setBatchReportThreshold(1); imu.setMaxBatchReports(20)
    feat = p.create(dai.node.FeatureTracker); left.out.link(feat.inputImage)
    x_isp = p.create(dai.node.XLinkOut); x_isp.setStreamName("isp"); cam.isp.link(x_isp.input)
    x_pre = p.create(dai.node.XLinkOut); x_pre.setStreamName("pre"); cam.preview.link(x_pre.input)
    x_dep = p.create(dai.node.XLinkOut); x_dep.setStreamName("depth"); stereo.depth.link(x_dep.input)
    x_imu = p.create(dai.node.XLinkOut); x_imu.setStreamName("imu"); imu.out.link(x_imu.input)
    x_fea = p.create(dai.node.XLinkOut); x_fea.setStreamName("feat"); feat.outputFeatures.link(x_fea.input)
    return p

# --- 6. MAIN RUNNER ---
# --- 6. MAIN RUNNER ---
def run():
    global total_dist, current_yaw, last_wp_dist, recorded_path, nav_path, is_listening, is_speaking, STATE, current_x, current_z
    
    # 🚀 6 DOF STATE VARIABLES
    curr_yaw, curr_pitch, curr_roll = 0.0, 0.0, 0.0
    last_imu_t = None
    
    print("⏳ Loading Vosk...")
    vosk_model = vosk.Model(VOSK_MODEL_PATH)
    rec = vosk.KaldiRecognizer(vosk_model, 16000, json.dumps(ALLOWED_WORDS))
    
    print("⏳ Loading Hailo NPU...")
    target = VDevice(); hef = HEF(HEF_PATH)
    conf = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
    group = target.configure(hef, conf)[0]
    in_p = InputVStreamParams.make(group, format_type=FormatType.UINT8)
    out_p = OutputVStreamParams.make(group, format_type=FormatType.FLOAT32)
    input_name = hef.get_input_vstream_infos()[0].name
    
    try: btn = Button(26, pull_up=True); btn.when_pressed = trigger_listening
    except: btn = None
    
    devices = sd.query_devices()
    mic_idx, native_rate, mic_channels = 0, 44100, 1
    for i, dev in enumerate(devices):
        if "USB" in dev['name'] and dev['max_input_channels'] > 0:
            mic_idx, native_rate, mic_channels = i, int(dev['default_samplerate']), dev['max_input_channels']; break
            
    def audio_callback(indata, frames, time_info, status):
        global is_listening, is_speaking
        if not is_listening or is_speaking: return
        mono_data = np.mean(indata, axis=1) if indata.shape[1] > 1 else indata.flatten()
        audio = (mono_data * 32768).astype('int16')
        num_s = int(len(audio) * 16000 / native_rate)
        resampled = audio[np.linspace(0, len(audio) - 1, num_s).astype(int)]
        if rec.AcceptWaveform(resampled.tobytes()):
            result = json.loads(rec.Result()); cmd = result.get('text', '')
            if cmd: is_listening = False; handle_voice_command(cmd); rec.Reset()

    feat_history, button_was_pressed = {}, False

    with dai.Device(get_pipeline()) as device:
        # Mic stream setup
        try:
            mic_stream = sd.InputStream(samplerate=native_rate, device=mic_idx, channels=1, dtype='float32', blocksize=4000, callback=audio_callback)
            mic_stream.start()
        except sd.PortAudioError:
            mic_stream = sd.InputStream(samplerate=native_rate, device=mic_idx, channels=2, dtype='float32', blocksize=4000, callback=audio_callback)
            mic_stream.start()

        q_isp = device.getOutputQueue("isp", 4, False); q_pre = device.getOutputQueue("pre", 4, False)
        q_dep = device.getOutputQueue("depth", 4, False); q_imu = device.getOutputQueue("imu", 20, False)
        q_fea = device.getOutputQueue("feat", 4, False)
        
        with group.activate():
            with InferVStreams(group, in_p, out_p) as pipe:
                print("✅ SENSEY 6-DOF Ready."); speak_offline("System Ready.")
                
                while True:
                    if btn and btn.is_pressed:
                        if not button_was_pressed:
                            button_was_pressed = True
                            trigger_listening()
                    else:
                        button_was_pressed = False

                    # 🚀 1. HIGH-PRECISION 6 DOF IMU FUSION
                    # 🚀 1. RECALIBRATED 6 DOF IMU FUSION
                    imuData = q_imu.tryGetAll() 
                    for data in imuData:
                        for packet in data.packets:
                            raw_gyro = packet.gyroscope
                            raw_accel = packet.acceleroMeter
                            ts = packet.acceleroMeter.timestamp.get().total_seconds()
                            
                            if last_imu_t is None:
                                last_imu_t = ts
                                continue
                            dt = ts - last_imu_t
                            last_imu_t = ts

                            # --- AXIS REALIGNMENT ---
                            # Re-mapping to ensure Pitch is 0 and Roll is 0 when straight
                            ax, ay, az = raw_accel.x, raw_accel.z, raw_accel.y
                            gx, gy, gz = raw_gyro.x, raw_gyro.z, raw_gyro.y

                            # --- A. Accelerometer (Gravity Reference) ---
                            # We adjusted the atan2 parameters to force Roll to 0
                            accel_pitch = math.degrees(math.atan2(ay, math.sqrt(ax**2 + az**2)))
                            accel_roll = math.degrees(math.atan2(ax, az)) 

                            # --- B. Gyroscope (Yaw integration) ---
                            # 🚀 YAW SIGN REVERSED: Left is now (+), Right is now (-)
                            # We use '-=' instead of '+=' to flip the direction
                            current_yaw -= (gz * (180.0 / math.pi) * dt)

                            # --- C. Complementary Filter ---
                            curr_pitch = 0.98 * (curr_pitch + gx * (180.0/math.pi) * dt) + 0.02 * accel_pitch
                            curr_roll = 0.98 * (curr_roll + gy * (180.0/math.pi) * dt) + 0.02 * accel_roll
                            
                            # --- D. Final Wrapping & Normalization ---
                            # This keeps all angles between -180 and 180 degrees
                            # ensuring 0 is always the center point
                            if curr_pitch > 180: curr_pitch -= 360
                            elif curr_pitch < -180: curr_pitch += 360
                            
                            if curr_roll > 180: curr_roll -= 360
                            elif curr_roll < -180: curr_roll += 360
                            
                            if current_yaw > 180: current_yaw -= 360
                            elif current_yaw < -180: current_yaw += 360

                    # 🚀 2. FETCH SENSOR FRAMES (This fixes the NameError!)
                    rgb_isp = q_isp.get().getCvFrame() 
                    rgb_pre = q_pre.get().getCvFrame() 
                    depth = q_dep.get().getFrame() 
                    fea_data = q_fea.get().trackedFeatures
                    
                    # 🚀 3. PEDOMETER
                    deltas = []
                    for f in fea_data:
                        x, y = int(f.position.x), int(f.position.y)
                        dx, dy = int(x * 1920/640), int(y * 1080/400)
                        if 0 <= dy < 1080 and 0 <= dx < 1920:
                            z = depth[dy, dx] / 1000.0
                            if z > 0 and f.id in feat_history:
                                d_z = feat_history[f.id] - z
                                if MIN_Z_DELTA < abs(d_z) < MAX_Z_DELTA: deltas.append(d_z)
                            feat_history[f.id] = z
                    
                    if deltas: 
                        total_dist += sum(deltas)/len(deltas)
                        rad_yaw = math.radians(current_yaw)
                        current_x = total_dist * math.sin(rad_yaw)
                        current_z = total_dist * math.cos(rad_yaw)

                    if STATE == "RECORDING" and (total_dist - last_wp_dist) > 0.5:
                        recorded_path.append([current_x, current_z, "path"])
                        last_wp_dist = total_dist
                    
                    if STATE == "NAVIGATING":
                        inst = nav_engine.get_instruction(current_x, current_z, current_yaw)
                        if inst: threading.Thread(target=speak_offline, args=(inst,), daemon=True).start()
                    
                    # 🚀 4. AI INFERENCE & UI RENDER
                    # No color conversion needed here because get_pipeline forces BGR order
                    res = pipe.infer({input_name: np.expand_dims(rgb_pre, axis=0)})
                    raw_dets = list(res.values())[0]

                    processed = inference_result_handler(
                        rgb_isp, 
                        raw_dets, 
                        LABELS, 
                        CONFIG_DATA, 
                        vio_data=(total_dist, current_yaw, curr_pitch, curr_roll), 
                        waypoints=recorded_path if STATE in ["RECORDING", "CONFIRM_FINISH", "CONFIRM_START"] else None, 
                        nav_waypoints=nav_path if STATE in ["NAVIGATING", "CONFIRM_FINISH", "CONFIRM_START"] else None, 
                        depth_frame=depth, 
                        state_text=STATE
                    )
                    
                    cv2.imshow("SENSEY 6-DOF AR Navigator", cv2.resize(processed, (1280, 720)))
                    if cv2.waitKey(1) == ord('q'): 
                        mic_stream.stop()
                        break
                        
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run()