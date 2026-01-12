import sys
import os
import time

# -----------------------------------------------------------
# 1. SOFT PAUSE CONFIG
# -----------------------------------------------------------
PAUSE_FLAG = "/tmp/hailo_pause"

os.environ["DISPLAY"] = ":0"
os.environ["QT_QPA_PLATFORM"] = "xcb"

# ===============================================================================================
# ⚡ FPS CONTROL
# ===============================================================================================
DESIRED_FPS = 10

# ===============================================================================================
# 🔧 SETUP PATHS & IMPORTS
# ===============================================================================================
REPO_ROOT = "/home/raspberrypi/hailo-rpi5-examples"
env_path = os.path.join(REPO_ROOT, ".env")
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                if value.startswith("./"):
                    value = os.path.join(REPO_ROOT, value[2:])
                os.environ[key] = value

venv_site_packages = os.path.join(REPO_ROOT, "venv_hailo_rpi_examples/lib/python3.11/site-packages")
if os.path.exists(venv_site_packages):
    sys.path.insert(0, venv_site_packages)

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    import action_logic
    import importlib
    importlib.reload(action_logic)
    from action_logic import StudentActionMonitor
except ImportError:
    print(f"\n❌ ERROR: Could not import 'action_logic.py'.")
    sys.exit(1)

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GObject
import hailo

try:
    from hailo_apps.hailo_app_python.apps.pose_estimation.pose_estimation_pipeline import GStreamerPoseEstimationApp
    from hailo_apps.hailo_app_python.core.common.buffer_utils import get_caps_from_pad
    from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app import app_callback_class
except ImportError as e:
    print(f"\n❌ IMPORT ERROR: {e}")
    sys.exit(1)

action_monitor = StudentActionMonitor()

# ===============================================================================================
# APP CALLBACK
# ===============================================================================================
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        self.use_frame = False 
        self.last_print_time = time.time()
        self.print_interval = 0.5

def app_callback(pad, info, user_data):
    # --- SOFT PAUSE CHECK ---
    is_paused = os.path.exists(PAUSE_FLAG)

    buffer = info.get_buffer()
    if buffer is None: return Gst.PadProbeReturn.OK

    user_data.increment()

    # If paused, we skip ALL logic to save CPU for Ollama
    # The Master Controller already has the last 10 lines in its buffer
    if is_paused:
        return Gst.PadProbeReturn.OK

    # 1. Gather Data (ONLY IF NOT PAUSED)
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
    
    active_students = [] 
    counts = {"Standing": 0, "Walking": 0, "Raising Hand": 0}

    for detection in detections:
        if detection.get_label() == "person":
            track_id = 0
            track = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
            if len(track) == 1: track_id = track[0].get_id()
            
            landmarks = detection.get_objects_typed(hailo.HAILO_LANDMARKS)
            
            if len(landmarks) > 0:
                # CPU HEAVY: Processing keypoints
                points = landmarks[0].get_points()
                kp_list = [[p.x(), p.y(), p.confidence()] for p in points]
                
                bbox = detection.get_bbox()
                center_x = bbox.xmin() + (bbox.width() / 2)
                center_y = bbox.ymin() + (bbox.height() / 2)

                # CPU HEAVY: Running custom action logic
                try:
                    action_text, _ = action_monitor.get_action(kp_list, track_id, (center_x, center_y))
                except Exception:
                    action_text = "Standing"
                
                if action_text in counts:
                    counts[action_text] += 1
                
                short_code = action_text[0] 
                if action_text == "Raising Hand": short_code = "R"
                active_students.append(f"ID{track_id}:{short_code}")

    # 2. PRINT LIMITER
    current_time = time.time()
    if (current_time - user_data.last_print_time) > user_data.print_interval:
        if len(active_students) > 0:
            print(f"FPS:{DESIRED_FPS} | Raised: {counts['Raising Hand']} | "
                  f"Walk: {counts['Walking']} | "
                  f"Stand: {counts['Standing']} || "
                  f"Status: {active_students}")
        user_data.last_print_time = current_time

    return Gst.PadProbeReturn.OK

# ===============================================================================================
# MAIN EXECUTION
# ===============================================================================================
if __name__ == "__main__":
    HEF_PATH = "/home/raspberrypi/hailo-rpi5-examples/resources/models/hailo8/yolov8m_pose.hef"

    if len(sys.argv) == 1:
        sys.argv.extend(["--input", "usb"]) 
        sys.argv.extend(["--disable-sync"])
        sys.argv.extend(["--frame-rate", str(DESIRED_FPS)])
        if os.path.exists(HEF_PATH):
            sys.argv.extend(["--hef-path", HEF_PATH])

    print(f"Starting Classroom Monitor (With AI-Pause Support)...")
    user_data = user_app_callback_class()
    app = GStreamerPoseEstimationApp(app_callback, user_data)
    
    try:
        app.run()
    except KeyboardInterrupt:
        pass