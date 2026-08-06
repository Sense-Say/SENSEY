import cv2
import depthai as dai
import numpy as np
import os
import sys
import time
import subprocess
import threading

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
FACE_BLOB = "/home/raspberrypi/TTS-STT-AUDIO/fast_face.blob" 
SNAP_SCRIPT = "/home/raspberrypi/Student Monitoring/cpu_process_screenshot.py"
PYTHON_EXE = sys.executable

PIPER_EXE = "/home/raspberrypi/TTS-STT-AUDIO/piper/piper" 
# 2. Point to the model in the new folder
PIPER_MODEL = "/home/raspberrypi/TTS-STT-AUDIO/en_US-lessac-medium.onnx"

def create_pipeline():
    pipeline = dai.Pipeline()

    # 1. RGB Camera (12MP 4:3 for MAX VFOV)
    cam = pipeline.create(dai.node.ColorCamera)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_12_MP)
    cam.setIspScale(1, 3) # Resizes 4032x3040 -> 1344x1008
    cam.setPreviewSize(640, 640) 
    cam.setInterleaved(False)
    cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.RGB)
    cam.setFps(20) # 🚀 Balanced FPS for stability and heat
    cam.initialControl.setManualFocus(0)

    # 2. Stereo Depth
    stereo = pipeline.create(dai.node.StereoDepth)
    left = pipeline.create(dai.node.MonoCamera)
    right = pipeline.create(dai.node.MonoCamera)
    # Use newer CAM sockets to avoid deprecation warnings
    left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P); left.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P); right.setBoardSocket(dai.CameraBoardSocket.CAM_C)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    stereo.setOutputSize(1344, 1008) 

    # 3. Face Detection (VPU)
    face_nn = pipeline.create(dai.node.MobileNetDetectionNetwork); face_nn.setBlobPath(FACE_BLOB); face_nn.setConfidenceThreshold(0.5)
    face_nn.setNumInferenceThreads(1)
    manip = pipeline.create(dai.node.ImageManip); manip.initialConfig.setResize(300, 300); manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888p); manip.setMaxOutputFrameSize(1300000)

    # 4. Output Nodes
    x_isp = pipeline.create(dai.node.XLinkOut); x_isp.setStreamName("isp")
    x_dep = pipeline.create(dai.node.XLinkOut); x_dep.setStreamName("depth")
    x_face = pipeline.create(dai.node.XLinkOut); x_face.setStreamName("face")

    left.out.link(stereo.left); right.out.link(stereo.right)
    cam.isp.link(x_isp.input) # 🚀 Full 4:3 View for display
    cam.preview.link(manip.inputImage); manip.out.link(face_nn.input); face_nn.out.link(x_face.input)
    stereo.depth.link(x_dep.input)
    return pipeline


def run_pose_monitor():
    # Setup Piper Command for initial ready message
    PIPER_CMD = f'echo "System ready. Press Button to Monitor Student Behavior" | {PIPER_EXE} --model {PIPER_MODEL} --length_scale 1.5 --output-raw | aplay -r 22050 -f S16_LE -t raw'
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
        print(f"❌ NPU Init Error: {e}"); return

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
                subprocess.Popen(PIPER_CMD, shell=True)
                while True:
                    f_rgb = q_isp.get().getCvFrame() 
                    f_dep = q_dep.get().getFrame()
                    face_packet = q_face.tryGet()
                    f_faces = face_packet.detections if face_packet else None

                    # Squeeze for NPU
                    hailo_input = cv2.resize(f_rgb, (640, 640))
                    
                    try:
                        raw_res = pipe.infer({in_name: np.expand_dims(np.ascontiguousarray(hailo_input), axis=0)})
                        parsed = post_proc.post_process(raw_res, 640, 640, 1)

                        key = cv2.waitKey(1) & 0xFF
                        bgr_frame = cv2.cvtColor(f_rgb, cv2.COLOR_RGB2BGR)

                        # Visualize
                        output = post_proc.visualize_pose_estimation_result(
                            parsed, bgr_frame, 640, 640, depth_map=f_dep, intrinsics=math_helpers, vpu_faces=f_faces, key_pressed=key
                        )

                        # 🚀 THE FIX: Check if output is a String (Flag) or an Array (Image)
                        if isinstance(output, str):
                            if output == "TRIGGERED":
                                print("📸 Snapshot! Processing in background...")
                                # Start Face Recognition in background thread
                                def handle_recognition():
                                    subprocess.run([PYTHON_EXE, SNAP_SCRIPT], env=env)
                                    # Create flag to trigger audio report in the next loop
                                    with open("/home/raspberrypi/Student Monitoring/just_scanned.flag", "w") as f:
                                        f.write("true")
                                threading.Thread(target=handle_recognition, daemon=True).start()
                                continue
                            elif output == "QUIT":
                                break
                        else:
                            # If it's the image array, show it
                            cv2.imshow("SENSEY 3D Monitor", cv2.resize(output, (1024, 768)))
                        
                    except Exception as e:
                        print(f"⚠️ Error: {e}")

                    if key == ord('q'): break
    cv2.destroyAllWindows()

def main():
    # Simplifed main: Hardware starts once, no more while loop restarts
    run_pose_monitor()
    print("🏁 System Shutdown.")

if __name__ == "__main__":
    main()