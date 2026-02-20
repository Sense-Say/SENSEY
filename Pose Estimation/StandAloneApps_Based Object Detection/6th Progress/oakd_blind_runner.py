import cv2
import depthai as dai
import numpy as np
import sys, os, time, math
from hailo_platform import HEF, VDevice, HailoStreamInterface, InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams, FormatType

# --- SETUP PATHS ---
sys.path.append("/home/raspberrypi/hailo-apps")
from hailo_apps.python.standalone_apps.object_detection.object_detection_post_process import inference_result_handler

# --- CONFIGURATION ---
HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m.hef"
LABELS = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"]
CONFIG_DATA = {"visualization_params": {"score_thres": 0.5, "max_boxes_to_draw": 50}}

# VIO SETTINGS
MIN_Z_DELTA, MAX_Z_DELTA = 0.01, 0.30

def letterbox_image(image, size):
    shape = image.shape
    ih, iw = shape[0], shape[1]
    scale = min(size/iw, size/ih)
    nw, nh = int(iw * scale), int(ih * scale)
    image_resized = cv2.resize(image, (nw, nh))
    if len(shape) == 3:
        new_image = np.zeros((size, size, shape[2]), dtype=image.dtype)
        new_image[(size-nh)//2:(size-nh)//2+nh, (size-nw)//2:(size-nw)//2+nw, :] = image_resized
    else:
        new_image = np.zeros((size, size), dtype=image.dtype)
        new_image[(size-nh)//2:(size-nh)//2+nh, (size-nw)//2:(size-nw)//2+nw] = image_resized
    return new_image

def get_pipeline():
    pipeline = dai.Pipeline()
    
    # 1. RGB
    cam = pipeline.create(dai.node.ColorCamera)
    cam.setPreviewSize(640, 480)
    cam.setBoardSocket(dai.CameraBoardSocket.CAM_A)
    cam.setInterleaved(False)
    cam.initialControl.setManualFocus(10)

    # 2. Depth + Mono
    left = pipeline.create(dai.node.MonoCamera)
    left.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    
    right = pipeline.create(dai.node.MonoCamera)
    right.setBoardSocket(dai.CameraBoardSocket.CAM_C)
    right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    
    stereo = pipeline.create(dai.node.StereoDepth)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    left.out.link(stereo.left); right.out.link(stereo.right)

    # 3. IMU (Heading)
    imu = pipeline.create(dai.node.IMU)
    imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 100)
    
    # 4. Feature Tracker (Distance)
    feat = pipeline.create(dai.node.FeatureTracker)
    left.out.link(feat.inputImage)

    # Outputs
    x_rgb = pipeline.create(dai.node.XLinkOut); x_rgb.setStreamName("rgb"); cam.preview.link(x_rgb.input)
    x_dep = pipeline.create(dai.node.XLinkOut); x_dep.setStreamName("depth"); stereo.depth.link(x_dep.input)
    x_imu = pipeline.create(dai.node.XLinkOut); x_imu.setStreamName("imu"); imu.out.link(x_imu.input)
    x_fea = pipeline.create(dai.node.XLinkOut); x_fea.setStreamName("feat"); feat.outputFeatures.link(x_fea.input)
    
    return pipeline

def run():
    # Init NPU
    target = VDevice()
    hef = HEF(HEF_PATH)
    conf = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
    group = target.configure(hef, conf)[0]
    in_p = InputVStreamParams.make(group, format_type=FormatType.FLOAT32)
    out_p = OutputVStreamParams.make(group, format_type=FormatType.FLOAT32)
    input_name = hef.get_input_vstream_infos()[0].name

    # VIO Variables
    total_dist, current_yaw, last_imu_t = 0.0, 0.0, None
    feat_history = {}

    with dai.Device(get_pipeline()) as device:
        q_rgb = device.getOutputQueue("rgb", 4, False)
        q_dep = device.getOutputQueue("depth", 4, False)
        q_imu = device.getOutputQueue("imu", 10, False)
        q_fea = device.getOutputQueue("feat", 4, False)

        with group.activate():
            with InferVStreams(group, in_p, out_p) as pipe:
                while True:
                    # 1. Update Yaw (IMU)
                    imuData = q_imu.tryGet()
                    if imuData:
                        for packet in imuData.packets:
                            gyro = packet.gyroscope
                            ts = time.time()
                            if last_imu_t:
                                current_yaw += gyro.z * (180/math.pi) * (ts - last_imu_t)
                            last_imu_t = ts

                    # 2. Get Visual Frames
                    rgb_in = q_rgb.get(); dep_in = q_dep.get(); fea_in = q_fea.get()
                    frame = rgb_in.getCvFrame(); depth = dep_in.getFrame(); features = fea_in.trackedFeatures
                    
                    # 3. Calculate Pedometer (Distance)
                    deltas = []
                    for f in features:
                        x, y = int(f.position.x), int(f.position.y)
                        if 0 <= y < depth.shape[0] and 0 <= x < depth.shape[1]:
                            z = depth[y, x] / 1000.0
                            if z > 0 and f.id in feat_history:
                                d_z = feat_history[f.id] - z
                                if MIN_Z_DELTA < abs(d_z) < MAX_Z_DELTA: deltas.append(d_z)
                            feat_history[f.id] = z
                    if deltas: total_dist += sum(deltas)/len(deltas)

                    # 4. Hailo Inference
                    padded = letterbox_image(frame, 640)
                    f_in = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB).astype(np.float32)
                    res = pipe.infer({input_name: np.expand_dims(f_in, axis=0)})
                    raw_dets = list(res.values())[0][0]

                    # 5. Draw Everything
                    processed = inference_result_handler(
                        padded, raw_dets, LABELS, CONFIG_DATA, 
                        vio_data=(total_dist, current_yaw % 360), 
                        depth_frame=letterbox_image(depth, 640)
                    )

                    cv2.imshow("SENSEY Blind Nav", processed)
                    if cv2.waitKey(1) == ord('q'): break

if __name__ == "__main__":
    run()