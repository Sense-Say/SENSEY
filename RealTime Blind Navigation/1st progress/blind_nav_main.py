import cv2
import depthai as dai
import numpy as np
import os
import sys
import time
import queue
import threading

os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"
os.environ["HAILO_SCHEDULER"] = "1"

from hailo_platform import (HEF, VDevice, InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams, FormatType, HailoStreamInterface)
from yolo_utils import YoloPostProcessing
from audio_announcer import SpatialAudioAnnouncer, speak, audio_queue

# --- CONFIGURATION ---
HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m.hef"

def letterbox(img, new_shape=(640, 640), color=(114, 114, 114)):
    """Pads image to 1:1 ratio for NPU without squashing."""
    shape = img.shape[:2] 
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    new_unpad = (int(round(shape[1] * r)), int(round(shape[0] * r)))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    dw /= 2; dh /= 2
    if shape[::-1] != new_unpad: img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    return cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)

def create_pipeline():
    pipeline = dai.Pipeline()
    
    # 1. Color Camera Node
    cam = pipeline.create(dai.node.ColorCamera)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam.setPreviewSize(640, 640) 
    cam.setInterleaved(False)
    cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    cam.setFps(20)
    cam.initialControl.setManualFocus(0)

    # 2. Mono Camera Nodes
    mono_left = pipeline.create(dai.node.MonoCamera)
    mono_right = pipeline.create(dai.node.MonoCamera)
    mono_left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
    mono_left.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    mono_right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
    mono_right.setBoardSocket(dai.CameraBoardSocket.CAM_C)

    # 3. Stereo Depth Node
    stereo = pipeline.create(dai.node.StereoDepth)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A) # Align depth to RGB frame
    stereo.setOutputSize(1920, 1080)                 # Match output size to 1080p RGB

    # Linking
    mono_left.out.link(stereo.left)
    mono_right.out.link(stereo.right)

    # Outputs
    x_isp = pipeline.create(dai.node.XLinkOut)
    x_isp.setStreamName("isp")
    cam.isp.link(x_isp.input) 

    x_dep = pipeline.create(dai.node.XLinkOut)
    x_dep.setStreamName("depth")
    stereo.depth.link(x_dep.input)

    return pipeline

def main():
    print("\n🟢 Starting Blind Navigation - Phase 3 (Speech Census)...")
    
    try:
        target = VDevice()
        hef = HEF(HEF_PATH)
        conf = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
        group = target.configure(hef, conf)[0]
        in_params = InputVStreamParams.make(group, format_type=FormatType.UINT8) 
        out_params = OutputVStreamParams.make(group, format_type=FormatType.FLOAT32)
        in_name = hef.get_input_vstream_infos()[0].name
    except Exception as e:
        print(f"❌ NPU Init Error: {e}")
        return

    # Initialize YOLO Parser with sensitive 30% threshold
    yolo_parser = YoloPostProcessing(score_threshold=0.30, model_type="yolov8")
    
    # Initialize Spatial Audio Announcer
    announcer = SpatialAudioAnnouncer()
    prev_time = time.time()

    with dai.Device(create_pipeline()) as device:
        q_isp = device.getOutputQueue("isp", 1, False)
        q_dep = device.getOutputQueue("depth", 1, False)

        with group.activate():
            with InferVStreams(group, in_params, out_params) as pipe:
                print("🚀 Navigation System Live.")
                
                # Speak system initialization
                speak("Navigation system online. Safe path finding active.")
                
                while True:
                    f_bgr = q_isp.get().getCvFrame() 
                    f_dep = q_dep.get().getFrame()  # Pull 16-bit depth frame

                    # Pad for YOLO
                    hailo_img = letterbox(f_bgr, (640, 640))
                    hailo_img = cv2.cvtColor(hailo_img, cv2.COLOR_BGR2RGB)

                    # Infer on Hailo
                    raw_res = pipe.infer({in_name: np.expand_dims(np.ascontiguousarray(hailo_img), axis=0)})
                    
                    # Parse and Fuse Depth Map
                    output_image, objects = yolo_parser.process_and_draw(raw_res, f_bgr, depth_map=f_dep)

                    # Extract floor walkable status from depth map
                    paths = yolo_parser.check_walkable_paths(f_dep)

                    # 🚀 Pass the actual width (f_bgr.shape[1] = 1920) for exact bounding box scale checks
                    announcer.update(objects, paths, img_w=f_bgr.shape[1])

                    # Calculate and draw FPS on HUD
                    fps = 1 / (time.time() - prev_time)
                    prev_time = time.time()
                    cv2.putText(output_image, f"FPS: {fps:.1f}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2, cv2.LINE_AA)

                    cv2.imshow("Blind Navigation Camera", cv2.resize(output_image, (960, 720)))
                    
                    if cv2.waitKey(1) == ord('q'): 
                        break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()