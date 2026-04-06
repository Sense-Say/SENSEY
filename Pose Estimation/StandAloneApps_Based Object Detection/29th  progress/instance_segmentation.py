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

total_dist, current_yaw = 0.0, 0.0
current_x, current_z = 0.0, 0.0
STATE = "EXPLORING" 
audio_queue = queue.Queue()
haptic_sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
UDP_TARGET = ('127.0.0.1', 5005)

pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
tick_sound_effect = pygame.mixer.Sound(TICK_SOUND)
is_ticking = False

# 🚀 FIXED: Added missing tick logic
def play_navigation_tick(cur_yaw, target_yaw, screen_width=1024):
    global is_ticking
    if target_yaw is None or STATE != "NAVIGATING":
        if is_ticking: tick_sound_effect.stop(); is_ticking = False
        return

    # Calculate shortest turn (Corrected for -180 to 180 wrapping)
    turn_err = (target_yaw - cur_yaw + 180) % 360 - 180
    
    # 🚀 NAVIGATION LOGIC:
    # 1. If within 10 degrees, play the tick (User is on track)
    if abs(turn_err) < 10:
        if not is_ticking: 
            tick_sound_effect.play(loops=-1)
            is_ticking = True
    else:
        # 2. If drifting, STOP the tick (User is off track)
        if is_ticking: 
            tick_sound_effect.stop()
            is_ticking = False
            
        # 3. VOICE NUDGE (Only play every 5 seconds so it's not annoying)
        if time.time() % 5 < 0.1: 
            direction = "right" if turn_err > 0 else "left"
            speak_offline(f"Turn {direction} {int(abs(turn_err))} degrees.")

# Make sure is_speaking is defined at the top of your script
is_speaking = False

def audio_worker():
    global is_speaking
    while True:
        cmd = audio_queue.get()
        
        # 🚀 THE "DON'T FALL BEHIND" FIX
        # If the queue has backed up with more than 2 messages, we just skip the old ones
        # so the teacher only hears the most recent, relevant information.
        if audio_queue.qsize() > 2:
            audio_queue.task_done()
            continue

        is_speaking = True
        
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
            
        elif cmd['type'] == 'beep':
            if start_beep_sound:
                start_beep_sound.play()
                time.sleep(start_beep_sound.get_length())
                
        elif cmd['type'] == 'arrival':
            if arrival_sound:
                arrival_sound.play()
                time.sleep(arrival_sound.get_length())
                
        is_speaking = False
        audio_queue.task_done()

threading.Thread(target=audio_worker, daemon=True).start()

class ExplorationManager:
    def __init__(self):
        self.target_yaw = 0.0
        self.horizon_dist = 0.0
        self.seen_objects = {}
        self.last_deadend_time = 0.0 # 🚀 ADD THIS TIMER

    def analyze_floor(self, master_mask, depth_frame, cur_yaw):
        """
        🚀 REVERSE SEGMENTATION: The Floor is where the mask is ZERO.
        """
        zones = [(0, 448), (448, 896), (896, 1344)]
        depth_profile = []
        
        scan_y_start = 500 
        scan_y_end = 1000

        for start_x, end_x in zones:
            zone_mask = master_mask[scan_y_start:scan_y_end, start_x:end_x]
            floor_pts = np.where(zone_mask == 0)
            
            if len(floor_pts[0]) > 0:
                top_y = np.min(floor_pts[0]) + scan_y_start
                avg_x = (start_x + end_x) // 2
                z = depth_frame[top_y, avg_x] / 1000.0
                
                if 0.5 < z < 8.0:
                    depth_profile.append(z)
                else:
                    depth_profile.append(0.0) 
            else:
                depth_profile.append(0.0)
        
        best_idx = int(np.argmax(depth_profile))
        self.horizon_dist = depth_profile[best_idx]
        
        offsets = [-30, 0, 30]
        raw_target_yaw = (cur_yaw + offsets[best_idx]) % 360
        self.target_yaw = (0.7 * self.target_yaw) + (0.3 * raw_target_yaw)

        # 🚀 THE FIX: Add a 5-second cooldown so Piper doesn't spam and crash!
        if all(d < 0.7 for d in depth_profile):
            current_time = time.time()
            if current_time - self.last_deadend_time > 5.0:
                audio_queue.put({"type": "text", "msg": "Dead end ahead. Turn around."})
                self.last_deadend_time = current_time
            
        return best_idx, depth_profile

    def describe_surroundings(self, detections, current_time):
        """🚀 AMBIENT NARRATION: Only speaks if the system is currently quiet."""
        global is_speaking
        
        # 🚀 If the system is busy, don't interrupt it with ambient chatter!
        if is_speaking:
            return None
            
        if len(detections) > 0:
            for det_list in (detections[0] if isinstance(detections, list) else detections):
                for det in det_list:
                    if len(det) >= 6 and float(np.array(det[4]).flatten()[0]) > 0.6:
                        class_id = int(np.array(det[5]).flatten()[0])
                        label = LABELS[class_id]
                        if current_time - self.seen_objects.get(label, 0) > 15:
                            self.seen_objects[label] = current_time
                            return f"{label} nearby."
        return None

# Pseudo-code logic for your next Exploration step:
    def check_for_intersections(depth_profile):
        # depth_profile = [left_depth, center_depth, right_depth]
        
        # If the center is blocked but the left is deep
        if depth_profile[1] < 1.0 and depth_profile[0] > 2.0:
            return "Left"
        # If the center is blocked but the right is deep
        elif depth_profile[1] < 1.0 and depth_profile[2] > 2.0:
            return "Right"
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
                

                # 6. INSTANCE SEGMENTATION & MASKING
                # Returns processed image for display and binary mask for movement logic
                processed_frame, master_mask = inference_result_handler(
                    rgb_frame, hailo_res, labels, config_data, 
                    depth_frame=depth_frame, state_text="EXPLORE", get_mask=True
                )

                # 7. PEDOMETER WITH MASK-GATING
                deltas = []
                is_rotating = abs(gz) > 0.1
                if not is_rotating:
                    for f in fea_data:
                        dx, dy = int(f.position.x * 1344/640), int(f.position.y * 1008/480)
                        if 0 <= dy < 1008 and 0 <= dx < 1344 and master_mask[dy, dx] == 0:
                            z = depth_frame[dy, dx] / 1000.0
                            if 0.8 < z < 8.0:
                                if f.id in feat_history:
                                    d_z = feat_history[f.id] - z
                                    if abs(d_z) < 0.4: deltas.append(d_z)
                                feat_history[f.id] = z
                
                if deltas and is_stepping:
                    move = np.median(deltas) * CALIBRATION_SCALE
                    if move > 0.005:
                        total_dist += move
                        current_x += move * math.sin(math.radians(current_yaw))
                        current_z += move * math.cos(math.radians(current_yaw))

                # 8. EXPLORATION BRAIN & HUD
                best_zone, zone_depths = explorer.analyze_floor(master_mask, depth_frame, current_yaw)
                
                # Haptics (3-Zone)
                for i, d in enumerate(zone_depths):
                    intensity = 1024 if d < 0.6 else (512 if d < 1.5 else 0)
                    haptic_sender.sendto(f"{i}:{intensity}".encode(), UDP_TARGET)
                
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