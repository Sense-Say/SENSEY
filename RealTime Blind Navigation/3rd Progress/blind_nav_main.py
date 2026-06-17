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
from yolo_utils import YoloPostProcessing, HostCollisionTracker, SceneDescriber, draw_birds_eye_view
from audio_announcer import SpatialAudioAnnouncer, ProximityTonePlayer, speak

HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m.hef"

def letterbox(img, new_shape=(640, 640), color=(114, 114, 114)):
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
    cam = pipeline.create(dai.node.ColorCamera)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_12_MP)
    cam.setIspScale(1, 3)          
    cam.setPreviewSize(640, 640) 
    cam.setInterleaved(False)
    cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    cam.setFps(25)                 
    cam.initialControl.setManualFocus(0)

    mono_left = pipeline.create(dai.node.MonoCamera)
    mono_right = pipeline.create(dai.node.MonoCamera)
    mono_left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
    mono_left.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    mono_right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
    mono_right.setBoardSocket(dai.CameraBoardSocket.CAM_C)

    stereo = pipeline.create(dai.node.StereoDepth)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A) 
    stereo.setOutputSize(1344, 1008)                 

    stereo.initialConfig.setMedianFilter(dai.MedianFilter.KERNEL_7x7) 
    stereo.setLeftRightCheck(True)                    
    stereo.setRectification(True)                    
    stereo.initialConfig.setConfidenceThreshold(230) 
    stereo.setExtendedDisparity(False)    
    stereo.setSubpixel(False)

    mono_left.out.link(stereo.left)
    mono_right.out.link(stereo.right)

    x_isp = pipeline.create(dai.node.XLinkOut)
    x_isp.setStreamName("isp")
    cam.isp.link(x_isp.input)

    x_dep = pipeline.create(dai.node.XLinkOut)
    x_dep.setStreamName("depth")
    stereo.depth.link(x_dep.input)

    return pipeline

def get_latest_frame(q):
    last_msg = None
    while True:
        msg = q.tryGet()
        if msg is None: break
        last_msg = msg
    if last_msg is None: last_msg = q.get()
    return last_msg

def main():
    print("\n🟢 Starting Raspberry Pi 5 Spatial Navigation Engine...")
    
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

    yolo_parser = YoloPostProcessing(score_threshold=0.30, model_type="yolov8")
    announcer = SpatialAudioAnnouncer()
    tones = ProximityTonePlayer(volume=0.35)
    prev_time = time.time()

    with dai.Device(create_pipeline()) as device:
        q_isp = device.getOutputQueue("isp", 1, False)
        q_dep = device.getOutputQueue("depth", 1, False)

        try:
            calibData = device.readCalibration()
            intrinsics = calibData.getCameraIntrinsics(dai.CameraBoardSocket.CAM_A, 1344, 1008)
            fx, fy, cx, cy = intrinsics[0][0], intrinsics[1][1], intrinsics[0][2], intrinsics[1][2]
            print(f"ℹ️ Camera Intrinsics: fx={fx:.1f}, fy={fy:.1f}, cx={cx:.1f}, cy={cy:.1f}")
        except Exception as calib_err:
            fx, fy, cx, cy = 1012.0, 1012.0, 672.0, 504.0
            print(f"⚠️ Using fallback intrinsics: {calib_err}")
        
        collision_tracker = HostCollisionTracker(fx, fy, cx, cy)
        scene_describer = SceneDescriber(announcer)

        with group.activate():
            with InferVStreams(group, in_params, out_params) as pipe:
                print("🚀 Navigation Engine online. Press 'd' for Scene Description | 'q' to quit.")
                speak("Navigation system ready.")
                
                while True:
                    f_bgr_msg = get_latest_frame(q_isp)
                    f_dep_msg = get_latest_frame(q_dep)

                    f_bgr = f_bgr_msg.getCvFrame() 
                    f_dep_raw = f_dep_msg.getFrame()  
                    f_dep = cv2.resize(f_dep_raw, (f_bgr.shape[1], f_bgr.shape[0]), interpolation=cv2.INTER_NEAREST)

                    hailo_img = letterbox(f_bgr, (640, 640))
                    hailo_img = cv2.cvtColor(hailo_img, cv2.COLOR_BGR2RGB)

                    raw_res = pipe.infer({in_name: np.expand_dims(np.ascontiguousarray(hailo_img), axis=0)})
                    output_image, objects = yolo_parser.process_and_draw(raw_res, f_bgr, depth_map=f_dep)

                    collision_tracker.update_tracks(objects)
                    alerts = collision_tracker.analyze_collisions()
                    paths = yolo_parser.check_walkable_paths(f_dep)

                    # Update Voice Queue
                    announcer.update(objects, paths, alerts=alerts, img_w=f_bgr.shape[1])
                    
                    # Update Binaural Sonification Pulse Tones
                    tones.update(collision_tracker.object_tracks, alerts)

                    fps = 1 / (time.time() - prev_time)
                    prev_time = time.time()
                    cv2.putText(output_image, f"FPS: {fps:.1f}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2, cv2.LINE_AA)

                    for track_id, alert in alerts.items():
                        if alert["is_dangerous"]:
                            lbl = alert["label"].split(":")[-1].strip()
                            tti, spd = alert["tti"], alert["speed"]
                            cv2.putText(output_image, f"COLLISION ID {track_id}: {lbl} ({spd:.1f}m/s, TTI:{tti:.1f}s)", 
                                        (20, 80 + int(track_id)*30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)

                    # Render top-down trajectory map
                    bev_map = draw_birds_eye_view(collision_tracker.object_tracks)
                    h_img, w_img = output_image.shape[:2]
                    output_image[15:15+250, w_img-265:w_img-15] = bev_map

                    # Render Depth Map
                    invalid_depth_mask = (f_dep == 0)
                    depth_clipped = np.clip(f_dep, 400, 4000)
                    depth_clipped[invalid_depth_mask] = 4000
                    depth_normalized = ((depth_clipped - 400) / 3600.0 * 255.0).astype(np.uint8)
                    depth_inverted = 255 - depth_normalized
                    depth_colored = cv2.applyColorMap(depth_inverted, cv2.COLORMAP_JET)

                    # HUD display
                    output_image_square = cv2.resize(output_image, (768, 768))
                    depth_colored_square = cv2.resize(depth_colored, (768, 768))
                    combined_monitor = np.hstack((output_image_square, depth_colored_square))

                    cv2.imshow("SENSEY Intelligent 3D Monitor & Depth Map", combined_monitor)
                    
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break
                    elif key == ord('d'):
                        # Trigger cloud visual scene description on demand
                        scene_describer.trigger_description(f_bgr, collision_tracker.object_tracks)

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()