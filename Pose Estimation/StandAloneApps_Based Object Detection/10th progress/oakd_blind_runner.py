import cv2
import depthai as dai
import numpy as np
import sys, os, time, math, json, threading, subprocess
import sounddevice as sd
import vosk
from gpiozero import Button
from hailo_platform import HEF, VDevice, HailoStreamInterface, InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams, FormatType

# --- 1. SYSTEM ENVIRONMENT ---
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"
os.environ["HAILO_SCHEDULER"] = "1"
DOC_PATH = "/home/raspberrypi/Documents/"
REPO_ROOT = "/home/raspberrypi/hailo-apps"

VOSK_MODEL_PATH = "/home/raspberrypi/Downloads/vosk-model-en-us-0.22-lgraph"
PIPER_EXE = "/home/raspberrypi/Documents/piper/piper"
PIPER_MODEL = "/home/raspberrypi/Documents/piper/en_US-lessac-medium.onnx"
HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m.hef"

sys.path.append(REPO_ROOT)
from hailo_apps.python.standalone_apps.object_detection.object_detection_post_process import inference_result_handler

# --- 2. CONFIGURATION ---
LABELS = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"]
CONFIG_DATA = {"visualization_params": {"score_thres": 0.5, "max_boxes_to_draw": 50}}

# Add update, pause, resume
ALLOWED_WORDS = ["record", "finish", "go", "to", "point", "saved", "front", "back", "door", "desk", "window", "stop", "navigate", "start", "yes", "no", "correct", "wrong", "update", "pause", "resume", "[unk]"]

# --- 3. GLOBAL STATE ---
STATE = "IDLE" # IDLE, RECORDING, NAVIGATING, CONFIRM_REC, CONFIRM_NAV, CONFIRM_FINISH
total_dist, current_yaw, last_wp_dist = 0.0, 0.0, 0.0
current_x, current_z = 0.0, 0.0 # True XYZ position
recorded_path, nav_path = [], []
current_route_name = "" 
pending_command = ""

is_listening = False
is_speaking = False
MIN_Z_DELTA, MAX_Z_DELTA = 0.01, 0.30

# --- 4. NAVIGATION MANAGER ---
class NavigationManager:
    def __init__(self):
        self.path = []
        self.current_wp_index = 0
        self.active = False
        
    def load_path(self, path_data):
        self.path = path_data
        self.current_wp_index = 0
        self.active = True
        
    def get_instruction(self, cur_x, cur_z, cur_yaw, is_on_demand=False):
        if not self.active or self.current_wp_index >= len(self.path):
            return None

        # Get Target Waypoint (X, Z, Label)
        target = self.path[self.current_wp_index]
        tx, tz, t_label = target[0], target[1], target[2]
        
        # Calculate Distance to Target
        dx = tx - cur_x
        dz = tz - cur_z
        distance = math.sqrt(dx**2 + dz**2)
        
        # Check if arrived at this waypoint (Threshold: 0.5 meters)
        if distance < 0.5:
            self.current_wp_index += 1
            if self.current_wp_index >= len(self.path):
                self.active = False
                return "Arrived at destination."
            else:
                # We hit a point, immediately give instructions for the NEXT point
                next_target = self.path[self.current_wp_index]
                return f"Reached {t_label}. " + self.calculate_turn(cur_x, cur_z, cur_yaw, next_target[0], next_target[1])
                
        # If the user explicitly asked for an update, calculate it from current position
        if is_on_demand:
            return self.calculate_turn(cur_x, cur_z, cur_yaw, tx, tz)
            
        return None

    def calculate_turn(self, cx, cz, cyaw, tx, tz):
        # Calculate angle to target
        dx = tx - cx
        dz = tz - cz
        distance = math.sqrt(dx**2 + dz**2)
        
        # Target angle from origin
        target_angle_rad = math.atan2(dx, dz)
        target_angle_deg = math.degrees(target_angle_rad)
        
        # Relative turn angle (Target Angle - Current Yaw)
        turn_angle = (target_angle_deg - cyaw) % 360
        if turn_angle > 180: turn_angle -= 360 # Convert to -180 to +180
        
        # Format speech
        turn_str = ""
        if turn_angle > 15:
            turn_str = f"Turn right {int(turn_angle)} degrees and "
        elif turn_angle < -15:
            turn_str = f"Turn left {int(abs(turn_angle))} degrees and "
        else:
            turn_str = "Go straight and "
            
        return f"{turn_str} walk {distance:.1f} meters."

nav_engine = NavigationManager()

# --- 5. AUDIO & VOICE ---

def speak_offline(text):
    global is_speaking
    if not text.strip(): return
    is_speaking = True
    print(f"🔊 Piper: {text}")
    cmd = f'echo "{text}" | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | aplay -r 22050 -f S16_LE -t raw > /dev/null 2>&1'
    subprocess.run(cmd, shell=True)
    time.sleep(0.1)
    is_speaking = False

def execute_action(cmd):
    """Handles logic after confirmation."""
    global STATE, recorded_path, nav_path, total_dist, current_yaw, last_wp_dist, current_route_filename, landmark_count
    global current_x, current_z, nav_engine
    
    # 1. START RECORDING
    if "record" in pending_command:
        STATE = "RECORDING"
        raw_name = pending_command.replace("record", "").strip()
        current_route_filename = raw_name.replace(" ", "_")
        recorded_path = [[0.0, 0.0, "start"]]
        total_dist, current_yaw, current_x, current_z, last_wp_dist = 0.0, 0.0, 0.0, 0.0, 0.0
        landmark_count = 0
        speak_offline(f"Recording {raw_name}. Anchor set.")

    # 2. FINISH EVERYTHING
    elif "finish" in pending_command or "stop" in pending_command:
        if STATE == "RECORDING":
            file_path = os.path.join(DOC_PATH, f"{current_route_filename}.json")
            with open(file_path, "w") as f: json.dump(recorded_path, f)
            speak_offline(f"Path saved. Total {landmark_count} points.")
        elif STATE == "NAVIGATING":
            speak_offline("Navigation stopped.")
            nav_engine.active = False
        STATE = "IDLE"

    # 3. START NAVIGATION
    elif "go to" in pending_command or "navigate" in pending_command:
        target = pending_command.replace("go to", "").replace("navigate", "").strip().replace(" ", "_")
        print(f"🔍 Searching for file containing: '{target}'")
        
        found = False
        for f in os.listdir(DOC_PATH):
            if f.endswith(".json"):
                base_name = f.replace(".json", "")
                
                # Check if target matches exactly or is a reversed phrase
                if target == base_name or (target in base_name):
                    try:
                        with open(os.path.join(DOC_PATH, f), "r") as jf: nav_path = json.load(jf)
                        
                        if "to" in target and target.split("_to_")[0] in base_name.split("_to_")[-1]:
                            nav_path.reverse()
                            speak_offline("Reversing route.")
                        
                        STATE = "NAVIGATING"
                        total_dist, current_yaw, current_x, current_z = 0.0, 0.0, 0.0, 0.0
                        nav_engine.load_path(nav_path)
                        
                        speak_offline(f"Navigating to {target.replace('_', ' ')}.")
                        found = True
                        break
                    except Exception as e:
                        print(f"❌ Error loading path file: {e}")
                        
        if not found:
            STATE = "IDLE"
            speak_offline("Route not found. Returning to standby.")

def handle_voice_command(cmd):
    """The State Machine for precise conversational logic."""
    global STATE, pending_command, is_listening, recorded_path, landmark_count, total_dist, current_yaw
    global current_x, current_z, nav_engine
    cmd = cmd.lower().strip()
    if not cmd: return

    print(f"✅ Processing Input: {cmd} (Current State: {STATE})")

    # --- CONFIRMING START (IDLE -> REC/NAV) ---
    if STATE == "CONFIRM_START":
        if "yes" in cmd or "correct" in cmd:
            print("✅ Confirmed Start.")
            confirmed_cmd = pending_command
            # Set to IDLE temporarily so execute_action handles the state change cleanly
            STATE = "IDLE" 
            execute_action(confirmed_cmd)
        else:
            print("❌ Cancelled Start.")
            STATE = "IDLE"
            pending_command = ""
            speak_offline("Command cancelled.")

    # --- CONFIRMING STOP (REC/NAV -> IDLE) ---
    elif STATE == "CONFIRM_FINISH":
        if "yes" in cmd or "correct" in cmd:
            print("✅ Confirmed Finish.")
            confirmed_cmd = pending_command
            STATE = "IDLE"
            execute_action(confirmed_cmd)
        else:
            print("❌ Cancelled Finish.")
            # We revert back to the previous state
            if "record" in pending_command: # Hacky check to see if we were recording
                STATE = "RECORDING"
                speak_offline("Continuing recording.")
            else:
                STATE = "NAVIGATING"
                # Give dynamic update upon resuming
                upd = nav_engine.get_instruction(current_x, current_z, current_yaw, is_on_demand=True)
                speak_offline(f"Resuming navigation. {upd}")
            pending_command = ""

    # --- RECORDING MODE ---
    elif STATE == "RECORDING":
        if "point" in cmd and "saved" in cmd:
            landmark_count += 1
            rad = math.radians(current_yaw)
            recorded_path.append([current_x, current_z, f"point_{landmark_count}"])
            speak_offline(f"Point {landmark_count} saved.")
        elif "finish" in cmd or "stop" in cmd:
            pending_command = cmd
            STATE = "CONFIRM_FINISH"
            speak_offline(f"You said, stop recording. Is this correct?")
            is_listening = True 

    # --- NAVIGATING MODE ---
    elif STATE == "NAVIGATING":
        if "update" in cmd:
            # Explicitly request the current math update
            upd = nav_engine.get_instruction(current_x, current_z, current_yaw, is_on_demand=True)
            if upd: speak_offline(upd)
            else: speak_offline("No path loaded.")
        elif "finish" in cmd or "stop" in cmd:
            pending_command = cmd
            STATE = "CONFIRM_FINISH"
            speak_offline(f"You said, stop navigating. Is this correct?")
            is_listening = True 

    # --- IDLE STATE ---
    else:
        if "record" in cmd or "go to" in cmd or "navigate" in cmd:
            pending_command = cmd
            STATE = "CONFIRM_START"
            speak_offline(f"You said, {cmd}. Is this correct?")
            is_listening = True 

def trigger_listening():
    global is_listening
    if not is_speaking and not is_listening:
        is_listening = True
        print("👂 Triggered! Listening...")
        speak_offline("Listening")

# --- 6. OAK-D PIPELINE ---
def get_pipeline():
    p = dai.Pipeline()
    cam = p.create(dai.node.ColorCamera); cam.setPreviewSize(640, 480); cam.setBoardSocket(dai.CameraBoardSocket.CAM_A); cam.setInterleaved(False); cam.initialControl.setManualFocus(10)
    left = p.create(dai.node.MonoCamera); left.setBoardSocket(dai.CameraBoardSocket.CAM_B); left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    right = p.create(dai.node.MonoCamera); right.setBoardSocket(dai.CameraBoardSocket.CAM_C); right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    stereo = p.create(dai.node.StereoDepth); stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT); stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    left.out.link(stereo.left); right.out.link(stereo.right)
    imu = p.create(dai.node.IMU); imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 100)
    feat = p.create(dai.node.FeatureTracker); left.out.link(feat.inputImage)
    x_rgb = p.create(dai.node.XLinkOut); x_rgb.setStreamName("rgb"); cam.preview.link(x_rgb.input)
    x_dep = p.create(dai.node.XLinkOut); x_dep.setStreamName("depth"); stereo.depth.link(x_dep.input)
    x_imu = p.create(dai.node.XLinkOut); x_imu.setStreamName("imu"); imu.out.link(x_imu.input)
    x_fea = p.create(dai.node.XLinkOut); x_fea.setStreamName("feat"); feat.outputFeatures.link(x_fea.input)
    return p

def letterbox_image(img, size):
    h, w = img.shape[:2]; scale = min(size/w, size/h); nw, nh = int(w*scale), int(h*scale)
    res = cv2.resize(img, (nw, nh))
    new = np.zeros((size, size, 3), dtype=np.uint8) if len(img.shape)==3 else np.zeros((size, size), dtype=img.dtype)
    new[(size-nh)//2:(size-nh)//2+nh, (size-nw)//2:(size-nw)//2+nw] = res
    return new

# --- 6. MAIN RUNNER ---
def run():
    global total_dist, current_yaw, last_wp_dist, recorded_path, nav_path, is_listening, is_speaking, STATE
    global current_x, current_z, nav_engine
    
    print("⏳ Loading Vosk...")
    vosk_model = vosk.Model(VOSK_MODEL_PATH)
    rec = vosk.KaldiRecognizer(vosk_model, 16000, json.dumps(ALLOWED_WORDS))
    
    print("⏳ Loading Hailo NPU...")
    target = VDevice()
    hef = HEF(HEF_PATH)
    conf = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
    group = target.configure(hef, conf)[0]
    in_p = InputVStreamParams.make(group, format_type=FormatType.FLOAT32)
    out_p = OutputVStreamParams.make(group, format_type=FormatType.FLOAT32)
    input_name = hef.get_input_vstream_infos()[0].name

    # 🚀 FIX: Initialize button but do NOT use .when_pressed
    try:
        btn = Button(26, pull_up=True)
        print("✅ Button 26 initialized.")
    except Exception as e:
        print(f"❌ GPIO Error: {e}")
        btn = None
    
    devices = sd.query_devices()
    mic_idx, native_rate = 1, 44100 
    for i, dev in enumerate(devices):
        if "USB" in dev['name']: mic_idx, native_rate = i, int(dev['default_samplerate']); break

    def audio_callback(indata, frames, time_info, status):
        global is_listening, is_speaking
        if not is_listening or is_speaking: return
        audio_data = (indata * 32768).astype('int16').flatten()
        num_samples = int(len(audio_data) * 16000 / native_rate)
        indices = np.linspace(0, len(audio_data) - 1, num_samples).astype(int)
        resampled = audio_data[indices]
        
        if rec.AcceptWaveform(resampled.tobytes()):
            result = json.loads(rec.Result())
            cmd = result.get('text', '')
            if cmd:
                is_listening = False
                handle_voice_command(cmd)
                rec.Reset()

    last_imu_t, feat_history = None, {}
    button_was_pressed = False # Debounce variable

    with dai.Device(get_pipeline()) as device, \
         sd.InputStream(samplerate=native_rate, device=mic_idx, channels=1, dtype='float32', blocksize=4000, callback=audio_callback):
        
        q_rgb = device.getOutputQueue("rgb", 4, False); q_dep = device.getOutputQueue("depth", 4, False)
        q_imu = device.getOutputQueue("imu", 10, False); q_fea = device.getOutputQueue("feat", 4, False)
        
        with group.activate():
            with InferVStreams(group, in_p, out_p) as pipe:
                print("✅ SENSEY System Ready.")
                speak_offline("System Ready.")
                
                while True:
                    # 🚀 FIX: Synchronous Button Check with Debounce
                    if btn and btn.is_pressed:
                        if not button_was_pressed: # Ensure we only trigger once per press
                            button_was_pressed = True
                            trigger_listening()
                    else:
                        button_was_pressed = False # Reset when button is released

                    # Navigation Data Update
                    imuData = q_imu.tryGet()
                    if imuData:
                        for p in imuData.packets:
                            ts = time.time()
                            if last_imu_t: current_yaw += p.gyroscope.z * (180/math.pi) * (ts - last_imu_t)
                            last_imu_t = ts
                    
                    rgb_in = q_rgb.get(); dep_in = q_dep.get(); fea_in = q_fea.get()
                    frame, depth, features = rgb_in.getCvFrame(), dep_in.getFrame(), fea_in.trackedFeatures
                    
                    deltas = []
                    for f in features:
                        x, y = int(f.position.x), int(f.position.y)
                        if 0 <= y < depth.shape[0] and 0 <= x < depth.shape[1]:
                            z = depth[y, x] / 1000.0
                            if z > 0 and f.id in feat_history:
                                d_z = feat_history[f.id] - z
                                if MIN_Z_DELTA < abs(d_z) < MAX_Z_DELTA: deltas.append(d_z)
                            feat_history[f.id] = z
                    
                    if deltas: 
                        avg_step = sum(deltas)/len(deltas)
                        total_dist += avg_step
                        rad = math.radians(current_yaw)
                        current_x = total_dist * math.sin(rad)
                        current_z = total_dist * math.cos(rad)

                    if STATE == "RECORDING" and (total_dist - last_wp_dist) > 0.5:
                        recorded_path.append([current_x, current_z, "path"])
                        last_wp_dist = total_dist

                    if STATE == "NAVIGATING":
                        inst = nav_engine.get_instruction(current_x, current_z, current_yaw)
                        if inst:
                            threading.Thread(target=speak_offline, args=(inst,), daemon=True).start()

                    padded_img = letterbox_image(frame, 640)
                    f_in = cv2.cvtColor(padded_img, cv2.COLOR_BGR2RGB).astype(np.float32)
                    res = pipe.infer({input_name: np.expand_dims(f_in, axis=0)})
                    raw_dets = list(res.values())[0][0]

                    processed = inference_result_handler(
                        padded_img, raw_dets, LABELS, CONFIG_DATA, 
                        vio_data=(total_dist, current_yaw), 
                        waypoints=recorded_path if STATE in ["RECORDING", "CONFIRM_FINISH", "CONFIRM_START"] else None, 
                        nav_waypoints=nav_path if STATE in ["NAVIGATING", "CONFIRM_FINISH", "CONFIRM_START"] else None, 
                        depth_frame=letterbox_image(depth, 640), 
                        state_text=STATE
                    )
                    
                    cv2.imshow("SENSEY AR Navigator", processed)
                    if cv2.waitKey(1) == ord('q'): break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    run()