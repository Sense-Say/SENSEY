import cv2
import depthai as dai
import numpy as np
import sys, os, time, math, json, threading
from gtts import gTTS
from gpiozero import Button
from hailo_platform import HEF, VDevice, HailoStreamInterface, InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams, FormatType

# --- 1. SYSTEM SETUP ---
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"
os.environ["HAILO_SCHEDULER"] = "1"
DOC_PATH = "/home/raspberrypi/Documents/"
REPO_ROOT = "/home/raspberrypi/hailo-apps"

# Setup Paths for Module Discovery
WHISPER_BASE = os.path.join(REPO_ROOT, "hailo_apps/python/standalone_apps/speech_recognition")
WHISPER_APP_DIR = os.path.join(WHISPER_BASE, "app")
WHISPER_COMMON_DIR = os.path.join(WHISPER_BASE, "common")

# Add all relevant folders to Python path
for p in [REPO_ROOT, WHISPER_BASE, WHISPER_APP_DIR, WHISPER_COMMON_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

# --- VITAL FIX: Constructor Logic for HailoWhisperPipeline ---
try:
    from hailo_whisper_pipeline import HailoWhisperPipeline
    WHISPER_READY = True
    print("✅ HailoWhisperPipeline Class Found.")
except Exception as e:
    print(f"❌ CRITICAL: Could not load the whisper module. Error: {e}")
    WHISPER_READY = False

from hailo_apps.python.standalone_apps.object_detection.object_detection_post_process import inference_result_handler

# --- 2. CONFIGURATION ---
HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m.hef"
# Your exact downloaded paths for tiny models:
WH_ENC = "/home/raspberrypi/hailo-apps/resources/models/hailo8/hefs/h8/tiny/tiny-whisper-encoder-10s_15dB.hef"
WH_DEC = "/home/raspberrypi/hailo-apps/resources/models/hailo8/hefs/h8/tiny/tiny-whisper-decoder-fixed-sequence-matmul-split.hef"

LABELS = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"]
CONFIG_DATA = {"visualization_params": {"score_thres": 0.5, "max_boxes_to_draw": 50}}
MIN_Z_DELTA, MAX_Z_DELTA = 0.01, 0.30

# --- 3. STATE ---
STATE = "IDLE"
current_route_name, recorded_points, nav_points = "", [], []
total_dist, current_yaw, last_wp_dist = 0.0, 0.0, 0.0
is_busy = False 

def speak(text):
    print(f"🔊 {text}")
    def _run():
        try:
            tts = gTTS(text=text, lang='en')
            p = os.path.join(DOC_PATH, "voice.mp3")
            tts.save(p); os.system(f"mpg123 -q {p} > /dev/null 2>&1"); os.remove(p)
        except: pass
    threading.Thread(target=_run, daemon=True).start()

# --- 4. OFFLINE NPU VOICE COMMAND HANDLER ---
def listen_command_npu(whisper_pipeline):
    global STATE, current_route_name, recorded_points, nav_points, total_dist, last_wp_dist, current_yaw, is_busy
    if is_busy: return
    is_busy = True
    
    speak("NPU Listening")
    try:
        # Based on hailo_whisper_pipeline.py: run() records audio if input_audio is None
        print("🎤 (NPU) Recording & Transcribing...")
        # .run() returns the transcription string
        cmd = whisper_pipeline.run().lower().strip()
        print(f"💬 NPU Result: {cmd}")

        if "record" in cmd:
            current_route_name = cmd.replace("record", "").strip().replace(" ", "_")
            recorded_points = [[0.0, 0.0, "start"]]
            total_dist, last_wp_dist, current_yaw = 0.0, 0.0, 0.0
            STATE = "RECORDING"; speak(f"Recording {current_route_name}")
        elif "point" in cmd:
            if STATE == "RECORDING":
                rad = math.radians(current_yaw)
                recorded_points.append([total_dist * math.sin(rad), total_dist * math.cos(rad), "landmark"])
                speak("Point saved")
        elif "finish" in cmd:
            if STATE == "RECORDING":
                with open(os.path.join(DOC_PATH, f"{current_route_name}.json"), "w") as f: json.dump(recorded_points, f)
                STATE = "IDLE"; speak("Finished")
        elif "go to" in cmd:
            target = cmd.replace("go to", "").strip().replace(" ", "_")
            found = False
            for f in os.listdir(DOC_PATH):
                if f.endswith(".json"):
                    base = f.replace(".json","")
                    if target in base or base in target:
                        with open(os.path.join(DOC_PATH, f), "r") as jf: nav_points = json.load(jf)
                        if "to" in target and target.split("_to_")[0] in base.split("_to_")[-1]:
                            nav_points.reverse(); speak("Reversing route")
                        STATE = "NAVIGATING"; total_dist, last_wp_dist = 0.0, 0.0
                        speak(f"Navigating")
                        found = True; break
            if not found: speak("Route not found.")
    except Exception as e: 
        print(f"🎤 NPU Voice Error: {e}")
        speak("Retry")
    is_busy = False

# --- 5. PIPELINE SETUP ---
def get_pipeline():
    pipeline = dai.Pipeline()
    cam = pipeline.create(dai.node.ColorCamera); cam.setPreviewSize(640, 480); cam.setBoardSocket(dai.CameraBoardSocket.CAM_A); cam.setInterleaved(False); cam.initialControl.setManualFocus(10)
    left = pipeline.create(dai.node.MonoCamera); left.setBoardSocket(dai.CameraBoardSocket.CAM_B); left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    right = pipeline.create(dai.node.MonoCamera); right.setBoardSocket(dai.CameraBoardSocket.CAM_C); right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    stereo = pipeline.create(dai.node.StereoDepth); stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT); stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    left.out.link(stereo.left); right.out.link(stereo.right)
    imu = pipeline.create(dai.node.IMU); imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 100)
    feat = pipeline.create(dai.node.FeatureTracker); left.out.link(feat.inputImage)
    x_rgb = pipeline.create(dai.node.XLinkOut); x_rgb.setStreamName("rgb"); cam.preview.link(x_rgb.input)
    x_dep = pipeline.create(dai.node.XLinkOut); x_dep.setStreamName("depth"); stereo.depth.link(x_dep.input)
    x_imu = pipeline.create(dai.node.XLinkOut); x_imu.setStreamName("imu"); imu.out.link(x_imu.input)
    x_fea = pipeline.create(dai.node.XLinkOut); x_fea.setStreamName("feat"); feat.outputFeatures.link(x_fea.input)
    return pipeline

def letterbox_image(image, size):
    shape = image.shape; scale = min(size/shape[1], size/shape[0])
    nw, nh = int(shape[1] * scale), int(shape[0] * scale); res = cv2.resize(image, (nw, nh))
    new = np.zeros((size, size, 3), dtype=np.uint8) if len(shape)==3 else np.zeros((size, size), dtype=image.dtype)
    new[(size-nh)//2:(size-nh)//2+nh, (size-nw)//2:(size-nw)//2+nw] = res
    return new

# --- 6. MAIN RUNNER ---
def run():
    global total_dist, current_yaw, last_wp_dist, recorded_points, nav_points
    if not WHISPER_READY: return
    
    # 1. Init NPU Device for YOLO
    target = VDevice(); hef = HEF(HEF_PATH)
    conf = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
    group = target.configure(hef, conf)[0]; in_p = InputVStreamParams.make(group, format_type=FormatType.FLOAT32)
    out_p = OutputVStreamParams.make(group, format_type=FormatType.FLOAT32); input_name = hef.get_input_vstream_infos()[0].name

    # 2. Init Whisper Pipeline
    print("🚀 Loading Whisper NPU Engine...")
    # FIXED: The constructor takes (encoder_path, decoder_path) as the first two arguments
    whisper_pipeline = HailoWhisperPipeline(WH_ENC, WH_DEC)
    
    last_imu_t, feat_history = None, {}
    btn = Button(26); btn.when_pressed = lambda: threading.Thread(target=listen_command_npu, args=(whisper_pipeline,)).start()

    with dai.Device(get_pipeline()) as device:
        q_rgb = device.getOutputQueue("rgb", 4, False); q_dep = device.getOutputQueue("depth", 4, False)
        q_imu = device.getOutputQueue("imu", 10, False); q_fea = device.getOutputQueue("feat", 4, False)
        
        with group.activate():
            with InferVStreams(group, in_p, out_p) as pipe:
                while True:
                    # Update IMU Heading
                    imuData = q_imu.tryGet()
                    if imuData:
                        for packet in imuData.packets:
                            ts = time.time();
                            if last_imu_t: current_yaw += packet.gyroscope.z * (180/math.pi) * (ts - last_imu_t)
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
                    if deltas: total_dist += sum(deltas)/len(deltas)
                    if STATE == "RECORDING" and (total_dist - last_wp_dist) > 0.5:
                        rad = math.radians(current_yaw)
                        recorded_points.append([total_dist * math.sin(rad), total_dist * math.cos(rad), "path"])
                        last_wp_dist = total_dist
                    padded = letterbox_image(frame, 640)
                    f_in = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB).astype(np.float32)
                    res = pipe.infer({input_name: np.expand_dims(f_in, axis=0)})
                    raw_dets = list(res.values())[0][0]
                    processed = inference_result_handler(padded, raw_dets, LABELS, CONFIG_DATA, vio_data=(total_dist, current_yaw), waypoints=recorded_points if STATE == "RECORDING" else None, nav_waypoints=nav_points if STATE == "NAVIGATING" else None, depth_frame=letterbox_image(depth, 640), state_text=STATE)
                    cv2.imshow("SENSEY AR Navigator", processed)
                    if cv2.waitKey(1) == ord('q'): break
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run()