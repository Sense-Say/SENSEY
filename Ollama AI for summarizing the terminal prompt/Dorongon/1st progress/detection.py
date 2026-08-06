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
    # COLUMN LOGIC & TERMINAL PRINTING
    # ---------------------------------------------------------
    current_time = time.time()
    elapsed_since_print = current_time - user_data.last_print_time

    # We process the descriptions every frame to draw, but only print every 0.5s
    detection_reports = []
    
    for detection in detections:
        label = detection.get_label()
        bbox = detection.get_bbox()
        
        # Calculate horizontal midpoint (normalized 0.0 to 1.0)
        # Using the midpoint ensures the "majority area" rule (if midpoint is in col, >50% is in col)
        mid_x = (bbox.xmin() + bbox.xmax()) / 2
        
        if mid_x < 0.33:
            column = "left"
        elif mid_x < 0.66:
            column = "center"
        else:
            column = "right"
            
        detection_reports.append(f"{label} on {column}")

    # Terminal Output every 0.5 seconds
    if elapsed_since_print >= 0.5:
        frames_since_last_print = user_data.get_count() - user_data.frame_count_at_last_print
        fps = int(frames_since_last_print / elapsed_since_print)

        # Format: FPS:15 | Person on left | Chair on center || Status: [...]
        report_str = " | ".join(detection_reports) if detection_reports else "Clear"
        
        # Short Status Codes (ID:ColumnIndex) - L=Left, C=Center, R=Right
        status_list = []
        for detection in detections:
            track_id = 0
            track = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
            if len(track) == 1: track_id = track[0].get_id()
            
            # Map column to a single letter for Status list
            mid_x = (detection.get_bbox().xmin() + detection.get_bbox().xmax()) / 2
            col_code = "L" if mid_x < 0.33 else "C" if mid_x < 0.66 else "R"
            status_list.append(f"ID{track_id}:{col_code}")

        print(f"FPS:{fps} | {report_str} || Status: {status_list}")

        # Reset timers
        user_data.last_print_time = current_time
        user_data.frame_count_at_last_print = user_data.get_count()

    # ---------------------------------------------------------
    # DRAWING LOGIC
    # ---------------------------------------------------------
    if user_data.use_frame and format is not None:
        frame = get_numpy_from_buffer(buffer, format, width, height)
        if frame is not None:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # Draw Column Dividers (2 Vertical Lines)
            cv2.line(frame, (int(width * 0.33), 0), (int(width * 0.33), height), (255, 255, 255), 1)
            cv2.line(frame, (int(width * 0.66), 0), (int(width * 0.66), height), (255, 255, 255), 1)
            
            # Add Column Labels
            cv2.putText(frame, "LEFT", (10, height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, "CENTER", (int(width * 0.45), height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, "RIGHT", (int(width * 0.85), height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

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
    # UPDATED ARGUMENTS to reduce QoS warnings
    # -----------------------------------------------------------
    sys.argv = [
        sys.argv[0],
        "--input", VIDEO_PATH,
        "--hef-path", HEF_PATH,
       # "--use-frame",
        "--disable-sync",
        "--frame-rate", "10"  # Force a steady 30 FPS to reduce QoS messages
    ]

    print("Starting Triple Column Detection...")
    user_data = user_app_callback_class()
    app = GStreamerDetectionApp(app_callback, user_data)
    app.run()

if __name__ == "__main__":
    main()