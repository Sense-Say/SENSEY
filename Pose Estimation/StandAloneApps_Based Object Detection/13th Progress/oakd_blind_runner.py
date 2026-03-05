import cv2
import depthai as dai
import numpy as np
import sys, os, time, math, json, threading, subprocess
import sounddevice as sd
import vosk
import pygame
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
TICK_SOUND = "/home/raspberrypi/Downloads/watch_tick.wav"
LABELS = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"]
CONFIG_DATA = {"visualization_params": {"score_thres": 0.5, "max_boxes_to_draw": 50}}
ALLOWED_WORDS = ["record", "finish", "go", "to", "point", "saved", "front", "back", "door", "desk", "window", "stop", "navigate", "start", "yes", "no", "correct", "wrong", "update", "pause", "resume", "[unk]"]
MIN_Z_DELTA, MAX_Z_DELTA = 0.01, 0.30

# --- AUDIO INIT ---
pygame.mixer.init()
tick_sound_effect = pygame.mixer.Sound(TICK_SOUND)
is_ticking = False

# --- STATE ---
STATE = "IDLE" 
total_dist, current_yaw, last_wp_dist, current_x, current_z = 0.0, 0.0, 0.0, 0.0, 0.0
recorded_path, nav_path = [], []
current_route_filename, landmark_count, pending_command, previous_state = "", 0, "", "IDLE"
is_listening, is_speaking = False, False

class NavigationManager:
    def __init__(self):
        self.path, self.current_wp_index, self.active = [], 0, False
        self.target_yaw = None
        self.distance_to_wp = 0.0

    def load_path(self, path_data):
        self.path = path_data
        self.active = True
        self.current_wp_index = 0
        self.find_next_landmark()

    def find_next_landmark(self):
        for i in range(self.current_wp_index, len(self.path)):
            label = str(self.path[i][2])
            if "point" in label or i == len(self.path) - 1:
                self.current_wp_index = i
                target = self.path[i]
                self.target_yaw = target[3] if len(target) > 3 else None
                return
        self.active = False

    def get_instruction(self, cur_x, cur_z, cur_yaw):
        if not self.active or self.current_wp_index >= len(self.path): 
            self.target_yaw = None
            return None
        target = self.path[self.current_wp_index]
        self.distance_to_wp = math.sqrt((target[0] - cur_x)**2 + (target[1] - cur_z)**2)
        if self.target_yaw is None:
            self.target_yaw = math.degrees(math.atan2(target[0] - cur_x, target[1] - cur_z)) % 360
        if self.distance_to_wp < 0.6:
            label = str(target[2])
            self.current_wp_index += 1
            if self.current_wp_index >= len(self.path):
                self.active = False
                return "Arrived at destination."
            self.find_next_landmark()
            return f"Reached {label}. Next point {int(self.target_yaw)} degrees."
        return None

nav_engine = NavigationManager()

def play_navigation_tick(current_yaw, target_yaw, screen_width=1024):
    global is_ticking
    if target_yaw is None or STATE != "NAVIGATING":
        if is_ticking: tick_sound_effect.stop(); is_ticking = False
        return
    pixels_per_degree = screen_width / 90
    relative_angle = (target_yaw - current_yaw + 180) % 360 - 180
    arrow_x = (screen_width // 2) + int(relative_angle * pixels_per_degree)
    l_lim, r_lim = screen_width // 3, 2 * screen_width // 3
    if l_lim <= arrow_x <= r_lim:
        if not is_ticking: tick_sound_effect.play(loops=-1); is_ticking = True
    else:
        if is_ticking: tick_sound_effect.stop(); is_ticking = False

def speak_offline(text):
    global is_speaking
    if not text.strip(): return
    def _speak_thread():
        global is_speaking
        is_speaking = True
        print(f"🔊 Speaking: {text}")
        cmd = f'echo "{text}" | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | aplay -r 22050 -f S16_LE -t raw > /dev/null 2>&1'
        subprocess.run(cmd, shell=True)
        is_speaking = False
    threading.Thread(target=_speak_thread, daemon=True).start()

def execute_action(cmd):
    global STATE, recorded_path, nav_path, total_dist, current_yaw, last_wp_dist, current_route_filename, landmark_count, current_x, current_z, nav_engine
    print(f"DEBUG: execute_action received '{cmd}'. State: {STATE}")
    if "record" in cmd:
        raw_name = cmd.replace("record", "").strip()
        current_route_filename = raw_name.replace(" ", "_") if raw_name else f"path_{int(time.time())}"
        recorded_path = [[0.0, 0.0, "start", current_yaw]]
        total_dist, current_yaw, current_x, current_z, last_wp_dist = 0.0, 0.0, 0.0, 0.0, 0.0
        landmark_count = 0
        STATE = "RECORDING"
        speak_offline(f"Recording {current_route_filename.replace('_', ' ')}. Anchor set.")
    elif "finish" in cmd or "stop" in cmd:
        if len(recorded_path) > 0:
            file_path = os.path.join(DOC_PATH, f"{current_route_filename}.json")
            with open(file_path, "w") as f: json.dump(recorded_path, f)
            speak_offline(f"Path saved. Total {landmark_count} points.")
        elif STATE == "NAVIGATING":
            speak_offline("Navigation stopped.")
            nav_engine.active = False
        STATE = "IDLE"
    elif "go to" in cmd or "navigate" in cmd:
        target = cmd.replace("go to", "").replace("navigate", "").strip().replace(" ", "_")
        found = False
        for f in os.listdir(DOC_PATH):
            if f.endswith(".json") and (target == f.replace(".json", "") or target in f):
                with open(os.path.join(DOC_PATH, f), "r") as jf: nav_path = json.load(jf)
                if "to" in target and target.split("_to_")[0] in f.split("_to_")[-1]:
                    nav_path.reverse(); speak_offline("Reversing route.")
                STATE = "NAVIGATING"
                total_dist, current_yaw, current_x, current_z = 0.0, 0.0, 0.0, 0.0
                nav_engine.load_path(nav_path)
                speak_offline(f"Navigating to {target.replace('_', ' ')}.")
                found = True; break
        if not found: STATE = "IDLE"; speak_offline("Route not found.")

def handle_voice_command(cmd):
    global STATE, pending_command, is_listening, recorded_path, landmark_count, current_x, current_z, previous_state
    cmd = cmd.lower().strip()
    if not cmd: return
    print(f"✅ Processing Input: {cmd} (State: {STATE})")
    if STATE == "CONFIRM_START":
        if "yes" in cmd or "correct" in cmd: execute_action(pending_command)
        else: STATE = "IDLE"; speak_offline("Cancelled.")
        pending_command = ""
    elif STATE == "CONFIRM_FINISH":
        if "yes" in cmd or "correct" in cmd: execute_action(pending_command)
        else: STATE = previous_state; speak_offline("Resuming.")
        pending_command = ""
    elif STATE == "RECORDING":
        if "point" in cmd and "saved" in cmd:
            landmark_count += 1
            recorded_path.append([current_x, current_z, f"point_{landmark_count}", current_yaw])
            speak_offline(f"Point {landmark_count} saved.")
        elif "finish" in cmd or "stop" in cmd:
            pending_command = "finish"; previous_state = "RECORDING"; STATE = "CONFIRM_FINISH"
            speak_offline("Stop recording. Is this correct?"); is_listening = True 
    elif STATE == "NAVIGATING":
        if "finish" in cmd or "stop" in cmd:
            pending_command = "stop"; previous_state = "NAVIGATING"; STATE = "CONFIRM_FINISH"
            speak_offline("Stop navigation. Is this correct?"); is_listening = True 
    else:
        if any(x in cmd for x in ["record", "go to", "navigate"]):
            pending_command = cmd; STATE = "CONFIRM_START"
            speak_offline(f"You said {cmd}. Is this correct?"); is_listening = True

def trigger_listening():
    global is_listening
    if not is_speaking and not is_listening:
        is_listening = True
        print("👂 Listening...")
        speak_offline("Listening")

def get_pipeline():
    p = dai.Pipeline()
    cam = p.create(dai.node.ColorCamera)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_12_MP)
    cam.setIspScale(1, 3) 
    cam.setInterleaved(False)
    cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    cam.setPreviewSize(640, 640)
    cam.setPreviewKeepAspectRatio(False) 
    cam.initialControl.setManualFocus(0) 
    left = p.create(dai.node.MonoCamera); left.setBoardSocket(dai.CameraBoardSocket.CAM_B); left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
    right = p.create(dai.node.MonoCamera); right.setBoardSocket(dai.CameraBoardSocket.CAM_C); right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
    stereo = p.create(dai.node.StereoDepth); stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT); stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A); stereo.setOutputSize(1344, 1008) 
    left.out.link(stereo.left); right.out.link(stereo.right)
    imu = p.create(dai.node.IMU); imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 100); imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 100); imu.setBatchReportThreshold(1); imu.setMaxBatchReports(20)
    feat = p.create(dai.node.FeatureTracker); feat.setHardwareResources(2, 2); feat.initialConfig.setNumTargetFeatures(320); left.out.link(feat.inputImage)
    x_isp = p.create(dai.node.XLinkOut); x_isp.setStreamName("isp"); cam.isp.link(x_isp.input)
    x_pre = p.create(dai.node.XLinkOut); x_pre.setStreamName("pre"); cam.preview.link(x_pre.input)
    x_dep = p.create(dai.node.XLinkOut); x_dep.setStreamName("depth"); stereo.depth.link(x_dep.input)
    x_imu = p.create(dai.node.XLinkOut); x_imu.setStreamName("imu"); imu.out.link(x_imu.input)
    x_fea = p.create(dai.node.XLinkOut); x_fea.setStreamName("feat"); feat.outputFeatures.link(x_fea.input)
    return p

def run():
    global total_dist, current_yaw, last_wp_dist, recorded_path, nav_path, is_listening, is_speaking, STATE, current_x, current_z
    
    # 🚀 INITIALIZE 6 DOF & GYRO VARIABLES (Fixes UnboundLocalError)
    curr_yaw, curr_pitch, curr_roll = 0.0, 0.0, 0.0
    gx, gy, gz = 0.0, 0.0, 0.0 
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
    mic_idx, native_rate = 0, 44100
    for i, dev in enumerate(devices):
        if "USB" in dev['name']: mic_idx, native_rate = i, int(dev['default_samplerate']); break
            
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
        try:
            mic_stream = sd.InputStream(samplerate=native_rate, device=mic_idx, channels=1, dtype='float32', blocksize=4000, callback=audio_callback)
            mic_stream.start()
        except: pass

        q_isp = device.getOutputQueue("isp", 4, False); q_pre = device.getOutputQueue("pre", 4, False)
        q_dep = device.getOutputQueue("depth", 4, False); q_imu = device.getOutputQueue("imu", 20, False)
        q_fea = device.getOutputQueue("feat", 4, False)
        
        with group.activate():
            with InferVStreams(group, in_p, out_p) as pipe:
                print("✅ SENSEY Ready."); speak_offline("System Ready.")
                
                while True:
                    if btn and btn.is_pressed:
                        if not button_was_pressed: button_was_pressed = True; trigger_listening()
                    else: button_was_pressed = False

                    # 🚀 1. RECALIBRATED 6 DOF IMU FUSION
                    imuData = q_imu.tryGetAll() 
                    for data in imuData:
                        for packet in data.packets:
                            ts = packet.acceleroMeter.timestamp.get().total_seconds()
                            if last_imu_t is None: last_imu_t = ts; continue
                            dt = ts - last_imu_t; last_imu_t = ts

                            ax, ay, az = packet.acceleroMeter.x, packet.acceleroMeter.z, packet.acceleroMeter.y
                            gx, gy, gz = packet.gyroscope.x, packet.gyroscope.z, packet.gyroscope.y

                            accel_pitch = math.degrees(math.atan2(ay, math.sqrt(ax**2 + az**2)))
                            accel_roll = math.degrees(math.atan2(ax, az)) 

                            current_yaw -= (gz * (180.0 / math.pi) * dt)
                            curr_pitch = 0.98 * (curr_pitch + gx * (180.0/math.pi) * dt) + 0.02 * accel_pitch
                            curr_roll = 0.98 * (curr_roll + gy * (180.0/math.pi) * dt) + 0.02 * accel_roll
                            
                            if curr_pitch > 180: curr_pitch -= 360
                            elif curr_pitch < -180: curr_pitch += 360
                            if curr_roll > 180: curr_roll -= 360
                            elif curr_roll < -180: curr_roll += 360
                            if current_yaw > 180: current_yaw -= 360
                            elif current_yaw < -180: current_yaw += 360

                    # 🚀 2. FETCH SENSOR FRAMES
                    rgb_isp = q_isp.get().getCvFrame(); rgb_pre = q_pre.get().getCvFrame() 
                    depth = q_dep.get().getFrame(); fea_data = q_fea.get().trackedFeatures
                    
                    # 🚀 3. MOTION-FILTERED PEDOMETER
                    deltas = []
                    # Filter: If rotating faster than 0.1 rad/s, ignore pedometer
                    is_rotating = abs(gz) > 0.1 or abs(gx) > 0.1 or abs(gy) > 0.1
                    
                    if not is_rotating:
                        for f in fea_data:
                            x, y = int(f.position.x), int(f.position.y)
                            dx, dy = int(x * 1344/640), int(y * 1008/480)
                            if 0 <= dy < 1008 and 0 <= dx < 1344:
                                z = depth[dy, dx] / 1000.0
                                if z > 0 and f.id in feat_history:
                                    d_z = feat_history[f.id] - z
                                    if MIN_Z_DELTA < abs(d_z) < MAX_Z_DELTA:
                                        deltas.append(d_z)
                                feat_history[f.id] = z
                    
                    if deltas and not is_rotating: 
                        avg_step = np.median(deltas) 
                        if abs(avg_step) > 0.005:
                            total_dist += avg_step
                            rad_yaw = math.radians(current_yaw)
                            current_x = total_dist * math.sin(rad_yaw)
                            current_z = total_dist * math.cos(rad_yaw)

                    if STATE == "RECORDING" and (total_dist - last_wp_dist) > 0.5:
                        recorded_path.append([current_x, current_z, "path", current_yaw])
                        last_wp_dist = total_dist
                    
                    if STATE == "NAVIGATING":
                        inst = nav_engine.get_instruction(current_x, current_z, current_yaw)
                        if inst: threading.Thread(target=speak_offline, args=(inst,), daemon=True).start()
                        play_navigation_tick(current_yaw, nav_engine.target_yaw, screen_width=1024)

                    res = pipe.infer({input_name: np.expand_dims(rgb_pre, axis=0)})
                    raw_dets = list(res.values())[0]
                    processed = inference_result_handler(
                        rgb_isp, raw_dets, LABELS, CONFIG_DATA, 
                        vio_data=(total_dist, current_yaw, curr_pitch, curr_roll), 
                        target_yaw=nav_engine.target_yaw if STATE == "NAVIGATING" else None, 
                        target_dist=nav_engine.distance_to_wp if STATE == "NAVIGATING" else None,
                        depth_frame=depth, state_text=STATE
                    )
                    cv2.imshow("SENSEY 6-DOF AR Navigator", cv2.resize(processed, (1024, 768)))
                    if cv2.waitKey(1) == ord('q'): break
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run()