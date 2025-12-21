# region imports
import sys
import os

# 1. FIX DISPLAY FOR RPI 5
# This ensures the window opens correctly
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"

# Third-party imports
import gi
gi.require_version("Gst", "1.0")
import cv2

# Local application-specific imports
import hailo
from gi.repository import Gst

from hailo_apps.hailo_app_python.apps.detection.detection_pipeline import GStreamerDetectionApp
from hailo_apps.hailo_app_python.core.common.buffer_utils import (
    get_caps_from_pad,
    get_numpy_from_buffer,
)

# Logger
from hailo_apps.hailo_app_python.core.common.hailo_logger import get_logger
from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app import app_callback_class

hailo_logger = get_logger(__name__)
# endregion imports

# -----------------------------------------------------------------------------------------------
# User-defined class to be used in the callback function
# -----------------------------------------------------------------------------------------------
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        self.new_variable = 42 

    def new_function(self): 
        return "Status: "

# -----------------------------------------------------------------------------------------------
# User-defined callback function
# -----------------------------------------------------------------------------------------------
def app_callback(pad, info, user_data):
    # Get the GstBuffer
    buffer = info.get_buffer()
    if buffer is None:
        hailo_logger.warning("Received None buffer")
        return Gst.PadProbeReturn.OK

    user_data.increment()
    frame_idx = user_data.get_count()
    string_to_print = f"Frame count: {user_data.get_count()}\n"

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
        bbox = detection.get_bbox()
        confidence = detection.get_confidence()
        
        # You can change "person" to any object you want to detect
        if label == "person":
            track_id = 0
            track = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
            if len(track) == 1:
                track_id = track[0].get_id()
            
            string_to_print += (
                f"Detection: ID: {track_id} Label: {label} Confidence: {confidence:.2f}\n"
            )
            detection_count += 1

    # Drawing on frame
    if user_data.use_frame and frame is not None:
        # Convert to BGR for OpenCV
        try:
             # Fix color format if needed
            if format == "RGB":
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
            # Draw Count
            cv2.putText(
                frame,
                f"Persons: {detection_count}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )
            
            # Show the frame
            cv2.imshow("Hailo Detection", frame)
            cv2.waitKey(1)
            
        except Exception as e:
            print(f"Drawing Error: {e}")

   #f hailo_logger.info(string_to_print.strip())
    return Gst.PadProbeReturn.OK


def main():
    hailo_logger.info("Starting Hailo Detection App...")

    # -----------------------------------------------------------
    # HARDCODED ARGUMENTS
    # These replace the need to type flags in the terminal
    # -----------------------------------------------------------
    hardcoded_args = [
        "--input", "/home/raspberrypi/Downloads/WRITINGINTHEBOARD.MOV",  # Change to your video file path if needed
        "--hef-path", "/home/raspberrypi/hailo-apps-infra/resources/models/hailo8/yolov8m.hef", # Make sure this path is correct!
        "--show-fps",
      #  "--disable-sync" # Vital for correct playback speed
    ]
    
    # Inject arguments into sys.argv
    # sys.argv[0] is the script name, we append our args after it
    sys.argv = [sys.argv[0]] + hardcoded_args

    # Run App
    user_data = user_app_callback_class()
    app = GStreamerDetectionApp(app_callback, user_data)
    app.run()


if __name__ == "__main__":
    main()