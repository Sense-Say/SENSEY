import sys
import os
import time
from pathlib import Path

# -----------------------------------------------------------
# 1. FIX MODULE PATHS
# -----------------------------------------------------------
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

try:
    from hailo_apps.hailo_app_python.core.common.buffer_utils import get_caps_from_pad, get_numpy_from_buffer
    from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app import app_callback_class
    from hailo_apps.hailo_app_python.apps.detection.detection_pipeline import GStreamerDetectionApp
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

# -----------------------------------------------------------------------------------------------
# User-defined class
# -----------------------------------------------------------------------------------------------
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        self.last_print_time = time.time()
        self.frame_count_at_last_print = 0

# -----------------------------------------------------------------------------------------------
# User-defined callback function
# -----------------------------------------------------------------------------------------------
def app_callback(pad, info, user_data):
    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK

    user_data.increment()
    format, width, height = get_caps_from_pad(pad)

    # Get detections
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

    # ---------------------------------------------------------
    # TERMINAL OUTPUT LOGIC (0.5s interval)
    # ---------------------------------------------------------
    current_time = time.time()
    elapsed_since_print = current_time - user_data.last_print_time

    detection_reports = []
    status_list = []

    for detection in detections:
        label = detection.get_label()
        bbox = detection.get_bbox()
        mid_x = (bbox.xmin() + bbox.xmax()) / 2
        
        # Column Logic
        if mid_x < 0.33:
            column, col_code = "right", "R"
        elif mid_x < 0.66:
            column, col_code = "center", "C"
        else:
            column, col_code = "left", "L"
            
        detection_reports.append(f"{label} on {column}")
        
        # Track ID for Status
        track_id = 0
        track = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
        if len(track) == 1: track_id = track[0].get_id()
        status_list.append(f"ID{track_id}:{col_code}")

    if elapsed_since_print >= 0.5:
        frames_since_last_print = user_data.get_count() - user_data.frame_count_at_last_print
        fps = int(frames_since_last_print / elapsed_since_print)
        report_str = " | ".join(detection_reports) if detection_reports else "Clear"
        print(f"FPS:{fps} | {report_str} || Status: {status_list}")
        
        user_data.last_print_time = current_time
        user_data.frame_count_at_last_print = user_data.get_count()

    # ---------------------------------------------------------
    # DRAWING LOGIC (Show lines on the screen)
    # ---------------------------------------------------------
    # IMPORTANT: user_data.use_frame must be True (enabled by --use-frame flag)
    if user_data.use_frame and format is not None:
        frame = get_numpy_from_buffer(buffer, format, width, height)
        if frame is not None:
            # Convert RGB to BGR for OpenCV
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # Draw Column Dividers (Thickened to 2 for visibility)
            cv_width = frame.shape[1]
            cv_height = frame.shape[0]
            line1_x = int(cv_width * 0.33)
            line2_x = int(cv_width * 0.66)
            
            # Draw Lines (Color: Green, Thickness: 2)
            cv2.line(frame, (line1_x, 0), (line1_x, cv_height), (0, 255, 0), 2)
            cv2.line(frame, (line2_x, 0), (line2_x, cv_height), (0, 255, 0), 2)
            
            # Add text labels on the screen
            cv2.putText(frame, "RIGHT", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, "CENTER", (line1_x + 20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, "LEFT", (line2_x + 20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # This pushes our drawn frame back to the Hailo display window
            user_data.set_frame(frame)

    return Gst.PadProbeReturn.OK

# -----------------------------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------------------------
def main():
    HEF_PATH = "/home/raspberrypi/hailo-rpi5-examples/resources/models/hailo8/yolov8m.hef"
    VIDEO_PATH = "usb" 

    if not os.path.exists(HEF_PATH):
        print(f"Error: HEF file not found at {HEF_PATH}")
        return
    
    # -----------------------------------------------------------
    # CRITICAL: We added "--use-frame" to enable OpenCV drawing
    # We added "--disable-sync" to keep the video smooth
    # -----------------------------------------------------------
    sys.argv = [
        sys.argv[0],
        "--input", VIDEO_PATH,
        "--hef-path", HEF_PATH,
        "--use-frame",      # Enables Python processing/drawing
        "--disable-sync"    # Improves display speed for USB cameras
    ]

    print("Starting Triple Column Detection with Visual Lines...")
    user_data = user_app_callback_class()
    app = GStreamerDetectionApp(app_callback, user_data)
    app.run()

if __name__ == "__main__":
    main()