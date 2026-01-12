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
    # --- SOFT PAUSE CHECK ---
    # Check if Master Controller created the pause flag to save power for Ollama
    is_paused = os.path.exists("/tmp/hailo_pause")

    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK

    user_data.increment()
    
    # Get detections (We always do this so the Master Controller gets logs)
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

    # ---------------------------------------------------------
    # COLUMN LOGIC & TERMINAL PRINTING
    # ---------------------------------------------------------
    current_time = time.time()
    elapsed_since_print = current_time - user_data.last_print_time

    detection_reports = []
    for detection in detections:
        label = detection.get_label()
        bbox = detection.get_bbox()
        mid_x = (bbox.xmin() + bbox.xmax()) / 2
        
        if mid_x < 0.33:
            column = "left"
        elif mid_x < 0.66:
            column = "center"
        else:
            column = "right"
        detection_reports.append(f"{label} on {column}")

    # We MUST keep printing even if paused, so the Master Controller's 
    # Qwen AI can read the logs from the pipe.
    if elapsed_since_print >= 0.5:
        frames_since_last_print = user_data.get_count() - user_data.frame_count_at_last_print
        fps = int(frames_since_last_print / elapsed_since_print)
        report_str = " | ".join(detection_reports) if detection_reports else "Clear"
        
        status_list = []
        for detection in detections:
            track_id = 0
            track = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
            if len(track) == 1: track_id = track[0].get_id()
            mid_x = (detection.get_bbox().xmin() + detection.get_bbox().xmax()) / 2
            col_code = "L" if mid_x < 0.33 else "C" if mid_x < 0.66 else "R"
            status_list.append(f"ID{track_id}:{col_code}")

        print(f"FPS:{fps} | {report_str} || Status: {status_list}")

        user_data.last_print_time = current_time
        user_data.frame_count_at_last_print = user_data.get_count()

    # ---------------------------------------------------------
    # DRAWING LOGIC (POWER SAVING MODE)
    # ---------------------------------------------------------
    # If is_paused is True, we skip all OpenCV work to prevent PSU Low Voltage
    if user_data.use_frame and not is_paused:
        format, width, height = get_caps_from_pad(pad)
        if format is not None:
            frame = get_numpy_from_buffer(buffer, format, width, height)
            if frame is not None:
                # CPU HEAVY: Color conversion
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # CPU HEAVY: Drawing lines and text
                cv2.line(frame, (int(width * 0.33), 0), (int(width * 0.33), height), (255, 255, 255), 1)
                cv2.line(frame, (int(width * 0.66), 0), (int(width * 0.66), height), (255, 255, 255), 1)
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
    
    sys.argv = [
        sys.argv[0],
        "--input", VIDEO_PATH,
        "--hef-path", HEF_PATH,
        "--use-frame",    # Ensure this is on so we can control drawing
        "--disable-sync"
    ]

    print("Starting Triple Column Detection (With AI-Pause Support)...")
    user_data = user_app_callback_class()
    app = GStreamerDetectionApp(app_callback, user_data)
    app.run()

if __name__ == "__main__":
    main()