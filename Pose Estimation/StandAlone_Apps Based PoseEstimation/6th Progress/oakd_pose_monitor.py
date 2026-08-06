import cv2
import depthai as dai
import numpy as np
import os
import sys
import time

# 1. FIX DISPLAY AND NPU STABILITY
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"
os.environ["HAILO_SCHEDULER"] = "1" 

from hailo_platform import HEF, VDevice, HailoStreamInterface, InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams, FormatType

# --- CONFIGURATION ---
HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m_pose.hef"
sys.path.append("/home/raspberrypi/hailo-apps/hailo_apps/python/standalone_apps/pose_estimation")
from pose_estimation_utils import PoseEstPostProcessing

def create_pipeline():
    pipeline = dai.Pipeline()

    cam_rgb = pipeline.create(dai.node.ColorCamera)
    mono_left = pipeline.create(dai.node.MonoCamera)
    mono_right = pipeline.create(dai.node.MonoCamera)
    stereo = pipeline.create(dai.node.StereoDepth)

    xout_rgb = pipeline.create(dai.node.XLinkOut)
    xout_depth = pipeline.create(dai.node.XLinkOut)

    xout_rgb.setStreamName("rgb")
    xout_depth.setStreamName("depth")

    cam_rgb.setPreviewSize(640, 640)
    cam_rgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam_rgb.setInterleaved(False)
    cam_rgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    cam_rgb.setFps(30)

    mono_left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    mono_left.setBoardSocket(dai.CameraBoardSocket.CAM_B) 
    mono_right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    mono_right.setBoardSocket(dai.CameraBoardSocket.CAM_C) 

    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
    stereo.setLeftRightCheck(True)
    stereo.setExtendedDisparity(False)
    stereo.setSubpixel(True)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)

    mono_left.out.link(stereo.left)
    mono_right.out.link(stereo.right)
    cam_rgb.preview.link(xout_rgb.input)
    stereo.depth.link(xout_depth.input)

    return pipeline

def main():
    print("🧠 Initializing Hailo NPU...")
    target = VDevice()
    hef = HEF(HEF_PATH)
    configure_params = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
    network_group = target.configure(hef, configure_params)[0]
    network_group_params = network_group.create_params()

    input_vstreams_params = InputVStreamParams.make(network_group, format_type=FormatType.FLOAT32)
    output_vstreams_params = OutputVStreamParams.make(network_group, format_type=FormatType.FLOAT32)

    post_proc = PoseEstPostProcessing(
        max_detections=20,
        score_threshold=0.3,
        nms_iou_thresh=0.45,
        regression_length=15,
        strides=[8, 16, 32]
    )

    print("📸 Initializing OAK-D Lite...")
    with dai.Device(create_pipeline()) as device:
        # Increase maxSize slightly to 2 for better sync
        q_rgb = device.getOutputQueue(name="rgb", maxSize=2, blocking=False)
        q_depth = device.getOutputQueue(name="depth", maxSize=2, blocking=False)

        input_name = hef.get_input_vstream_infos()[0].name
        print(f"✅ Setup Complete. Input Layer: {input_name}")

        with network_group.activate(network_group_params):
            with InferVStreams(network_group, input_vstreams_params, output_vstreams_params) as infer_pipeline:
                print("🚀 Loop Started. Looking for students...")
                while True:
                    # Use .get() to force the script to wait for data
                    in_rgb = q_rgb.get()
                    in_depth = q_depth.get()

                    frame = in_rgb.getCvFrame()
                    depth_frame = in_depth.getFrame()

                    input_frame = np.ascontiguousarray(frame)
                    input_data = {input_name: np.expand_dims(input_frame, axis=0).astype(np.float32)}
                    
                    try:
                        raw_results = infer_pipeline.infer(input_data)
                        
                        processed_results = post_proc.post_process(
                            raw_results, height=640, width=640, class_num=1
                        )

                        # Draw result
                        output_frame = post_proc.visualize_pose_estimation_result(
                            processed_results, frame, 640, 640, depth_map=depth_frame
                        )

                        cv2.imshow("SENSEY 3D Spatial Monitor", output_frame)
                    
                    except Exception as e:
                        print(f"Loop Error: {e}")

                    if cv2.waitKey(1) == ord('q'):
                        break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()