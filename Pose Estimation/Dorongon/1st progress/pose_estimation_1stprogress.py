import sys
import os
import logging

# ===============================================================================================
# 🔧 ENVIRONMENT CONFIGURATION
# ===============================================================================================
REPO_ROOT = "/home/raspberrypi/hailo-rpi5-examples"

# 1. Load .env file
env_path = os.path.join(REPO_ROOT, ".env")
if os.path.exists(env_path):
    print(f"✅ Loading configuration from: {env_path}")
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                if value.startswith("./"):
                    value = os.path.join(REPO_ROOT, value[2:])
                os.environ[key] = value

# 2. Add Virtual Env to Path
venv_site_packages = os.path.join(REPO_ROOT, "venv_hailo_rpi_examples/lib/python3.11/site-packages")
if os.path.exists(venv_site_packages):
    sys.path.insert(0, venv_site_packages)

# ===============================================================================================
# 🔧 CUSTOM LOGIC IMPORT
# ===============================================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from action_logic import StudentActionMonitor
except ImportError:
    print(f"\n❌ ERROR: Could not import 'action_logic_1stprogress.py'.")
    print(f"Make sure action_logic.py is in the same folder as this script: {current_dir}")
    sys.exit(1)

# ===============================================================================================
# IMPORTS
# ===============================================================================================
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GObject
import cv2
import numpy as np
import hailo

try:
    from hailo_apps.hailo_app_python.apps.pose_estimation.pose_estimation_pipeline import GStreamerPoseEstimationApp
    from hailo_apps.hailo_app_python.core.common.buffer_utils import get_caps_from_pad, get_numpy_from_buffer
    from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app import app_callback_class
except ImportError as e:
    print(f"\n❌ IMPORT ERROR: {e}")
    sys.exit(1)

# Initialize Logic
action_monitor = StudentActionMonitor()

# ===============================================================================================
# APP CALLBACK
# ===============================================================================================
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        self.use_frame = True 

def app_callback(pad, info, user_data):
    buffer = info.get_buffer()
    if buffer is None: return Gst.PadProbeReturn.OK

    format, width, height = get_caps_from_pad(pad)
    
    frame = None
    if user_data.use_frame and format and width and height:
        frame = get_numpy_from_buffer(buffer, format, width, height)

    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
    
    for detection in detections:
        if detection.get_label() == "person":
            track_id = 0
            track = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
            if len(track) == 1: track_id = track[0].get_id()
            
            landmarks = detection.get_objects_typed(hailo.HAILO_LANDMARKS)
            if len(landmarks) > 0:
                points = landmarks[0].get_points()
                kp_list = [[p.x(), p.y(), p.confidence()] for p in points]
                
                bbox = detection.get_bbox()
                center_x = bbox.xmin() + (bbox.width() / 2)
                center_y = bbox.ymin() + (bbox.height() / 2)

                # --- LOGIC & DRAWING ---
                status = action_monitor.get_action(kp_list, track_id, (center_x, center_y))

                if frame is not None:
                    x = int(bbox.xmin() * width)
                    y = int(bbox.ymin() * height) - 10
                    if y < 20: y = 20
                    
                    color = (0, 255, 0) # Green
                    if "Raising Hand" in status: color = (0, 0, 255) # Red
                    elif "Walking" in status: color = (255, 0, 0) # Blue

                    cv2.putText(frame, f"ID {track_id}: {status}", (x, y), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    if user_data.use_frame and frame is not None:
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        user_data.set_frame(frame)
        user_data.increment()

    return Gst.PadProbeReturn.OK

# ===============================================================================================
# 🔧 MAIN EXECUTION (MODEL SELECTION)
# ===============================================================================================
if __name__ == "__main__":
    
    # ------------------------------------------------------------------
    # CHANGE THIS PATH TO SWITCH MODELS
    # ------------------------------------------------------------------
    NEW_MODEL_PATH = "/home/raspberrypi/hailo-rpi5-examples/resources/models/hailo8/yolov8m_pose.hef"
    # ------------------------------------------------------------------

    # Auto-Argument Injection for Thonny
    if len(sys.argv) == 1:
        print("--- THONNY MODE ---")
        
        # 1. Set Camera Input
        print("Setting input to /dev/video0")
        sys.argv.extend(["--input", "/dev/video0"])
        
        # 2. Set Custom Model (yolov8m_pose)
        if os.path.exists(NEW_MODEL_PATH):
            print(f"Setting custom model: {os.path.basename(NEW_MODEL_PATH)}")
            sys.argv.extend(["--hef-path", NEW_MODEL_PATH])
        else:
            print(f"⚠️ WARNING: Custom model not found at: {NEW_MODEL_PATH}")
            print("Using default model (yolov8s_pose) instead.")

    print("Starting Application...")
    user_data = user_app_callback_class()
    app = GStreamerPoseEstimationApp(app_callback, user_data)
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("Stopping...")