import cv2
import depthai as dai
import numpy as np
import sys
import os
import json
from hailo_platform import HEF, VDevice, HailoStreamInterface, InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams, FormatType

# --- IMPORT POST-PROCESS UTILS ---
sys.path.append("/home/raspberrypi/hailo-apps")
try:
    from hailo_apps.python.standalone_apps.object_detection.object_detection_post_process import inference_result_handler
except ImportError:
    print("❌ Error: Could not find object_detection_post_process.py")
    sys.exit(1)

# --- CONFIGURATION ---
# Fix display environment before OpenCV does anything
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"

HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m.hef"

LABELS = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone",
    "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush"
]

CONFIG_DATA = {
    "visualization_params": {
        "score_thres": 0.5,
        "max_boxes_to_draw": 50
    }
}

# --- HELPER: LETTERBOXING (FIXED) ---
def letterbox_image(image, size):
    """
    Pads the image with black bars to make it square (size x size).
    Handles both 3-channel (RGB) and 1-channel/2D (Depth) images safely.
    """
    shape = image.shape
    ih = shape[0]
    iw = shape[1]
    
    h, w = size, size
    scale = min(w/iw, h/ih)
    nw = int(iw * scale)
    nh = int(ih * scale)
    
    image_resized = cv2.resize(image, (nw, nh))
    
    # Check if the image has color channels (RGB) or is a 2D map (Depth)
    if len(shape) == 3:
        # RGB Image
        new_image = np.zeros((h, w, shape[2]), dtype=image.dtype)
        dy = (h - nh) // 2
        dx = (w - nw) // 2
        new_image[dy:dy+nh, dx:dx+nw, :] = image_resized
    else:
        # Depth Map (2D array)
        new_image = np.zeros((h, w), dtype=image.dtype)
        dy = (h - nh) // 2
        dx = (w - nw) // 2
        new_image[dy:dy+nh, dx:dx+nw] = image_resized
        
    return new_image

# --- OAK-D PIPELINE ---
def get_oakd_pipeline():
    pipeline = dai.Pipeline()
    
    cam_rgb = pipeline.create(dai.node.ColorCamera)
    cam_rgb.setPreviewSize(640, 480) 
    cam_rgb.setInterleaved(False)
    cam_rgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
    
    cam_rgb.initialControl.setManualFocus(10)
    controlIn = pipeline.create(dai.node.XLinkIn)
    controlIn.setStreamName('control')
    controlIn.out.link(cam_rgb.inputControl)

    mono_left = pipeline.create(dai.node.MonoCamera)
    mono_left.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    mono_left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    
    mono_right = pipeline.create(dai.node.MonoCamera)
    mono_right.setBoardSocket(dai.CameraBoardSocket.CAM_C)
    mono_right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    
    stereo = pipeline.create(dai.node.StereoDepth)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A) 
    
    mono_left.out.link(stereo.left)
    mono_right.out.link(stereo.right)
    
    xout_rgb = pipeline.create(dai.node.XLinkOut)
    xout_rgb.setStreamName("rgb")
    cam_rgb.preview.link(xout_rgb.input)
    
    xout_depth = pipeline.create(dai.node.XLinkOut)
    xout_depth.setStreamName("depth")
    stereo.depth.link(xout_depth.input)
    
    return pipeline

# --- MAIN RUNNER ---
def run():
    print("🚀 Initializing Hailo NPU...")
    try:
        target = VDevice()
        hef = HEF(HEF_PATH)
        conf = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
        group = target.configure(hef, conf)[0]
        in_p = InputVStreamParams.make(group, format_type=FormatType.FLOAT32)
        out_p = OutputVStreamParams.make(group, format_type=FormatType.FLOAT32)
        input_name = hef.get_input_vstream_infos()[0].name
    except Exception as e:
        print(f"❌ NPU Init Failed: {e}")
        return

    print("🚀 Starting OAK-D Pipeline (Max FOV 640x480)...")
    lens_pos = 10 

    with dai.Device(get_oakd_pipeline()) as device:
        q_rgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
        q_depth = device.getOutputQueue(name="depth", maxSize=4, blocking=False)
        q_control = device.getInputQueue(name="control")

        print("✅ System Active.")
        
        with group.activate():
            with InferVStreams(group, in_p, out_p) as pipe:
                while True:
                    in_rgb = q_rgb.get()
                    in_depth = q_depth.get()
                    
                    frame = in_rgb.getCvFrame() 
                    depth = in_depth.getFrame() 

                    # 1. PREPARE FOR HAILO (Letterbox to 640x640)
                    padded_frame = letterbox_image(frame, 640)
                    padded_depth = letterbox_image(depth, 640)
                    
                    f_input = cv2.cvtColor(padded_frame, cv2.COLOR_BGR2RGB).astype(np.float32)
                    res = pipe.infer({input_name: np.expand_dims(f_input, axis=0)})
                    
                    raw_results_batch = list(res.values())[0]
                    raw_results = raw_results_batch[0] 

                    # 2. CALL POST-PROCESS
                    try:
                        processed_frame = inference_result_handler(
                            padded_frame, 
                            raw_results, 
                            LABELS, 
                            CONFIG_DATA, 
                            tracker=None, 
                            draw_trail=False, 
                            depth_frame=padded_depth  # Send the safe padded depth map
                        )
                    except Exception as e:
                        import traceback
                        print(f"Drawing Error: {e}")
                        traceback.print_exc()
                        processed_frame = padded_frame
                    
                    # 3. Draw Focus Info
                    cv2.putText(processed_frame, f"Focus: {lens_pos}", (10, 620), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)

                    cv2.imshow("Blind Nav (Max FOV)", processed_frame)
                    
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'): break
                    if key == ord('w'):
                        lens_pos = max(0, lens_pos - 5)
                        ctrl = dai.CameraControl()
                        ctrl.setManualFocus(lens_pos)
                        q_control.send(ctrl)
                    if key == ord('e'):
                        lens_pos = min(255, lens_pos + 5)
                        ctrl = dai.CameraControl()
                        ctrl.setManualFocus(lens_pos)
                        q_control.send(ctrl)

    cv2.destroyAllWindows()

if __name__ == "__main__":
    run()