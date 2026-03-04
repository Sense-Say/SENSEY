import cv2
import depthai as dai
import numpy as np
import os
import sys
import time
import subprocess

# --- 1. ENVIRONMENT SETUP ---
env = os.environ.copy()
env["QT_QPA_PLATFORM"] = "xcb"
env["DISPLAY"] = ":0"
env["HAILO_SCHEDULER"] = "1"
for key, value in env.items():
    os.environ[key] = value

from hailo_platform import (HEF, VDevice, InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams, FormatType, HailoStreamInterface)
sys.path.append("/home/raspberrypi/hailo-apps/hailo_apps/python/standalone_apps/pose_estimation")
from pose_estimation_utils import PoseEstPostProcessing

# --- 2. CONFIGURATION ---
HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m_pose.hef"
FACE_BLOB = "/home/raspberrypi/Documents/fast_face.blob"
SNAP_SCRIPT = "/home/raspberrypi/Documents/cpu_process_screenshot.py"
TRIGGER_FILE = "/home/raspberrypi/Documents/trigger.txt"
PYTHON_EXE = sys.executable

def create_pipeline():
    pipeline = dai.Pipeline()

    # 1. RGB Camera (12MP 4:3 for MAX VFOV)
    cam = pipeline.create(dai.node.ColorCamera)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_12_MP)
    cam.setIspScale(1, 3) # Resizes 4032x3040 -> 1344x1008
    cam.setPreviewSize(640, 640) # Hailo Square Input
    cam.setInterleaved(False)
    cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.RGB) # Hailo needs RGB
    cam.setFps(15)
    cam.initialControl.setManualFocus(0) # Infinity lock

    # 2. Stereo Depth (Synchronized to 1344x1008)
    stereo = pipeline.create(dai.node.StereoDepth)
    left = pipeline.create(dai.node.MonoCamera)
    right = pipeline.create(dai.node.MonoCamera)
    left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P); left.setBoardSocket(dai.CameraBoardSocket.LEFT)
    right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P); right.setBoardSocket(dai.CameraBoardSocket.RIGHT)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    stereo.setOutputSize(1344, 1008) 

    # 3. Face Detection (VPU Throttled for cooling)
    face_nn = pipeline.create(dai.node.MobileNetDetectionNetwork); face_nn.setBlobPath(FACE_BLOB); face_nn.setConfidenceThreshold(0.5)
    face_nn.setNumInferenceThreads(1)
    manip = pipeline.create(dai.node.ImageManip); manip.initialConfig.setResize(300, 300); manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888p); manip.setMaxOutputFrameSize(1300000)

    # 4. Output Nodes
    x_isp = pipeline.create(dai.node.XLinkOut); x_isp.setStreamName("isp")
    x_dep = pipeline.create(dai.node.XLinkOut); x_dep.setStreamName("depth")
    x_face = pipeline.create(dai.node.XLinkOut); x_face.setStreamName("face")

    left.out.link(stereo.left); right.out.link(stereo.right)
    cam.isp.link(x_isp.input)
    cam.preview.link(manip.inputImage); manip.out.link(face_nn.input); face_nn.out.link(x_face.input)
    stereo.depth.link(x_dep.input)
    return pipeline

def run_pose_monitor():
    print("\n🔵 Starting Widescreen 4:3 Monitor Loop...")
    try:
        target = VDevice()
        hef = HEF(HEF_PATH)
        conf = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
        group = target.configure(hef, conf)[0]
        in_params = InputVStreamParams.make(group, format_type=FormatType.UINT8) 
        out_params = OutputVStreamParams.make(group, format_type=FormatType.FLOAT32)
        in_name = hef.get_input_vstream_infos()[0].name
    except Exception as e:
        print(f"❌ NPU Init Error: {e}"); return "ERROR"

    post_proc = PoseEstPostProcessing(max_detections=15)

    with dai.Device(create_pipeline()) as device:
        calib = device.readCalibration()
        intr = calib.getCameraIntrinsics(dai.CameraBoardSocket.CAM_A, 1344, 1008)
        math_helpers = [intr[0][0], intr[1][1], intr[0][2], intr[1][2]]

        q_isp = device.getOutputQueue("isp", 1, False)
        q_dep = device.getOutputQueue("depth", 1, False)
        q_face = device.getOutputQueue("face", 1, False)

        with group.activate():
            with InferVStreams(group, in_params, out_params) as pipe:
                print("🚀 System Live.")
                while True:
                    f_rgb = q_isp.get().getCvFrame() # 1344x1008 RGB
                    f_dep = q_dep.get().getFrame()
                    face_packet = q_face.tryGet()
                    f_faces = face_packet.detections if face_packet else None

                    # Squeeze for Hailo (1344x1008 -> 640x640)
                    hailo_input = cv2.resize(f_rgb, (640, 640))
                    
                    try:
                        raw_res = pipe.infer({in_name: np.expand_dims(np.ascontiguousarray(hailo_input), axis=0)})
                        parsed = post_proc.post_process(raw_res, 640, 640, 1)

                        # Capture Keyboard input ONCE here
                        key = cv2.waitKey(1) & 0xFF

                        # OpenCV imshow expects BGR, so we must convert the RGB frame back before drawing
                        bgr_display_frame = cv2.cvtColor(f_rgb, cv2.COLOR_RGB2BGR)

                        # Visualize on the TALL 4:3 frame
                        output = post_proc.visualize_pose_estimation_result(
                            parsed, bgr_display_frame, 640, 640, depth_map=f_dep, intrinsics=math_helpers, vpu_faces=f_faces, key_pressed=key
                        )

                        if isinstance(output, str):
                            if output == "TRIGGERED" or output == "QUIT":
                                cv2.destroyAllWindows(); return output
                        
                        # Display (resized for screen fit)
                        cv2.imshow("SENSEY 3D Monitor", cv2.resize(output, (1024, 768)))
                        
                    except Exception as e:
                        print(f"⚠️ Error: {e}")

                    if key == ord('q'): return "QUIT"

def main():
    if os.path.exists(TRIGGER_FILE): os.remove(TRIGGER_FILE)
    while True:
        status = run_pose_monitor()
        if status == "QUIT" or status == "ERROR": break
        if status == "TRIGGERED":
            if os.path.exists(TRIGGER_FILE): os.remove(TRIGGER_FILE)
            print("⏳ COOLING NPU/VPU (2s Handover)...")
            time.sleep(2)
            subprocess.run([PYTHON_EXE, SNAP_SCRIPT], env=env)
            with open("/home/raspberrypi/Documents/just_scanned.flag", "w") as f: f.write("true")
            time.sleep(1)

if __name__ == "__main__":
    main()