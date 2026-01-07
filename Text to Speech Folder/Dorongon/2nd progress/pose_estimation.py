import sys
import os
import time

os.environ["DISPLAY"] = ":0"
os.environ["QT_QPA_PLATFORM"] = "xcb"

# ===============================================================================================
# ⚡ FPS CONTROL
# ===============================================================================================
DESIRED_FPS = 15

# ===============================================================================================
# 🔧 SETUP PATHS & IMPORTS
# ===============================================================================================
# 1. Setup Hailo Environment Paths
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

# 2. Add current directory to path to find action_logic.py
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# 3. Import Custom Logic
try:
    import action_logic
    import importlib
    importlib.reload(action_logic) # Ensures we use the latest edited version
    from action_logic import StudentActionMonitor
except ImportError:
    print(f"\n❌ ERROR: Could not import 'action_logic.py'. Make sure it is in the same folder.")
    sys.exit(1)

# 4. Standard Imports
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

# Initialize Logic Class
action_monitor = StudentActionMonitor()

# ===============================================================================================
# APP CALLBACK
# ===============================================================================================
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        # We disable the frame copy because we are only printing text to the console
        self.use_frame = False 
        
        # 🟢 PRINT TIMER SETUP
        self.last_print_time = time.time()
        self.print_interval = 0.5  # Print status every 0.5 seconds

def app_callback(pad, info, user_data):
    buffer = info.get_buffer()
    if buffer is None: return Gst.PadProbeReturn.OK

    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
    
    active_students = [] 
    counts = {"Standing": 0, "Walking": 0, "Raising Hand": 0}

    # 1. Gather Data
    for detection in detections:
        if detection.get_label() == "person":
            # Get ID (Required for Walking Logic)
            track_id = 0
            track = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
            if len(track) == 1: track_id = track[0].get_id()
            
            landmarks = detection.get_objects_typed(hailo.HAILO_LANDMARKS)
            
            if len(landmarks) > 0:
                points = landmarks[0].get_points()
                # Create simple list of [x, y, confidence]
                kp_list = [[p.x(), p.y(), p.confidence()] for p in points]
                
                # Get Bounding Box Center (Normalized 0.0 - 1.0)
                bbox = detection.get_bbox()
                center_x = bbox.xmin() + (bbox.width() / 2)
                center_y = bbox.ymin() + (bbox.height() / 2)

                # --- RUN LOGIC ---
                try:
                    # Logic returns (Action, Color). We only need Action here.
                    action_text, _ = action_monitor.get_action(kp_list, track_id, (center_x, center_y))
                except Exception:
                    action_text = "Standing"
                
                # Update counts
                if action_text in counts:
                    counts[action_text] += 1
                
                # Create short string for console (e.g., ID1:W, ID2:S)
                short_code = action_text[0] # 'W', 'S', 'R'
                if action_text == "Raising Hand": short_code = "R"
                
                active_students.append(f"ID{track_id}:{short_code}")

    # 2. PRINT LIMITER (Only runs every 0.5 seconds to keep terminal clean)
    current_time = time.time()
    if (current_time - user_data.last_print_time) > user_data.print_interval:
        
        if len(active_students) > 0:
            print(f"FPS:{DESIRED_FPS} | Raised: {counts['Raising Hand']} | "
                  f"Walk: {counts['Walking']} | "
                  f"Stand: {counts['Standing']} || "
                  f"Status: {active_students}")
        else:
            # Optional: Print that no one is detected
            # print("No students detected.")
            pass
        
        # Reset the timer
        user_data.last_print_time = current_time

    return Gst.PadProbeReturn.OK

# ===============================================================================================
# MAIN EXECUTION
# ===============================================================================================
if __name__ == "__main__":
    
    # Path to your HEF model
    HEF_PATH = "/home/raspberrypi/hailo-rpi5-examples/resources/models/hailo8/yolov8m_pose.hef"

    # If running from Thonny/Editor without arguments, inject defaults
    if len(sys.argv) == 1:
        print("--- THONNY / NO ARGS DETECTED: USING DEFAULTS ---")
        
        # 1. Input: Use USB Camera (/dev/video0)
        # Change "usb" to a file path if you want to test a video file
        sys.argv.extend(["--input", "usb"]) 
        
        # 2. Sync: Disable sync for lowest latency on camera
        sys.argv.extend(["--disable-sync"])
        
        # 3. Hardware Frame Rate limit
        sys.argv.extend(["--frame-rate", str(DESIRED_FPS)])

        # 4. Model Path
        if os.path.exists(HEF_PATH):
            sys.argv.extend(["--hef-path", HEF_PATH])
        else:
            print(f"WARNING: HEF model not found at {HEF_PATH}")

    print(f"Starting Classroom Monitor...")
    print(f"Update Rate: Text prints every 0.5 seconds.")
    print("-----------------------------------")
    
    user_data = user_app_callback_class()
    app = GStreamerPoseEstimationApp(app_callback, user_data)
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("\nExiting...")
