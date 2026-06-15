import cv2
import depthai as dai
import numpy as np
import os
import sys
import time

# --- 1. ENVIRONMENT SETUP ---
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"
os.environ["HAILO_SCHEDULER"] = "1"

from hailo_platform import (HEF, VDevice, InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams, FormatType, HailoStreamInterface)
sys.path.append("/home/raspberrypi/hailo-apps/hailo_apps/python/standalone_apps/pose_estimation")

# 🚀 Import the class and the background queue helper
from pose_estimation_utils import PoseEstPostProcessing, speak

# --- 2. CONFIGURATION ---
HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m_pose.hef"
FACE_BLOB = "/home/raspberrypi/TTS-STT-AUDIO/fast_face.blob" 
PYTHON_EXE = sys.executable

def create_pipeline():
    pipeline = dai.Pipeline()

    # 1. RGB Camera (NATIVE 4:3 SETUP FOR MAX VFOV)
    cam = pipeline.create(dai.node.ColorCamera)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_12_MP)
    cam.setIspScale(1, 3) # Resizes 4032x3040 -> 1344x1008
    cam.setPreviewSize(640, 640) 
    cam.setInterleaved(False)
    
    # OUTPUT BGR (OpenCV Native Format)
    cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    cam.setFps(25)
    cam.initialControl.setManualFocus(0)

    # 2. Stereo Depth (Aligned to 4:3)
    stereo = pipeline.create(dai.node.StereoDepth)
    left = pipeline.create(dai.node.MonoCamera)
    right = pipeline.create(dai.node.MonoCamera)
    left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P); left.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P); right.setBoardSocket(dai.CameraBoardSocket.CAM_C)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    stereo.setOutputSize(1344, 1008) 

    # 3. Output Nodes
    x_isp = pipeline.create(dai.node.XLinkOut); x_isp.setStreamName("isp")
    x_dep = pipeline.create(dai.node.XLinkOut); x_dep.setStreamName("depth")

    # 4. Linking
    left.out.link(stereo.left); right.out.link(stereo.right)
    cam.isp.link(x_isp.input) # Full 4:3 View for display
    stereo.depth.link(x_dep.input)
    return pipeline

def run_pose_monitor():
    print("\n🔵 Starting Widescreen 4:3 Monitor Loop...")
    
    try:
        target = VDevice(); hef = HEF(HEF_PATH)
        conf = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
        group = target.configure(hef, conf)[0]
        in_params = InputVStreamParams.make(group, format_type=FormatType.UINT8) 
        out_params = OutputVStreamParams.make(group, format_type=FormatType.FLOAT32)
        in_name = hef.get_input_vstream_infos()[0].name
    except Exception as e:
        print(f"❌ NPU Init Error: {e}"); return

    post_proc = PoseEstPostProcessing(max_detections=15)

    with dai.Device(create_pipeline()) as device:
        calib = device.readCalibration()
        intr = calib.getCameraIntrinsics(dai.CameraBoardSocket.CAM_A, 1344, 1008)
        math_helpers = [intr[0][0], intr[1][1], intr[0][2], intr[1][2]]
        q_isp = device.getOutputQueue("isp", 1, False)
        q_dep = device.getOutputQueue("depth", 1, False)

        with group.activate():
            with InferVStreams(group, in_params, out_params) as pipe:
                print("🚀 System Live.")
                
                # 🚀 Use background Queue instead of legacy blocking Popen call
                speak("Classroom monitoring system is ready.")
                
                while True:
                    # 🚀 Fix UnboundLocalError: Define 'key' at the top of loop execution
                    key = 255 
                    
                    f_bgr = q_isp.get().getCvFrame() 
                    f_dep = q_dep.get().getFrame()

                    # Hailo expects RGB format
                    hailo_img = cv2.resize(f_bgr, (640, 640))
                    hailo_img = cv2.cvtColor(hailo_img, cv2.COLOR_BGR2RGB)
                    
                    # pose_estimation_utils expects an RGB image input
                    rgb_frame_for_utils = cv2.cvtColor(f_bgr, cv2.COLOR_BGR2RGB)

                    try:
                        raw_res = pipe.infer({in_name: np.expand_dims(np.ascontiguousarray(hailo_img), axis=0)})
                        parsed = post_proc.post_process(raw_res, 640, 640, 1)

                        key = cv2.waitKey(1) & 0xFF

                        # Visualize
                        output = post_proc.visualize_pose_estimation_result(
                            parsed, rgb_frame_for_utils, 640, 640, depth_map=f_dep, intrinsics=math_helpers, key_pressed=key
                        )

                        if isinstance(output, str):
                            if output == "QUIT": break
                        else:
                            cv2.imshow("SENSEY Intelligent 3D Monitor", cv2.resize(output, (1024, 768)))
                        
                    except Exception as e:
                        print(f"⚠️ Error: {e}")

                    if key == ord('q'): break
    cv2.destroyAllWindows()

def main():
    run_pose_monitor()
    print("🏁 System Shutdown.")

if __name__ == "__main__":
    time.sleep(1)
    main()