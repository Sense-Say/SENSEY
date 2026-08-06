import cv2
import depthai as dai
import numpy as np
import os
import sys
import time
import queue
import threading
import blobconverter

os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"
os.environ["HAILO_SCHEDULER"] = "1"

from hailo_platform import (HEF, VDevice, InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams, FormatType, HailoStreamInterface)
from yolo_utils import YoloPostProcessing
from audio_announcer import SpatialAudioAnnouncer, speak, audio_queue

# --- GLOBAL CONFIGURATION ---
HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m.hef"

# --- 🚀 HOST SYNC HELPER (From gen2-blur-faces) ---
class HostSync:
    def __init__(self):
        self.arrays = {}
    def add_msg(self, name, msg):
        if not name in self.arrays:
            self.arrays[name] = []
        self.arrays[name].append(msg)
    def get_msgs(self, seq):
        ret = {}
        for name, arr in self.arrays.items():
            for i, msg in enumerate(arr):
                if msg.getSequenceNum() == seq:
                    ret[name] = msg
                    self.arrays[name] = arr[i:]
                    break
        return ret

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
    print("Creating pipeline...")
    pipeline = dai.Pipeline()
    
    # 1. Color Camera Node (Scale ISP to 1344x1008 - 12MP Native 4:3)
    cam = pipeline.create(dai.node.ColorCamera)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_12_MP)
    cam.setIspScale(1, 3)          # Scale FULL 12MP sensor to 1344x1008
    cam.setPreviewSize(300, 300)   # Required preview size for face-detection-retail model
    cam.setInterleaved(False)
    cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    cam.setFps(20)
    cam.initialControl.setManualFocus(0)

    # On-device Face Detection Neural Network (Direct v2.32 MobileNet Node)
    print("Creating Face Detection Neural Network...")
    face_det_nn = pipeline.create(dai.node.MobileNetDetectionNetwork)
    face_det_nn.setConfidenceThreshold(0.1)
    
    # Compile and download the face model for exactly 1 SHAVE
    # as recommended by your camera hardware firmware warning log!
    face_det_nn.setBlobPath(blobconverter.from_zoo(
        name="face-detection-retail-0004",
        shaves=1, 
    ))
    cam.preview.link(face_det_nn.input)

    # On-device Object Tracker (Tracks faces smoothly even when turned)
    objectTracker = pipeline.create(dai.node.ObjectTracker)
    objectTracker.setDetectionLabelsToTrack([1]) # Track faces (ID 1)
    objectTracker.setTrackerType(dai.TrackerType.ZERO_TERM_COLOR_HISTOGRAM)
    objectTracker.setTrackerIdAssignmentPolicy(dai.TrackerIdAssignmentPolicy.SMALLEST_ID)

    # Linking Face detector to Tracker
    face_det_nn.passthrough.link(objectTracker.inputDetectionFrame)
    face_det_nn.passthrough.link(objectTracker.inputTrackerFrame)
    face_det_nn.out.link(objectTracker.inputDetections)

    # 2. Mono Camera Nodes (OV7251 native 640x480)
    mono_left = pipeline.create(dai.node.MonoCamera)
    mono_right = pipeline.create(dai.node.MonoCamera)
    mono_left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
    mono_left.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    mono_right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
    mono_right.setBoardSocket(dai.CameraBoardSocket.CAM_C)

    # 3. Stereo Depth Node (Aligned and locked at exactly 1344x1008 to match Color ISP)
    stereo = pipeline.create(dai.node.StereoDepth)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A) # Align depth to RGB frame
    stereo.setOutputSize(1344, 1008)                 # Match depth output to 1344x1008 Color ISP

    # High-accuracy hardware matching parameters
    stereo.initialConfig.setMedianFilter(dai.MedianFilter.KERNEL_7x7) 
    stereo.setLeftRightCheck(True)       
    stereo.setRectification(True)        
    stereo.initialConfig.setConfidenceThreshold(230) 

    # Linking Mono cameras to Stereo
    mono_left.out.link(stereo.left)
    mono_right.out.link(stereo.right)

    # Outputs
    cam_xout = pipeline.create(dai.node.XLinkOut)
    cam_xout.setStreamName("frame")
    cam.isp.link(cam_xout.input) # Outputs full 1344x1008 BGR frame

    pass_xout = pipeline.create(dai.node.XLinkOut)
    pass_xout.setStreamName("pass_out")
    objectTracker.passthroughTrackerFrame.link(pass_xout.input)

    tracklets_xout = pipeline.create(dai.node.XLinkOut)
    tracklets_xout.setStreamName("tracklets")
    objectTracker.out.link(tracklets_xout.input)

    x_dep = pipeline.create(dai.node.XLinkOut)
    x_dep.setStreamName("depth")
    stereo.depth.link(x_dep.input)

    print("Pipeline created.")
    return pipeline

def main():
    print("\n🟢 Starting Blind Navigation - Phase 3/4 (Depth & Wall Fusion)...")
    
    hef_path = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m.hef"
    
    try:
        target = VDevice()
        hef = HEF(hef_path)
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
    
    # Initialize HostSync
    sync = HostSync()

    # 🚀 FIX: Removed the pre-opening device_info block. 
    # The pipeline now initializes natively and cleanly on-device with zero platform checks!
    with dai.Device(create_pipeline()) as device:
        q_dep = device.getOutputQueue("depth", 1, False)
        
        # Mapped the queue streams
        q_isp = device.getOutputQueue("frame", 1, False)
        tracklets_q = device.getOutputQueue("tracklets", 1, False)
        pass_q = device.getOutputQueue("pass_out", 1, False)

        with group.activate():
            with InferVStreams(group, in_params, out_params) as pipe:
                print("🚀 Navigation System Live.")
                
                # Speak system initialization
                speak("Navigation system online. Safe path finding active.")
                
                while True:
                    # Sync frames
                    f_bgr = q_isp.get().getCvFrame() 
                    f_dep_raw = q_dep.get().getFrame()  # Pull native 16-bit 480p depth frame (no alignment active!)
                    
                    # Rescale the depth map in Python to match the RGB frame size (1344x1008) perfectly
                    f_dep = cv2.resize(f_dep_raw, (f_bgr.shape[1], f_bgr.shape[0]), interpolation=cv2.INTER_NEAREST)

                    # --- RUN ON-DEVICE BLURRING RESOLUTIONS ---
                    # In your loop, since the incoming frame 'f_bgr' is already pre-processed,
                    # we extract active tracklets and blur the face on host before NPU inference.
                    nn_in = tracklets_q.tryGet()
                    if nn_in is not None:
                        # Synchronize the frame with its correct tracking sequence
                        seq = pass_q.get().getSequenceNum()
                        msgs = sync.get_msgs(seq)
                        if "color" in msgs:
                            f_bgr = msgs["color"].getCvFrame()

                        for t in nn_in.tracklets:
                            # Expand the bounding box a bit so it fits the face nicely (covers hair/chin/ears)
                            t.roi.x -= t.roi.width / 10
                            t.roi.width = t.roi.width * 1.2
                            t.roi.y -= t.roi.height / 7
                            t.roi.height = t.roi.height * 1.2

                            roi = t.roi.denormalize(f_bgr.shape[1], f_bgr.shape[0])
                            bbox = [
                                max(0, int(roi.topLeft().x)), 
                                max(0, int(roi.topLeft().y)), 
                                min(f_bgr.shape[1]-1, int(roi.bottomRight().x)), 
                                min(f_bgr.shape[0]-1, int(roi.bottomRight().y))
                            ]

                            if bbox[2] > bbox[0] and bbox[3] > bbox[1]:
                                face = f_bgr[bbox[1]:bbox[3], bbox[0]:bbox[2]]
                                if face.size > 0:
                                    fh, fw, fc = face.shape
                                    frame_h, frame_w, frame_c = f_bgr.shape

                                    # Create blur mask around the face
                                    mask = np.zeros((frame_h, frame_w), np.uint8)
                                    polygon = cv2.ellipse2Poly((bbox[0] + int(fw / 2), bbox[1] + int(fh / 2)), (int(fw / 2), int(fh / 2)), 0, 0, 360, delta=1)
                                    cv2.fillConvexPoly(mask, polygon, 255)

                                    # Fast Bilinear Downsample-Blur Pipeline (Saves CPU, maintains high FPS)
                                    frame_copy = f_bgr.copy()
                                    small_roi = cv2.resize(frame_copy, (int(frame_w * 0.25), int(frame_h * 0.25)), interpolation=cv2.INTER_LINEAR)
                                    blurred_small = cv2.GaussianBlur(small_roi, (15, 15), 5)
                                    blurred_frame = cv2.resize(blurred_small, (frame_w, frame_h), interpolation=cv2.INTER_LINEAR)

                                    face_extracted = cv2.bitwise_and(blurred_frame, blurred_frame, mask=mask)
                                    background_mask = cv2.bitwise_not(mask)
                                    background = cv2.bitwise_and(f_bgr, f_bgr, mask=background_mask)
                                    f_bgr = cv2.add(background, face_extracted)

                    # Add frame to host sync
                    sync.add_msg("color", q_isp.get())

                    # Pad BGR frame for YOLOv8 NPU
                    hailo_img = letterbox(f_bgr, (640, 640))
                    hailo_img = cv2.cvtColor(hailo_img, cv2.COLOR_BGR2RGB)

                    # Infer on Hailo
                    raw_res = pipe.infer({in_name: np.expand_dims(np.ascontiguousarray(hailo_img), axis=0)})
                    
                    # Parse and Fuse Depth Map
                    output_image, objects = yolo_parser.process_and_draw(raw_res, f_bgr, depth_map=f_dep)

                    # Extract floor walkable status from depth map
                    paths = yolo_parser.check_walkable_paths(f_dep)

                    # Pass spatial grid objects + floor paths to the Audio Announcer
                    announcer.update(objects, paths, img_w=f_bgr.shape[1])

                    # Calculate and draw FPS on HUD
                    fps = 1 / (time.time() - prev_time)
                    prev_time = time.time()
                    cv2.putText(output_image, f"FPS: {fps:.1f}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2, cv2.LINE_AA)

                    # --- REAL-TIME DEPTH MAP RENDERING ---
                    invalid_depth_mask = (f_dep == 0)
                    depth_clipped = np.clip(f_dep, 400, 4000)
                    depth_clipped[invalid_depth_mask] = 4000
                    
                    depth_normalized = ((depth_clipped - 400) / 3600.0 * 255.0).astype(np.uint8)
                    depth_inverted = 255 - depth_normalized
                    depth_colored = cv2.applyColorMap(depth_inverted, cv2.COLORMAP_JET)

                    # VERTICAL STRETCH TO 1:1 SQUARE (768x768)
                    output_image_square = cv2.resize(output_image, (768, 768))
                    depth_colored_square = cv2.resize(depth_colored, (768, 768))

                    # Horizontally stack the two square feeds (Total size: 1536x768)
                    combined_monitor = np.hstack((output_image_square, depth_colored_square))

                    # Display the combined 1536x768 screen
                    cv2.imshow("SENSEY Intelligent 3D Monitor & Depth Map", combined_monitor)
                    
                    if cv2.waitKey(1) == ord('q'): 
                        break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
