import cv2
import depthai as dai
import numpy as np
import os
import sys
import time

# --- ENVIRONMENT ---
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"
os.environ["HAILO_SCHEDULER"] = "1"

from hailo_platform import (HEF, VDevice, InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams, FormatType, HailoStreamInterface)

# Add paths
sys.path.append("/home/raspberrypi/hailo-apps/hailo_apps/python/standalone_apps/pose_estimation")
from pose_estimation_utils import PoseEstPostProcessing

HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m_pose.hef"
FACE_BLOB = "/home/raspberrypi/Documents/face_detector.blob"

def create_pipeline():
    pipeline = dai.Pipeline()

    # 1. RGB Camera
    cam = pipeline.create(dai.node.ColorCamera)
    cam.setPreviewSize(640, 640)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam.setInterleaved(False)
    # 🚀 FIX: Hailo expects RGB input, so let's have OAK-D output RGB directly
    cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.RGB) 
    cam.initialControl.setManualFocus(0) # Infinity lock

    # 2. Stereo Depth
    stereo = pipeline.create(dai.node.StereoDepth)
    left = pipeline.create(dai.node.MonoCamera)
    right = pipeline.create(dai.node.MonoCamera)
    
    left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
    left.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
    right.setBoardSocket(dai.CameraBoardSocket.CAM_C)
    
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)

    # 3. Face Detection NN (VPU)
    face_nn = pipeline.create(dai.node.MobileNetDetectionNetwork)
    face_nn.setBlobPath(FACE_BLOB)
    face_nn.setConfidenceThreshold(0.5)
    
    manip = pipeline.create(dai.node.ImageManip)
    manip.initialConfig.setResize(300, 300)
    # The face detector might expect BGR, so we keep the manip output BGR
    manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888p)

    # 4. Output Nodes
    x_rgb = pipeline.create(dai.node.XLinkOut)
    x_dep = pipeline.create(dai.node.XLinkOut)
    x_face = pipeline.create(dai.node.XLinkOut)
    
    x_rgb.setStreamName("rgb")
    x_dep.setStreamName("depth")
    x_face.setStreamName("face")

    # 5. Linking
    left.out.link(stereo.left)
    right.out.link(stereo.right)
    
    cam.preview.link(x_rgb.input)
    cam.preview.link(manip.inputImage) 
    manip.out.link(face_nn.input)      
    
    face_nn.out.link(x_face.input)
    stereo.depth.link(x_dep.input)

    return pipeline

def main():
    target = VDevice()
    hef = HEF(HEF_PATH)
    conf = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
    group = target.configure(hef, conf)[0]
    
    # 🚀 FIX: explicitly set the format types to match the expected NPU math
    in_params = InputVStreamParams.make(group, format_type=FormatType.UINT8) 
    out_params = OutputVStreamParams.make(group, format_type=FormatType.FLOAT32)
    in_name = hef.get_input_vstream_infos()[0].name

    post_proc = PoseEstPostProcessing(max_detections=15, score_threshold=0.3, nms_iou_thresh=0.45, regression_length=15, strides=[8, 16, 32])

    print("🚀 Fusing VPU (Faces), NPU (Pose), and 3D Depth...")
    with dai.Device(create_pipeline()) as device:
        calib = device.readCalibration()
        intr = calib.getCameraIntrinsics(dai.CameraBoardSocket.CAM_A, 640, 640)
        math_helpers = [intr[0][0], intr[1][1], intr[0][2], intr[1][2]]

        q_rgb = device.getOutputQueue("rgb", 1, False)
        q_dep = device.getOutputQueue("depth", 1, False)
        q_face = device.getOutputQueue("face", 1, False)

        with group.activate():
            with InferVStreams(group, in_params, out_params) as pipe:
                while True:
                    f_rgb = q_rgb.get().getCvFrame() # This is now RGB from the camera
                    f_dep = q_dep.get().getFrame()
                    f_faces = q_face.get().detections 

                    # 🚀 FIX: Ensure array is exactly the format the Hailo Python API wants
                    input_frame = np.expand_dims(f_rgb, axis=0)
                    input_data = {in_name: np.ascontiguousarray(input_frame)}
                    
                    try:
                        raw_res = pipe.infer(input_data)
                        parsed = post_proc.post_process(raw_res, 640, 640, 1)

                        # OpenCV imshow expects BGR, so we must convert the RGB frame back before drawing
                        bgr_display_frame = cv2.cvtColor(f_rgb, cv2.COLOR_RGB2BGR)

                        output = post_proc.visualize_pose_estimation_result(
                            parsed, bgr_display_frame, 640, 640, depth_map=f_dep, intrinsics=math_helpers, vpu_faces=f_faces
                        )

                        cv2.imshow("SENSEY 3D Monitor", output)
                    except Exception as e:
                        print(f"⚠️ Inference Error: {e}")

                    if cv2.waitKey(1) == ord('q'): break
    cv2.destroyAllWindows()

if __name__ == "__main__":

    main()