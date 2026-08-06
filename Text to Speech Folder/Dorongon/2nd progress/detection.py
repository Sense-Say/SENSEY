import sys
import os
from pathlib import Path

# -----------------------------------------------------------
# 1. FIX MODULE PATHS (Crucial for fresh SD cards)
# -----------------------------------------------------------
# We need to tell Python where the 'hailo_apps' folder is.
# Usually, it is in /home/raspberrypi/hailo-rpi5-examples
HAILO_EXAMPLES_PATH = "/home/raspberrypi/hailo-rpi5-examples"

if HAILO_EXAMPLES_PATH not in sys.path:
    sys.path.append(HAILO_EXAMPLES_PATH)

# 2. ENVIRONMENT SETUP
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"

# 3. IMPORTS
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import numpy as np
import cv2
import hailo

# These imports now work because of step 1
try:
    from hailo_apps.hailo_app_python.core.common.buffer_utils import get_caps_from_pad, get_numpy_from_buffer
    from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app import app_callback_class
    from hailo_apps.hailo_app_python.apps.detection.detection_pipeline import GStreamerDetectionApp
except ImportError as e:
    print(f"Import Error: {e}")
    print(f"Could not find Hailo modules. Please ensure the repo is at: {HAILO_EXAMPLES_PATH}")
    sys.exit(1)

# -----------------------------------------------------------------------------------------------
# User-defined class
# -----------------------------------------------------------------------------------------------
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        self.new_variable = 42 

    def new_function(self): 
        return "Status: Active"

# -----------------------------------------------------------------------------------------------
# User-defined callback function
# -----------------------------------------------------------------------------------------------
def app_callback(pad, info, user_data):
    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK

    user_data.increment()
    format, width, height = get_caps_from_pad(pad)

    # Get video frame
    frame = None
    if user_data.use_frame and format is not None and width is not None and height is not None:
        frame = get_numpy_from_buffer(buffer, format, width, height)

    # Get detections
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

    detection_count = 0
    for detection in detections:
        label = detection.get_label()
        if label == "person":
            detection_count += 1

    # Drawing logic
    if user_data.use_frame and frame is not None:
        # Convert RGB to BGR for OpenCV
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        # UI Overlays
        cv2.putText(frame, f"Persons detected: {detection_count}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"{user_data.new_function()}", (10, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # Use user_data.set_frame to show it in the GStreamer window
        user_data.set_frame(frame)

    return Gst.PadProbeReturn.OK

# -----------------------------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------------------------
def main():
    # --- UPDATE THESE PATHS TO YOUR ACTUAL FILES ---
    # Since it is a fresh SD card, make sure these files exist!
    HEF_PATH = "/home/raspberrypi/hailo-rpi5-examples/resources/models/hailo8/yolov8m.hef"
    VIDEO_PATH = "usb"

    # Validation
    if not os.path.exists(HEF_PATH):
        print(f"Error: HEF file not found at {HEF_PATH}")
        print("Please check the path or download the model using download_resources.sh")
        return
    
    # Inject arguments so GStreamerDetectionApp sees them
    sys.argv = [
        sys.argv[0],
        "--input", VIDEO_PATH,
        "--hef-path", HEF_PATH,
       # "--show-fps"
    ]

    print("Starting Hailo App...")
    user_data = user_app_callback_class()
    app = GStreamerDetectionApp(app_callback, user_data)
    app.run()

if __name__ == "__main__":
    main()