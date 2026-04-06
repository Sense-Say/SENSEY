#!/usr/bin/env python3
import os
import sys
import queue
import threading
import time
import math
import numpy as np
import collections
import cv2
import depthai as dai
import pygame
import socket
import subprocess # 🚀 FIXED: Added missing import

from functools import partial
from collections import deque

from post_process.postprocessing import inference_result_handler

os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"
BASE_DIR = "/home/raspberrypi/TTS-STT-AUDIO/"
DOC_PATH = "/home/raspberrypi/BlindNavigation/"
REPO_ROOT = "/home/raspberrypi/hailo-apps"
sys.path.append(REPO_ROOT)

from hailo_apps.python.core.common.hailo_inference import HailoInfer
from hailo_apps.python.core.common.toolbox import load_json_file, get_labels

# Change this to your exact validated path
HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m_seg.hef"

# 🚀 ADD THIS CHECK BEFORE YOU INITIALIZE HailoInfer
if not os.path.exists(HEF_PATH):
    print(f"❌ CRITICAL ERROR: The HEF file is NOT at this path: {HEF_PATH}")
    sys.exit(1)
    
PIPER_EXE = os.path.join(BASE_DIR, "piper/piper")
PIPER_MODEL = os.path.join(BASE_DIR, "en_US-lessac-medium.onnx")
TICK_SOUND = os.path.join(BASE_DIR, "watch_tick.wav")

# --- GLOBAL STATE ---
STATE = "EXPLORING" 
total_dist, current_yaw = 0.0, 0.0
current_x, current_z = 0.0, 0.0

# 🚀 FIX: Ensure these audio flags are initialized globally
is_listening = False
is_speaking = False 
is_ticking = False

audio_queue = queue.Queue()

pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
tick_sound_effect = pygame.mixer.Sound(TICK_SOUND)

def play_navigation_tick(cur_yaw, target_yaw, screen_width=1024):
    """
    🚀 DYNAMIC AUDIO TICKING
    The 'Ticks' are a magnet. They only play when you are facing the open path.
    """
    global is_ticking
    
    if target_yaw is None or STATE != "EXPLORING":
        if is_ticking: tick_sound_effect.stop(); is_ticking = False
        return

    # Calculate difference between your body and the deepest path
    turn_err = (target_yaw - cur_yaw + 180) % 360 - 180
    
    # 🚀 If you are within 15 degrees of the deepest path, play the Ticks!
    if abs(turn_err) < 15:
        if not is_ticking: 
            tick_sound_effect.play(loops=-1)
            is_ticking = True
    else:
        # If you drifted off the safe path, stop the ticks instantly
        if is_ticking: 
            tick_sound_effect.stop()
            is_ticking = False

def audio_worker():
    global is_speaking # 🚀 Pull the global variable
    while True:
        cmd = audio_queue.get()
        
        # Don't fall behind if the AI is spamming messages
        if audio_queue.qsize() > 2:
            audio_queue.task_done()
            continue

        is_speaking = True # 🚀 Lock the speaker
        
        if cmd['type'] == 'text':
            print(f"\n[SENSEY VOICE] 🔊: {cmd['msg']}\n")
            cmd_string = f'echo "{cmd["msg"]}" | {PIPER_EXE} --model {PIPER_MODEL} --output_raw 2>/dev/null | paplay --raw --format=s16le --rate=22050 --channels=1'
            subprocess.run(cmd_string, shell=True)
            
        elif cmd['type'] == 'wav':
            if os.path.exists(cmd['path']):
                print(f"\n[SENSEY AUDIO] 🎵: Playing {os.path.basename(cmd['path'])}\n")
                sound = pygame.mixer.Sound(cmd['path'])
                sound.play()
                time.sleep(sound.get_length())
                
        is_speaking = False # 🚀 Unlock the speaker
        audio_queue.task_done()

threading.Thread(target=audio_worker, daemon=True).start()
class ExplorationManager:
    def __init__(self):
        self.target_yaw = 0.0
        self.horizon_dist = 0.0
        self.seen_objects = {}
        self.last_deadend_time = 0.0 
        self.last_intersection_time = 0.0 
        
        # 🚀 INTERSECTION TRACKING
        self.pending_path_side = None # "left" or "right"
        self.dist_to_intersection = 0.0
        self.yaw_at_detection = 0.0

    def analyze_floor(self, master_mask, depth_frame, cur_yaw):
        """
        🚀 REVERSE SEGMENTATION (Virtual LiDAR)
        Finds the 'deepest' clear path in the room by analyzing the unmasked floor.
        """
        # Divide the 1344 screen into 5 vertical slices for higher precision
        zones = [
            (0, 268),    # Far Left
            (268, 537),  # Mid Left
            (537, 806),  # Center
            (806, 1075), # Mid Right
            (1075, 1344) # Far Right
        ]
        depth_profile = []
        scan_y_start = 500 

        for start_x, end_x in zones:
            zone_mask = master_mask[scan_y_start:1008, start_x:end_x]
            floor_pts = np.where(zone_mask == 0)
            
            if len(floor_pts[0]) > 0:
                top_y = np.min(floor_pts[0]) + scan_y_start
                avg_x = (start_x + end_x) // 2
                z = depth_frame[top_y, avg_x] / 1000.0
                
                if 0.5 < z < 8.0: depth_profile.append(z)
                else: depth_profile.append(0.0) 
            else:
                depth_profile.append(0.0) 
        
        best_idx = int(np.argmax(depth_profile))
        self.horizon_dist = depth_profile[best_idx]
        
        offsets = [-40, -20, 0, 20, 40]
        raw_target_yaw = (cur_yaw + offsets[best_idx]) % 360
        self.target_yaw = (0.7 * self.target_yaw) + (0.3 * raw_target_yaw)

        return best_idx, depth_profile

    def check_intersections(self, depth_profile):
        current_time = time.time()
        if current_time - self.last_intersection_time < 8.0:
            return None

        # Logic for identifying openings
        left_open = max(depth_profile[0], depth_profile[1]) > 2.5
        right_open = max(depth_profile[3], depth_profile[4]) > 2.5
        center_open = depth_profile[2] > 1.5
        
        msg = None
        if center_open and left_open:
            msg = "Path opens to your left."
        elif center_open and right_open:
            msg = "Path opens to your right."
            
        if msg:
            self.last_intersection_time = current_time
            return msg # 🚀 Returns a STRING, not a tuple
            
        return None

    def check_user_choice(self, currrent_yaw):
        """🚀 INTENT RECOGNITION: Detects if the user physically turned 90°."""
        if self.pending_path_side is None:
            return None

        # Calculate how many degrees the user has rotated since we saw the path
        yaw_delta = (current_yaw - self.yaw_at_detection + 180) % 360 - 180
        
        # If user turns > 70 degrees toward the suggested side
        if self.pending_path_side == "left" and yaw_delta < -70:
            self.pending_path_side = None # Reset
            return "Changing route to left aisle."
        elif self.pending_path_side == "right" and yaw_delta > 70:
            self.pending_path_side = None # Reset
            return "Changing route to right aisle."
            
        return None

    def describe_surroundings(self, detections, current_time, labels):
        global is_speaking
        if is_speaking: return None

        allowed_objects = {
            "person": "person", "chair": "chair", "dining table": "desk",
            "backpack": "bag", "handbag": "bag", "suitcase": "bag"
        }
            
        for det in detections:
            # 🚀 FIX: Support both Dictionary and List input
            if isinstance(det, dict):
                score = det['score']
                class_id = det['class_id']
                bbox = det['bbox'] # [xmin, ymin, xmax, ymax]
            else:
                # Fallback if it receives a raw list [xmin, ymin, xmax, ymax, score, class_id]
                bbox = det[0:4]
                score = det[4]
                class_id = int(det[5])
            
            if score < 0.70: # Increase from 0.55 to 0.70 to stop ghost 'people'
                continue
            
            if score > 0.55:
                original_label = labels[class_id]
                
                if original_label in allowed_objects:
                    spoken_label = allowed_objects[original_label]
                    cx = (bbox[0] + bbox[2]) / 2.0
                    norm_cx = cx / 1344.0
                    
                    memory_key = f"{spoken_label}_{int(norm_cx > 0.33)}_{int(norm_cx > 0.66)}"
                    
                    if current_time - self.seen_objects.get(memory_key, 0) > 8.0:
                        self.seen_objects[memory_key] = current_time
                        if norm_cx < 0.33: return f"Beware of the {spoken_label} on your left side."
                        elif norm_cx > 0.66: return f"Beware of the {spoken_label} on your right side."
                        else: return f"The {spoken_label} is blocking your path."
        return None

def inference_callback(completion_info, bindings_list, input_batch, output_queue):
    if not completion_info.exception:
        for i, bindings in enumerate(bindings_list):
            result = {name: np.expand_dims(bindings.output(name).get_buffer(), axis=0) for name in bindings._output_names}
            output_queue.put((input_batch[i], result))

def infer_loop(hailo_inference, input_queue, output_queue, stop_event):
    pending_jobs = collections.deque()
    while not stop_event.is_set():
        batch = input_queue.get()
        if not batch: break
        input_batch, preprocessed_batch = batch
        callback = partial(inference_callback, input_batch=input_batch, output_queue=output_queue)
        job = hailo_inference.run(preprocessed_batch, callback)
        pending_jobs.append(job)
        while len(pending_jobs) > 3: pending_jobs.popleft().wait(1000)

# --- OAK-D PIPELINE ---
def get_oak_pipeline():
    p = dai.Pipeline()
    
    # RGB Camera
    cam = p.create(dai.node.ColorCamera)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_12_MP)
    cam.setIspScale(1, 3) 
    cam.setInterleaved(False)
    cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    cam.setPreviewSize(640, 640)
    cam.setPreviewKeepAspectRatio(False) 
    cam.initialControl.setManualFocus(0) 
    cam.setFps(15) 
    
    # Mono Cameras
    left = p.create(dai.node.MonoCamera)
    left.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
    
    right = p.create(dai.node.MonoCamera)
    right.setBoardSocket(dai.CameraBoardSocket.CAM_C)
    right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
    
    # Stereo Depth
    stereo = p.create(dai.node.StereoDepth)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    stereo.setOutputSize(1344, 1008) 
    stereo.setLeftRightCheck(True)
    
    left.out.link(stereo.left)
    right.out.link(stereo.right)
    
    # IMU
    imu = p.create(dai.node.IMU)
    imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 100)
    imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 100)
    imu.setBatchReportThreshold(1)
    imu.setMaxBatchReports(20)
    
    # Feature Tracker
    feat = p.create(dai.node.FeatureTracker)
    feat.setHardwareResources(1, 1)
    feat.initialConfig.setNumTargetFeatures(200)
    left.out.link(feat.inputImage)
    
    # XLinkOuts
    x_isp = p.create(dai.node.XLinkOut); x_isp.setStreamName("isp"); cam.isp.link(x_isp.input)
    x_pre = p.create(dai.node.XLinkOut); x_pre.setStreamName("pre"); cam.preview.link(x_pre.input)
    x_dep = p.create(dai.node.XLinkOut); x_dep.setStreamName("depth"); stereo.depth.link(x_dep.input)
    x_imu = p.create(dai.node.XLinkOut); x_imu.setStreamName("imu"); imu.out.link(x_imu.input)
    x_fea = p.create(dai.node.XLinkOut); x_fea.setStreamName("feat"); feat.outputFeatures.link(x_fea.input)
    
    return p

def run_exploration():
    global current_yaw, total_dist, current_x, current_z, STATE
    global is_ticking, trigger_voice_note_record
    
    # 🚀 1. LOCAL VARIABLES & SAFETY GATES
    last_imu_t, feat_history = None, {}
    motion_window = deque(maxlen=10)
    explorer = ExplorationManager()
    warmup_frames = 0
    CALIBRATION_SCALE = 1.66
    
    # 🚀 2. HAILO INITIALIZATION WITH RECOVERY
    try:
        hailo_inference = HailoInfer(HEF_PATH, batch_size=1, output_type="FLOAT32")
    except Exception as e:
        print(f"🔴 Hailo Initialization Error: {e}")
        # If the NPU is locked, the only way to recover is to restart the hailort_service
        subprocess.run(["sudo", "systemctl", "restart", "hailort"], stderr=subprocess.DEVNULL)
        time.sleep(2)
        hailo_inference = HailoInfer(HEF_PATH, batch_size=1, output_type="FLOAT32")
    except Exception as e:
        print(f"🔴 Hailo Initialization Error: {e}")
        time.sleep(3)
        return

    input_queue = queue.Queue(4)
    output_queue = queue.Queue(4)
    stop_event = threading.Event()
    labels = get_labels(None)
    config_data = load_json_file("config.json")

    # 🚀 FIX 3: Pass the 'labels' variable into the ExplorationManager!
    explorer = ExplorationManager()

    with dai.Device(get_oak_pipeline()) as device:
        q_pre = device.getOutputQueue("pre", 4, False)
        q_isp = device.getOutputQueue("isp", 4, False)
        q_dep = device.getOutputQueue("depth", 4, False)
        q_imu = device.getOutputQueue("imu", 20, False)
        q_fea = device.getOutputQueue("feat", 4, False)

        threading.Thread(target=infer_loop, args=(hailo_inference, input_queue, output_queue, stop_event), daemon=True).start()
        print("🚀 SENSEY ASYNC EXPLORATION LIVE.")
        
        while not stop_event.is_set():
            # 🚀 3. IMU FUSION (6-DOF)
            imuData = q_imu.tryGetAll()
            is_stepping = False
            gx, gy, gz = 0.0, 0.0, 0.0
            for data in imuData:
                for packet in data.packets:
                    ts = packet.acceleroMeter.timestamp.get().total_seconds()
                    if last_imu_t is None: last_imu_t = ts; continue
                    dt = ts - last_imu_t; last_imu_t = ts
                    gx, gy, gz = packet.gyroscope.x, packet.gyroscope.z, packet.gyroscope.y
                    current_yaw -= (gz * (180.0 / math.pi) * dt)
                    current_yaw = (current_yaw + 180) % 360 - 180
                    if abs(math.sqrt(packet.acceleroMeter.x**2 + packet.acceleroMeter.y**2 + packet.acceleroMeter.z**2) - 9.81) > 0.3:
                        is_stepping = True

            # 4. Push frame to NPU
            if not q_pre.has(): continue
            pre_frame = q_pre.get().getCvFrame()
            input_queue.put(([pre_frame], [pre_frame]))

            try:
                original_batch, hailo_res = output_queue.get_nowait()
                rgb_frame = q_isp.get().getCvFrame()
                depth_frame = q_dep.get().getFrame()
                fea_data = q_fea.get().trackedFeatures
                

                # 🚀 6. INSTANCE SEGMENTATION & MASKING
                # Capture all 3 returns correctly!
                processed_frame, master_mask, formatted_detections = inference_result_handler(
                    rgb_frame, hailo_res, labels, config_data, 
                    depth_frame=depth_frame, state_text="EXPLORE", get_mask=True
                )

                # 🚀 7. EXPLORATION BRAIN
                # This function returns (index, [list]). We store them in variables.
                best_zone, zone_depths = explorer.analyze_floor(master_mask, depth_frame, current_yaw)
                
                if STATE == "EXPLORING":
                    # 🚀 FIX: Do NOT put 'zone_depths' into the audio_queue.
                    # Instead, we pass it to the INTERSECTION checker which returns TEXT.
                    path_choice_msg = explorer.check_intersections(zone_depths)
                    
                    if path_choice_msg:
                        # This will now print a clean message like: [SENSEY VOICE] 🔊: Path opens to your right.
                        audio_queue.put({"type": "text", "msg": path_choice_msg})
                    
                    # Ambient Narration
                    surr_msg = explorer.describe_surroundings(formatted_detections, time.time(), labels)
                    if surr_msg: 
                        audio_queue.put({"type": "text", "msg": surr_msg})

                # 8. TICKING "MAGNET"
                play_navigation_tick(current_yaw, explorer.target_yaw, 1024)
                
                cv2.imshow("SENSEY Exploration", cv2.resize(processed_frame, (1024, 768)))

            except queue.Empty: pass
            if cv2.waitKey(1) == ord('q'): stop_event.set(); break

if __name__ == "__main__":
    # 🚀 REMOVE THE WHILE TRUE LOOP IF IT EXISTS HERE
    # If your main() function has a while True, change it to run ONCE.
    try:
        run_exploration()
    except Exception as e:
        print(f"🔴 CRITICAL ERROR: {e}")
        # Stop everything. DO NOT RESTART.
        sys.exit(1)
