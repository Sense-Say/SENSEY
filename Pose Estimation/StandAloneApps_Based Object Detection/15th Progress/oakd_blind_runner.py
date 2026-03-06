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
        self.path = []
        self.current_wp_index = 0
        self.active = False
        self.target_yaw = 0.0
        self.distance_to_wp = 0.0
        self.offset_x, self.offset_z, self.offset_yaw = 0.0, 0.0, 0.0
        self.stride_length = 0.75 

    def load_path(self, path_data):
        """🚀 CLEW AUTO-TURN LOGIC: Filters out tiny segments."""
        raw_nodes = []
        for p in path_data:
            raw_nodes.append({
                "x": p[0], "z": p[1], "label": p[2], 
                "yaw": p[3] if len(p) > 3 else 0.0,
                "note": p[4] if len(p) > 4 else ""
            })
        
        self.path = [raw_nodes[0]] 
        for i in range(1, len(raw_nodes) - 1):
            prev, curr, next_n = raw_nodes[i-1], raw_nodes[i], raw_nodes[i+1]
            
            # Calculate segment length
            seg_dist = math.sqrt((curr['x'] - self.path[-1]['x'])**2 + (curr['z'] - self.path[-1]['z'])**2)
            
            angle1 = math.atan2(curr['x'] - prev['x'], curr['z'] - prev['z'])
            angle2 = math.atan2(next_n['x'] - curr['x'], next_n['z'] - curr['z'])
            diff = abs(math.degrees(angle2 - angle1 + math.pi) % 360 - 180)
            
            # 🚀 FIX: Only keep nodes if they are > 0.6m away OR a major turn
            if seg_dist > 0.6 or diff > 30 or curr['note'] != "":
                self.path.append(curr)
        
        self.path.append(raw_nodes[-1]) 
        self.active = True
        self.current_wp_index = 1 if len(self.path) > 1 else 0
        self.offset_x, self.offset_z, self.offset_yaw = 0, 0, 0
        print(f"🚀 Path loaded. Compressed into {len(self.path)} navigation nodes.")

    def get_human_direction(self, target_yaw, current_yaw):
        error = (target_yaw - current_yaw + 180) % 360 - 180
        if -22.5 <= error <= 22.5: return "straight ahead"
        elif 22.5 < error <= 67.5: return "front right"
        elif 67.5 < error <= 112.5: return "to your right side"
        elif 112.5 < error <= 157.5: return "back right"
        elif -67.5 <= error < -22.5: return "front left"
        elif -112.5 <= error < -67.5: return "to your left side"
        elif -157.5 <= error < -112.5: return "back left"
        else: return "directly behind you"

    def get_instruction(self, cur_x, cur_z, cur_yaw, is_on_demand=False):
        global STATE, is_speaking
        if not self.active or self.current_wp_index >= len(self.path): return None
        
        # 🚀 FIX: If the system is already speaking, don't calculate a new instruction
        if is_speaking and not is_on_demand: return None

        target = self.path[self.current_wp_index]
        tx, tz = target["x"] + self.offset_x, target["z"] + self.offset_z
        self.distance_to_wp = math.sqrt((tx - cur_x)**2 + (tz - cur_z)**2)
        self.target_yaw = math.degrees(math.atan2(tx - cur_x, tz - cur_z)) % 360
        
        direction_word = self.get_human_direction(self.target_yaw, cur_yaw)
        steps = max(1, int(self.distance_to_wp / self.stride_length))

        if is_on_demand:
            return f"Target is {direction_word}. Walk {steps} steps."

        if self.distance_to_wp < 0.5:
            self.current_wp_index += 1
            if self.current_wp_index >= len(self.path):
                self.active = False
                STATE = "IDLE"
                return "Arrived at destination."
            
            next_target = self.path[self.current_wp_index]
            nx, nz = next_target["x"] + self.offset_x, next_target["z"] + self.offset_z
            next_dist = math.sqrt((nx - tx)**2 + (nz - tz)**2)
            next_steps = max(1, int(next_dist / self.stride_length))
            next_yaw = math.degrees(math.atan2(nx - tx, nz - tz)) % 360
            next_direction = self.get_human_direction(next_yaw, cur_yaw)
            
            msg = ""
            if target['note']: msg += f"Note: {target['note']}. "
            
            if "ahead" in next_direction:
                msg += f"Continue straight for {next_steps} steps."
            else:
                msg += f"Turn {next_direction} and walk {next_steps} steps."
            return msg
        return None

    def get_path_remaining_distance(self, cur_x, cur_z):
        if not self.active or self.current_wp_index >= len(self.path): return 0.0
        target = self.path[self.current_wp_index]
        d = math.sqrt((target["x"] + self.offset_x - cur_x)**2 + (target["z"] + self.offset_z - cur_z)**2)
        for i in range(self.current_wp_index, len(self.path) - 1):
            p1, p2 = self.path[i], self.path[i+1]
            d += math.sqrt((p2["x"] - p1["x"])**2 + (p2["z"] - p1["z"])**2)
        return d

    def get_path_remaining_distance(self, cur_x, cur_z):
        # This is used for the HUD display if you want total remaining distance
        if not self.active or self.current_wp_index >= len(self.path): return 0.0
        target = self.path[self.current_wp_index]
        d = math.sqrt((target["x"] + self.offset_x - cur_x)**2 + (target["z"] + self.offset_z - cur_z)**2)
        for i in range(self.current_wp_index, len(self.path) - 1):
            p1, p2 = self.path[i], self.path[i+1]
            d += math.sqrt((p2["x"] - p1["x"])**2 + (p2["z"] - p1["z"])**2)
        return d

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
    """Mouth: Uses Piper, but does NOT block the main loop."""
    global is_speaking
    if not text.strip(): return
    
    def _speak_thread():
        global is_speaking
        is_speaking = True
        print(f"🔊 Speaking: {text}")
        # Use aplay for standard output
        cmd = f'echo "{text}" | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | aplay -r 22050 -f S16_LE -t raw > /dev/null 2>&1'
        subprocess.run(cmd, shell=True)
        is_speaking = False
        
    threading.Thread(target=_speak_thread, daemon=True).start()

def execute_action(cmd):
    global STATE, recorded_path, nav_path, total_dist, current_yaw, last_wp_dist, current_route_filename, landmark_count, current_x, current_z, nav_engine
    
    if "record" in cmd:
        STATE = "RECORDING"
        raw_name = cmd.replace("record", "").strip().replace(" ", "_")
        current_route_filename = raw_name if raw_name else f"path_{int(time.time())}"
        recorded_path = [[0.0, 0.0, "start", current_yaw, ""]]
        total_dist, current_yaw, current_x, current_z, last_wp_dist = 0.0, 0.0, 0.0, 0.0, 0.0
        landmark_count = 0
        speak_offline(f"Recording {raw_name.replace('_', ' ')}. Anchor set.")

    elif "finish" in cmd or "stop" in cmd:
        if len(recorded_path) > 0:
            recorded_path.append([current_x, current_z, "destination", current_yaw, ""])
            file_path = os.path.join(DOC_PATH, f"{current_route_filename}.json")
            with open(file_path, "w") as f: json.dump(recorded_path, f)
            speak_offline(f"Route saved.")
        if STATE == "NAVIGATING":
            nav_engine.active = False
            speak_offline("Navigation stopped.")
        STATE = "IDLE"

    elif "go to" in cmd or "navigate" in cmd:
        target = cmd.replace("go to", "").replace("navigate", "").strip().replace(" ", "_")
        found = False
        for f in os.listdir(DOC_PATH):
            if f.endswith(".json"):
                base_name = f.replace(".json", "")
                is_reverse = False
                if "_to_" in target and "_to_" in base_name:
                    t_parts = target.split("_to_")
                    b_parts = base_name.split("_to_")
                    if t_parts[0] == b_parts[1] and t_parts[1] == b_parts[0]:
                        is_reverse = True

                if target == base_name or is_reverse:
                    with open(os.path.join(DOC_PATH, f), "r") as jf:
                        loaded_data = json.load(jf)
                    
                    if isinstance(loaded_data, list):
                        nav_path = loaded_data
                        if is_reverse:
                            nav_path.reverse()
                            # 🚀 REVERSE START: Tell the user to turn around immediately
                            speak_offline("Reversing route. Please turn around.")
                        
                        STATE = "NAVIGATING"
                        total_dist, current_yaw, current_x, current_z = 0.0, 0.0, 0.0, 0.0
                        nav_engine.load_path(nav_path)
                        found = True; break

def handle_voice_command(cmd):
    global STATE, pending_command, is_listening, recorded_path, landmark_count, current_x, current_z, current_yaw, previous_state
    cmd = cmd.lower().strip()
    if not cmd: return

    print(f"✅ Voice Input: {cmd} (State: {STATE})")

    if STATE == "CONFIRM_START":
        if "yes" in cmd or "correct" in cmd: execute_action(pending_command)
        else: STATE = "IDLE"; speak_offline("Cancelled.")
        pending_command = ""

    elif STATE == "CONFIRM_FINISH":
        if "yes" in cmd or "correct" in cmd: execute_action(pending_command)
        else: STATE = previous_state; speak_offline("Resuming.")
        pending_command = ""

    elif STATE == "CONFIRM_NOTE":
        if "yes" in cmd or "correct" in cmd:
            STATE = "RECORDING_NOTE"
            speak_offline("Say your voice note now.")
            is_listening = True
        else:
            STATE = "RECORDING"
            speak_offline("Continuing recording.")

    elif STATE == "RECORDING_NOTE":
        if len(recorded_path) > 0:
            recorded_path[-1][4] = cmd 
        STATE = "RECORDING"
        speak_offline("Voice note saved. Continuing recording.")

    elif STATE == "RECORDING":
        if "point" in cmd and "saved" in cmd:
            landmark_count += 1
            recorded_path.append([current_x, current_z, f"point_{landmark_count}", current_yaw, ""])
            STATE = "CONFIRM_NOTE"
            speak_offline(f"Point {landmark_count} saved. Do you want to add a voice note?")
            is_listening = True
        elif "finish" in cmd or "stop" in cmd:
            pending_command = "finish"; previous_state = "RECORDING"; STATE = "CONFIRM_FINISH"
            speak_offline("Stop recording. Is this correct?"); is_listening = True 

    elif STATE == "NAVIGATING":
        if "update" in cmd:
            status = nav_engine.get_instruction(current_x, current_z, current_yaw, is_on_demand=True)
            if status: speak_offline(status)
        elif "finish" in cmd or "stop" in cmd:
            pending_command = "stop"; previous_state = "NAVIGATING"; STATE = "CONFIRM_FINISH"
            speak_offline("Stop navigation. Is this correct?"); is_listening = True 

    else: # IDLE
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

    left = p.create(dai.node.MonoCamera)
    left.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
    
    right = p.create(dai.node.MonoCamera)
    right.setBoardSocket(dai.CameraBoardSocket.CAM_C)
    right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
    
    stereo = p.create(dai.node.StereoDepth)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    stereo.setOutputSize(1344, 1008) 
    
    # 🚀 THE FIX: Enable Left-Right Check
    # This forces the camera to return 0 instead of "guessing" 2m-3m when objects are < 0.4m away.
    stereo.setLeftRightCheck(True)
    
    left.out.link(stereo.left)
    right.out.link(stereo.right)
    
    imu = p.create(dai.node.IMU)
    imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 100)
    imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 100)
    imu.setBatchReportThreshold(1)
    imu.setMaxBatchReports(20)
    
    feat = p.create(dai.node.FeatureTracker)
    feat.setHardwareResources(2, 2)
    feat.initialConfig.setNumTargetFeatures(320)
    left.out.link(feat.inputImage)
    
    x_isp = p.create(dai.node.XLinkOut); x_isp.setStreamName("isp"); cam.isp.link(x_isp.input)
    x_pre = p.create(dai.node.XLinkOut); x_pre.setStreamName("pre"); cam.preview.link(x_pre.input)
    x_dep = p.create(dai.node.XLinkOut); x_dep.setStreamName("depth"); stereo.depth.link(x_dep.input)
    x_imu = p.create(dai.node.XLinkOut); x_imu.setStreamName("imu"); imu.out.link(x_imu.input)
    x_fea = p.create(dai.node.XLinkOut); x_fea.setStreamName("feat"); feat.outputFeatures.link(x_fea.input)
    
    return p

def run():
    global total_dist, current_yaw, last_wp_dist, recorded_path, nav_path, is_listening, is_speaking, STATE, current_x, current_z
    
    # 🚀 1. INITIALIZE CORE VARIABLES & FILTERS
    curr_yaw, curr_pitch, curr_roll = 0.0, 0.0, 0.0
    smooth_yaw = 0.0 
    gx, gy, gz = 0.0, 0.0, 0.0 
    last_imu_t = None
    feat_history = {} 
    motion_window = [] 
    raw_dets = [] 
    path_dist = 0.0 
    warmup_frames = 0
    
    # 🚀 CONFIG
    CALIBRATION_SCALE = 1.66 
    PERSON_CLASS_ID = 0 

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

    button_was_pressed = False

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

                    # 🚀 2. IMU FUSION
                    imuData = q_imu.tryGetAll() 
                    for data in imuData:
                        for packet in data.packets:
                            ts = packet.acceleroMeter.timestamp.get().total_seconds()
                            if last_imu_t is None: last_imu_t = ts; continue
                            dt = ts - last_imu_t; last_imu_t = ts
                            ax, ay, az = packet.acceleroMeter.x, packet.acceleroMeter.z, packet.acceleroMeter.y
                            gx, gy, gz = packet.gyroscope.x, packet.gyroscope.z, packet.gyroscope.y
                            current_yaw -= (gz * (180.0 / math.pi) * dt)
                            curr_pitch = 0.98 * (curr_pitch + gx * (180.0/math.pi) * dt) + 0.02 * math.degrees(math.atan2(ay, math.sqrt(ax**2 + az**2)))
                            curr_roll = 0.98 * (curr_roll + gy * (180.0/math.pi) * dt) + 0.02 * math.degrees(math.atan2(ax, az))
                            current_yaw = (current_yaw + 180) % 360 - 180
                            smooth_yaw = (0.8 * smooth_yaw) + (0.2 * current_yaw)

                    # 🚀 3. FETCH SENSOR FRAMES
                    rgb_isp = q_isp.get().getCvFrame(); rgb_pre = q_pre.get().getCvFrame() 
                    depth_raw = q_dep.get().getFrame(); fea_data = q_fea.get().trackedFeatures
                    
                    # 🚀 4. AI-MASKED PEDOMETER WITH VISUALS
                    deltas = []
                    is_rotating = abs(gz) > 0.1 or abs(gx) > 0.1
                    
                    if not is_rotating:
                        for f in fea_data:
                            x, y = int(f.position.x), int(f.position.y)
                            dx, dy = int(x * 1344/640), int(y * 1008/480)
                            
                            if 0 <= dy < 1008 and 0 <= dx < 1344:
                                # --- DYNAMIC MASKING ---
                                is_on_person = False
                                if len(raw_dets) > 0:
                                    for class_id, class_list in enumerate(raw_dets[0] if isinstance(raw_dets, list) else raw_dets):
                                        if class_id == PERSON_CLASS_ID:
                                            for det in class_list:
                                                if len(det) >= 5 and det[4] > 0.5:
                                                    ymin, xmin, ymax, xmax = det[:4]
                                                    if (xmin*1344) <= dx <= (xmax*1344) and (ymin*1008) <= dy <= (ymax*1008):
                                                        is_on_person = True; break
                                        if is_on_person: break
                                
                                # 🟢 VISUALIZER: Draw dots
                                if is_on_person:
                                    cv2.circle(rgb_isp, (dx, dy), 2, (0, 0, 255), -1) # RED for masked
                                    continue 
                                else:
                                    cv2.circle(rgb_isp, (dx, dy), 2, (0, 255, 255), -1) # YELLOW for tracked

                                z = depth_raw[dy, dx] / 1000.0
                                if 0.8 < z < 8.0:
                                    if f.id in feat_history:
                                        d_z = feat_history[f.id] - z
                                        if abs(d_z) < 0.40: deltas.append(d_z)
                                    feat_history[f.id] = z
                    
                    if len(feat_history) > 500: feat_history.clear()
                    frame_move = sum(deltas) / len(deltas) if deltas else 0.0
                    motion_window.append(frame_move)
                    if len(motion_window) > 10: motion_window.pop(0)
                    smooth_move = sum(motion_window) / len(motion_window)

                    if warmup_frames < 30:
                        warmup_frames += 1
                        total_dist = 0.0 
                    elif smooth_move > 0.005: 
                        total_dist += (smooth_move * CALIBRATION_SCALE)
                        rad_yaw = math.radians(current_yaw)
                        current_x = total_dist * math.sin(rad_yaw); current_z = total_dist * math.cos(rad_yaw)

                    # 🚀 5. CLEW RECORDING & NAVIGATION
                    if STATE == "RECORDING":
                        last_p = recorded_path[-1]
                        dist_from_last = math.sqrt((current_x - last_p[0])**2 + (current_z - last_p[1])**2)
                        yaw_change = abs(current_yaw - last_p[3])
                        if dist_from_last > 0.6 or yaw_change > 20:
                            recorded_path.append([current_x, current_z, "path", current_yaw, ""])

                    # Inside the run() loop while True:
                    if STATE == "NAVIGATING":
                        # 🚀 Only request instruction if NOT currently speaking
                        if not is_speaking:
                            inst = nav_engine.get_instruction(current_x, current_z, current_yaw)
                            if inst: 
                                speak_offline(inst) # This function handles its own thread
                        
                        hud_dist = nav_engine.distance_to_wp
                        play_navigation_tick(current_yaw, nav_engine.target_yaw, screen_width=1024)

                    # AI Inference and UI Render
                    res = pipe.infer({input_name: np.expand_dims(rgb_pre, axis=0)})
                    raw_dets = list(res.values())[0]
                    
                    processed = inference_result_handler(
                        rgb_isp, raw_dets, LABELS, CONFIG_DATA, 
                        vio_data=(total_dist, smooth_yaw, curr_pitch, curr_roll), 
                        target_yaw=nav_engine.target_yaw if STATE == "NAVIGATING" else None, 
                        target_dist=path_dist if STATE == "NAVIGATING" else None,
                        depth_frame=depth_raw, state_text=STATE
                    )

                    # Run Hailo Inference
                    res = pipe.infer({input_name: np.expand_dims(rgb_pre, axis=0)})
                    raw_dets = list(res.values())[0]
                    
                    processed = inference_result_handler(
                        rgb_isp, raw_dets, LABELS, CONFIG_DATA, 
                        vio_data=(total_dist, smooth_yaw, curr_pitch, curr_roll), 
                        target_yaw=nav_engine.target_yaw if STATE == "NAVIGATING" else None, 
                        target_dist=path_dist if STATE == "NAVIGATING" else None,
                        depth_frame=depth_raw, state_text=STATE
                    )
                    cv2.imshow("SENSEY 6-DOF AR Navigator", cv2.resize(processed, (1024, 768)))
                    if cv2.waitKey(1) == ord('q'): break
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run()