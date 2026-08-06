import cv2
import depthai as dai
import numpy as np
import os
import sys
import time
import subprocess

# --- 1. ENVIRONMENT SETUP ---
# Global env definition so it is accessible in main()
env = os.environ.copy()
env["QT_QPA_PLATFORM"] = "xcb"
env["DISPLAY"] = ":0"
env["HAILO_SCHEDULER"] = "1"

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
    cam = pipeline.create(dai.node.ColorCamera)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam.setInterleaved(False)
    cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.RGB) # AI needs RGB
    cam.setFps(30)
    cam.setPreviewSize(640, 640)
    cam.initialControl.setManualFocus(200)

    stereo = pipeline.create(dai.node.StereoDepth)
    left, right = pipeline.create(dai.node.MonoCamera), pipeline.create(dai.node.MonoCamera)
    left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P); left.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P); right.setBoardSocket(dai.CameraBoardSocket.CAM_C)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    stereo.setOutputSize(1920, 1080) 

    face_nn = pipeline.create(dai.node.MobileNetDetectionNetwork); face_nn.setBlobPath(FACE_BLOB); face_nn.setConfidenceThreshold(0.5)
    manip = pipeline.create(dai.node.ImageManip); manip.initialConfig.setResize(300, 300); manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888p); manip.setMaxOutputFrameSize(1300000)

    x_isp, x_dep, x_face = [pipeline.create(dai.node.XLinkOut) for _ in range(3)]
    x_isp.setStreamName("isp"); x_dep.setStreamName("depth"); x_face.setStreamName("face")

    left.out.link(stereo.left); right.out.link(stereo.right)
    cam.isp.link(x_isp.input); cam.preview.link(manip.inputImage); manip.out.link(face_nn.input); face_nn.out.link(x_face.input); stereo.depth.link(x_dep.input)
    return pipeline

def run_pose_monitor():
    print("\n🔵 Starting Full-FOV 1080p Monitor Loop...")
    target = VDevice(); hef = HEF(HEF_PATH)
    group = target.configure(hef, ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe))[0]
    in_params = InputVStreamParams.make(group, format_type=FormatType.UINT8) 
    out_params = OutputVStreamParams.make(group, format_type=FormatType.FLOAT32)
    in_name = hef.get_input_vstream_infos()[0].name
    post_proc = PoseEstPostProcessing(max_detections=15)

    with dai.Device(create_pipeline()) as device:
        calib = device.readCalibration()
        intr = calib.getCameraIntrinsics(dai.CameraBoardSocket.CAM_A, 1920, 1080)
        math_helpers = [intr[0][0], intr[1][1], intr[0][2], intr[1][2]]
        q_isp, q_dep, q_face = device.getOutputQueue("isp", 1, False), device.getOutputQueue("depth", 1, False), device.getOutputQueue("face", 1, False)

        with group.activate():
            with InferVStreams(group, in_params, out_params) as pipe:
                print("🚀 System Live.")
                while True:
                    f_rgb = q_isp.get().getCvFrame() # 1080p RGB
                    f_dep = q_dep.get().getFrame()   
                    f_faces = q_face.tryGet().detections if q_face.has() else None

                    input_data = {in_name: np.expand_dims(np.ascontiguousarray(cv2.resize(f_rgb, (640, 640))), axis=0)}
                    
                    try:
                        parsed = post_proc.post_process(pipe.infer(input_data), 640, 640, 1)

                        # 🚀 COLOR FIX: Convert RGB to BGR before drawing
                        bgr_display_frame = cv2.cvtColor(f_rgb, cv2.COLOR_RGB2BGR)

                        output = post_proc.visualize_pose_estimation_result(
                            parsed, bgr_display_frame, 640, 640, depth_map=f_dep, intrinsics=math_helpers, vpu_faces=f_faces
                        )

                        if isinstance(output, str):
                            cv2.destroyAllWindows(); return output

                        # Resize 1080p to 720p for the screen window
                        cv2.imshow("SENSEY Intelligent 3D Monitor", cv2.resize(output, (1280, 720)))
                    except Exception as e: print(f"⚠️ Error: {e}")
                    if cv2.waitKey(1) == ord('q'): return "QUIT"

def main():
    if os.path.exists(TRIGGER_FILE): os.remove(TRIGGER_FILE)
    while True:
        status = run_pose_monitor()
        if status == "QUIT": break
        if status == "TRIGGERED":
            if os.path.exists(TRIGGER_FILE): os.remove(TRIGGER_FILE)
            print("🔴 TRIGGER DETECTED! Running CPU Face Processor...")
            # 🚀 FIXED: env is now globally defined
            subprocess.run([PYTHON_EXE, SNAP_SCRIPT], env=env)
            with open("/home/raspberrypi/Documents/just_scanned.flag", "w") as f: f.write("true")
            time.sleep(1)

if __name__ == "__main__":
    main()