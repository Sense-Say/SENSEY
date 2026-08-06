import cv2
import depthai as dai
import numpy as np
import sys, os, time, math, json, threading, subprocess
import sounddevice as sd
import vosk
import pygame
from hailo_platform import HEF, VDevice, HailoStreamInterface, InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams, FormatType
from gpiozero import Button
from collections import deque
from gpiozero import PWMOutputDevice


is_listening, is_speaking = False, False
is_recording_note = False
voice_note_buffer = []  # 🚀 THE SPONGE: Stores audio chunks
note_recording_start_time = 0.0 # Tracks the 5-second limit

# --- ENV ---
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"
os.environ["HAILO_SCHEDULER"] = "1"
DOC_PATH = "/home/raspberrypi/BlindNavigation"
REPO_ROOT = "/home/raspberrypi/hailo-apps"
sys.path.append(REPO_ROOT)
from hailo_apps.python.standalone_apps.object_detection.object_detection_post_process import inference_result_handler

# --- CONFIG ---
HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m.hef"
VOSK_MODEL_PATH = "/home/raspberrypi/TTS-STT-AUDIO/vosk-model-en-us-0.22-lgraph"
PIPER_EXE = "/home/raspberrypi/TTS-STT-AUDIO/piper/piper"
PIPER_MODEL = "/home/raspberrypi/TTS-STT-AUDIO/en_US-lessac-medium.onnx"
TICK_SOUND = "/home/raspberrypi/TTS-STT-AUDIO/watch_tick.wav"
LABELS = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"]
CONFIG_DATA = {"visualization_params": {"score_thres": 0.5, "max_boxes_to_draw": 50}}

# 🚀 EXPANDED DICTIONARY (Ordinals, Destinations, Reverse, Identify added)
ALLOWED_WORDS = [
    "record", "finish", "go", "to", "point", "saved", "front", "back", "door", "desk", 
    "window", "stop", "navigate", "start", "yes", "no", "correct", "wrong", "update", 
    "pause", "resume", "[unk]", "first", "second", "third", "fourth", "fifth", "sixth", 
    "seventh", "eighth", "ninth", "tenth", "destination", "reverse", "identify", "one", "two", "three"
]

MIN_Z_DELTA, MAX_Z_DELTA = 0.01, 0.30

# --- AUDIO INIT ---
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
tick_sound_effect = pygame.mixer.Sound(TICK_SOUND)
is_ticking = False

# 🚀 NEW: Load your custom sound effects via Pygame to prevent 'Static'
try:
    start_beep_sound = pygame.mixer.Sound("/home/raspberrypi/TTS-STT-AUDIO/recording_notes.wav")
    arrival_sound = pygame.mixer.Sound("/home/raspberrypi/TTS-STT-AUDIO/arrived_destination02.wav")
except Exception as e:
    print(f"⚠️ Warning: Could not load custom sounds. {e}")
    # Fallback to standard beep if your files are missing
    start_beep_sound = None
    arrival_sound = None

# --- STATE & ROUTE VARIABLES ---
STATE = "IDLE" 
total_dist, current_yaw, last_wp_dist, current_x, current_z = 0.0, 0.0, 0.0, 0.0, 0.0
recorded_path, nav_path = [], []
current_route_filename, landmark_count, pending_command, previous_state = "", 0, "", "IDLE"
tag_persistence_counter = 0


pending_tag_scan = "" # 🚀 NEW: Tracks what we are waiting to scan ("start", "finish", or "navigate")
scanned_tag_id = None # 🚀 NEW: Stores the ID of the tag we just looked at

# --- EXPLORATION SETTINGS ---
CENTER_CLEAR_THRESHOLD = 2.0  # Meters: If center depth > this, play the centering tick
SIDE_OPENING_THRESHOLD = 2.5  # Meters: Depth required to identify a side aisle
AISLE_PERSISTENCE_FRAMES = 10 # Frames required to confirm a path opening
aisle_cooldown = 0            # Global cooldown to prevent spamming Piper

# 🚀 SILENCE LOGS
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
vosk.SetLogLevel(-1)

# Ensure btn is defined early to avoid NameError
try:
    from gpiozero import Button
    btn = Button(26, pull_up=True)
except:
    btn = None


# 🚀 ALIAS/MAPPING VARS
pending_route_key = ""    # Will store e.g., 'destination_1'
pending_route_alias = ""  # Will store e.g., 'front door to desk'
ROUTE_MAP_FILE = os.path.join(DOC_PATH, "route_map.json")

def get_ordinal_key(text):
    """
    🚀 UPGRADED PARSER: Handles 'first', 'destination one', '1', etc.
    Returns: (destination_X, number_string)
    """
    # Dictionary mapping every possible way a teacher might say a number
    mapping = {
        "1": "1", "one": "1", "first": "1",
        "2": "2", "two": "2", "second": "2",
        "3": "3", "three": "3", "third": "3",
        "4": "4", "four": "4", "fourth": "4",
        "5": "5", "five": "5", "fifth": "5",
        "6": "6", "six": "6", "sixth": "6",
        "7": "7", "seven": "7", "seventh": "7",
        "8": "8", "eight": "8", "eighth": "8",
        "9": "9", "nine": "9", "ninth": "9",
        "10": "10", "ten": "10", "tenth": "10"
    }
    
    words = text.lower().split()
    for word in words:
        if word in mapping:
            num = mapping[word]
            return f"destination_{num}", num
    return None, None

import queue
audio_queue = queue.Queue()

# 🚀 THE SINGLE-THREADED AUDIO MANAGER (No more aplay, no more busy errors)
def audio_worker():
    """🚀 THE SINGLE-THREADED AUDIO MANAGER: Perfectly Silent Terminal."""
    while True:
        cmd = audio_queue.get()
        
        if cmd['type'] == 'text':
            # This print is for YOU to see what the AI is saying
            print(f"\n[SPEECH SYSTEM] 🔊: {cmd['msg']}\n")
            
            # 🚀 THE LOG KILLER: Use DEVNULL inside subprocess to ensure piper is silent
            cmd_string = f'echo "{cmd["msg"]}" | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | paplay --raw --format=s16le --rate=22050 --channels=1'
            subprocess.run(cmd_string, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
        elif cmd['type'] == 'wav':
            if os.path.exists(cmd['path']):
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
        
        audio_queue.task_done()

# Start this thread once at the beginning of your script
threading.Thread(target=audio_worker, daemon=True).start()

class NavigationManager:
    def __init__(self):
        self.path = []
        self.current_wp_index = 0
        self.active = False
        self.target_yaw = 0.0
        self.distance_to_wp = 0.0
        self.offset_x, self.offset_z, self.offset_yaw = 0.0, 0.0, 0.0
        self.stride_length = 0.33

    def load_path(self, path_data):
        """🚀 PURE NODE-TO-NODE LOGIC: Ignores all 'path' breadcrumbs."""
        self.path = []
        for p in path_data:
            label = str(p[2]).lower()
            if "point" in label or "destination" in label or "start" in label:
                self.path.append({
                    "x": p[0], "z": p[1], "type": "ANCHOR", "label": p[2], 
                    "yaw": p[3] if len(p) > 3 else 0.0,
                    "note": p[4] if len(p) > 4 else "",
                    "total_dist": p[5] if len(p) > 5 else 0.0 
                })
        
        self.active = True
        # 🚀 REVERSE FIX: Start at Index 1 so we don't 'arrive' at our starting spot instantly
        self.current_wp_index = 1 if len(self.path) > 1 else 0
        self.offset_x, self.offset_z, self.offset_yaw = 0, 0, 0

    def get_instruction(self, cur_x, cur_z, cur_yaw, current_total_dist, is_on_demand=False):
        global STATE
        if not self.active or self.current_wp_index >= len(self.path): return None
        
        target = self.path[self.current_wp_index]
        origin_node = self.path[0] # 🚀 The node we started this session at
        
        # 🚀 THE REVERSE FIX:
        # Distance is (Absolute difference from session start to target) minus (Physical feet walked)
        total_segment_length = abs(target["total_dist"] - origin_node["total_dist"])
        self.distance_to_wp = max(0.0, total_segment_length - current_total_dist)
        
        # HUD YAW LOCK
        if self.distance_to_wp > 0.1:
            self.target_yaw = (target["yaw"] + self.offset_yaw) % 360

        if is_on_demand:
            dist_str = f"{self.distance_to_wp:.2f}"
            next_anchor_yaw = (target["yaw"] + self.offset_yaw) % 360
            turn_err = (next_anchor_yaw - cur_yaw + 180) % 360 - 180
            
            if abs(turn_err) <= 5:
                return f"Walk straight for {dist_str} meters."
            elif turn_err < -5 and turn_err >= -174:
                return f"Turn {int(abs(turn_err))} degrees to the left side and walk {dist_str} meters."
            elif turn_err > 5 and turn_err <= 174:
                return f"Turn {int(turn_err)} degrees to the right side and walk {dist_str} meters."
            else:
                return f"Turn behind you and walk {dist_str} meters."

        # Arrival at Node (Threshold 0.45m)
        if self.distance_to_wp < 0.45:
            node_label = target['label']
            arrived_node_yaw = (target["yaw"] + self.offset_yaw) % 360
            
            self.current_wp_index += 1
            
            if self.current_wp_index >= len(self.path):
                self.active = False
                STATE = "IDLE"
                audio_queue.put({"type": "arrival"})
                audio_queue.put({"type": "text", "msg": "Arrived at destination."})
                return None
            
            audio_queue.put({"type": "beep"})
            audio_queue.put({"type": "text", "msg": f"Reached {node_label}."})
            
            if target['note'] and target['note'].endswith(".wav"):
                audio_queue.put({"type": "wav", "path": os.path.join(DOC_PATH, target['note'])})
            
            # 🚀 NEXT POINT CALCULATION
            next_wp = self.path[self.current_wp_index]
            
            # Use abs() for odometer math so Forward/Reverse both work
            next_dist = abs(next_wp["total_dist"] - target["total_dist"])
            next_yaw = (next_wp["yaw"] + self.offset_yaw) % 360
            
            turn_err = (next_yaw - arrived_node_yaw + 180) % 360 - 180
            dist_str = f"{next_dist:.2f}"
            
            if abs(turn_err) <= 5:
                final_msg = f"Walk straight for {dist_str} meters."
            elif turn_err < -5 and turn_err >= -174:
                final_msg = f"Turn {int(abs(turn_err))} degrees to the left side and walk {dist_str} meters."
            elif turn_err > 5 and turn_err <= 174:
                final_msg = f"Turn {int(turn_err)} degrees to the right side and walk {dist_str} meters."
            else:
                final_msg = f"Turn behind you and walk {dist_str} meters."
            
            audio_queue.put({"type": "text", "msg": final_msg})
        
        return None

    def get_path_remaining_distance(self, current_total_dist):
        if not self.active or self.current_wp_index >= len(self.path): return 0.0
        # For the HUD countdown
        target = self.path[self.current_wp_index]
        origin_node = self.path[0]
        total_segment_length = abs(target["total_dist"] - origin_node["total_dist"])
        return max(0.0, total_segment_length - current_total_dist)

nav_engine = NavigationManager()

def play_navigation_tick(is_path_clear):
    global is_ticking
    # If the center aisle is clear, play the tick (Virtual Rail)
    if is_path_clear:
        if not is_ticking:
            tick_sound_effect.play(loops=-1)
            is_ticking = True
    else:
        if is_ticking:
            tick_sound_effect.stop()
            is_ticking = False

def speak_offline(text):
    if not text.strip(): return
    def _speak():
        global is_speaking
        is_speaking = True
        # 🚀 SILENCE GUARANTEED: Added '> /dev/null 2>&1' inside the shell command
        cmd = f'echo "{text}" | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | paplay --raw --format=s16le --rate=22050 --channels=1 > /dev/null 2>&1'
        subprocess.run(cmd, shell=True)
        is_speaking = False
    threading.Thread(target=_speak, daemon=True).start()

def execute_action(cmd):
    global STATE, recorded_path, nav_path, total_dist, current_yaw, last_wp_dist, current_route_filename, landmark_count, current_x, current_z, nav_engine
    global pending_route_key, pending_route_alias, scanned_tag_id, motor_map # 🚀 Added motor_map
    
    print(f"DEBUG: execute_action received '{cmd}'. Current STATE: {STATE}")
    
    # ------------- 1. START RECORDING (Post-Tag Scan) -------------------
    if cmd == "start_recording_dest":
        STATE = "RECORDING"
        current_route_filename = pending_route_key
        
        # Save name alias mapping to route_map.json
        mapping = {}
        if os.path.exists(ROUTE_MAP_FILE):
            try:
                with open(ROUTE_MAP_FILE, 'r') as f: 
                    mapping = json.load(f)
            except: pass
                
        mapping[pending_route_key] = pending_route_alias
        with open(ROUTE_MAP_FILE, 'w') as f: 
            json.dump(mapping, f, indent=4) 

        # 🚀 7-ELEMENT JSON INITIALIZATION [X, Z, Label, Yaw, Note, Total_Dist, Tag_ID]
        recorded_path = [[0.0, 0.0, "start", current_yaw, "", 0.0, scanned_tag_id]]
        
        total_dist, current_yaw, current_x, current_z, last_wp_dist = 0.0, 0.0, 0.0, 0.0, 0.0
        landmark_count = 0
        
        audio_queue.put({"type": "text", "msg": f"Tag {scanned_tag_id} detected. Anchor set. Start recording."})

    # ------------- 2. FINISH RECORDING (Post-Tag Scan) -------------------
    elif "finish" in cmd:
        # 🛑 HARD KILL: Stop all physical motor vibrations immediately for safety
        try:
            for zone in motor_map:
                for motor in motor_map[zone]:
                    motor.value = 0.0
        except: pass

        if len(recorded_path) > 0:
            # 🚀 APPEND FINAL DESTINATION (Retaining 7 Elements)
            recorded_path.append([current_x, current_z, "destination", current_yaw, "", total_dist, scanned_tag_id])
            
            file_path = os.path.join(DOC_PATH, f"{current_route_filename}.json")
            try:
                with open(file_path, "w") as f: 
                    json.dump(recorded_path, f, indent=4) 
                audio_queue.put({"type": "text", "msg": f"Tag {scanned_tag_id} scanned. Saving last point. Recording finished."})
            except Exception as e:
                print(f"Error saving: {e}")
        
        if STATE == "NAVIGATING":
            nav_engine.active = False
            audio_queue.put({"type": "text", "msg": "Navigation stopped."})
        STATE = "IDLE"

    # ------------- 3. STOP / ABORT -------------------
    elif "stop" in cmd:
        # 🛑 HARD KILL: Stop all physical motor vibrations immediately for safety
        try:
            for zone in motor_map:
                for motor in motor_map[zone]:
                    motor.value = 0.0
        except: pass

        global previous_state
        if previous_state == "RECORDING":
            audio_queue.put({"type": "text", "msg": "Recording not saved."})
        elif previous_state == "NAVIGATING":
            nav_engine.active = False
            audio_queue.put({"type": "text", "msg": "Navigation stopped."})
        STATE = "IDLE"

    # ------------- 4. START NAVIGATION (Retaining original logic) -------------------
    elif "go to" in cmd or "navigate" in cmd:
        dest_key, _ = get_ordinal_key(cmd)
        is_reverse = "reverse" in cmd

        if not dest_key:
            audio_queue.put({"type": "text", "msg": "Please specify a destination number."})
            STATE = "IDLE"
            return

        file_path = os.path.join(DOC_PATH, f"{dest_key}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as jf:
                    loaded_data = json.load(jf)
                
                if isinstance(loaded_data, list):
                    nav_path = loaded_data
                    
                    if is_reverse:
                        nav_path.reverse()
                        audio_queue.put({"type": "text", "msg": "Reversing route. Please turn around."})
                        first_node_yaw = nav_path[0][3] if len(nav_path[0]) > 3 else 0.0
                        current_yaw = (first_node_yaw + 180) % 360 - 180
                    else:
                        audio_queue.put({"type": "text", "msg": "Navigating."})
                        first_node_yaw = nav_path[0][3] if len(nav_path[0]) > 3 else 0.0
                        current_yaw = first_node_yaw
                        
                    STATE = "NAVIGATING"
                    total_dist, current_x, current_z = 0.0, 0.0, 0.0
                    nav_engine.load_path(nav_path)
                    
                    first_upd = nav_engine.get_instruction(0, 0, current_yaw, 0.0, is_on_demand=True)
                    if first_upd:
                        audio_queue.put({"type": "text", "msg": first_upd})

            except Exception as e:
                print(f"Load Error: {e}")
                audio_queue.put({"type": "text", "msg": "Failed to load destination data."})
        else:
            STATE = "IDLE"
            audio_queue.put({"type": "text", "msg": "Destination not found."})

def handle_voice_command(cmd):
    global STATE, pending_command, is_listening, recorded_path, landmark_count, current_x, current_z, current_yaw, previous_state
    global mic_stream, native_rate, mic_idx, audio_callback, rec, is_recording_note
    global pending_route_key, pending_route_alias

    cmd = cmd.lower().strip()
    if not cmd or cmd == "[unk]": return
    print(f"✅ Voice Input: {cmd} (State: {STATE})")

    # ---------------- IDLE & BASE LEVEL COMMANDS ---------------- #
    if STATE == "IDLE":
        if "identify" in cmd:
            key, num = get_ordinal_key(cmd)
            if key:
                mapping = {}
                if os.path.exists(ROUTE_MAP_FILE):
                    try:
                        with open(ROUTE_MAP_FILE, 'r') as f: mapping = json.load(f)
                    except: pass
                alias = mapping.get(key, "unnamed")
                speak_offline(f"Destination {num} is {alias}.")
            else:
                speak_offline("Destination not specified.")

        elif any(x in cmd for x in ["record", "go to", "navigate"]):
            pending_command = cmd
            STATE = "CONFIRM_START"
            speak_offline(f"You said {cmd}. Is this correct?")
            is_listening = True

    # ---------------- START WORKFLOW STATES ---------------- #
    elif STATE == "CONFIRM_START":
        if "yes" in cmd or "correct" in cmd:
            if "record" in pending_command:
                dest_key, _ = get_ordinal_key(pending_command)
                if dest_key:
                    pending_route_key = dest_key
                    STATE = "WAIT_DEST_NAME"
                    speak_offline("Please say the name for this destination.")
                    is_listening = True 
                else:
                    STATE = "IDLE"
                    speak_offline("Ordinal required, like record first destination. Cancelled.")
                    
            elif "go to" in pending_command or "navigate" in pending_command:
                # 🚀 NAVIGATE: Ask to scan tag instead of starting immediately
                global pending_tag_scan
                pending_tag_scan = "start_navigate"
                STATE = "WAITING_FOR_TAG"
                speak_offline("Turn around and scan the nearest tag in your current position.")
                # Do NOT set is_listening=True; the camera takes over now
            else:
                STATE = "IDLE"
                execute_action(pending_command)
        else: 
            STATE = "IDLE"
            speak_offline("Cancelled.")

    elif STATE == "WAIT_DEST_NAME":
        pending_route_alias = cmd
        STATE = "CONFIRM_DEST_NAME"
        speak_offline(f"You said {cmd}. Is this correct?")
        is_listening = True

    elif STATE == "CONFIRM_DEST_NAME":
        if "yes" in cmd or "correct" in cmd:
            # 🚀 RECORDING: Ask to scan tag before setting anchor
            pending_tag_scan = "start_record"
            STATE = "WAITING_FOR_TAG"
            speak_offline("Scan the nearest tag in your position.")
            # Do NOT set is_listening=True; the camera takes over now
        else:
            STATE = "WAIT_DEST_NAME"
            speak_offline("Please say the name for this destination again.")
            is_listening = True

    # ---------------- FINISH WORKFLOW STATES ---------------- #
    elif STATE == "CONFIRM_FINISH":
        if "yes" in cmd or "correct" in cmd: 
            if pending_command == "finish":
                # 🚀 FINISHING: Ask to scan tag before saving the JSON
                pending_tag_scan = "finish_record"
                STATE = "WAITING_FOR_TAG"
                speak_offline("Scan the nearest tag in your current position.")
            else:
                # If they were just saying "Stop" to cancel something, run it normally
                execute_action(pending_command)
        else: 
            STATE = previous_state
            speak_offline("Resuming.")
        pending_command = ""

    # ---------------- VOICE NOTE TRIGGER ---------------- #
    elif STATE == "CONFIRM_NOTE":
        if "yes" in cmd or "correct" in cmd:
            # 🚀 RESTORED: Trigger the ultra-safe main loop recorder
            global trigger_voice_note_record
            STATE = "RECORDING_NOTE"
            trigger_voice_note_record = True 
        else:
            STATE = "RECORDING"
            speak_offline("Continuing recording.")

    # ---------------- OPERATIONAL RECORDING ---------------- #
    elif STATE == "RECORDING":
        if "point" in cmd and "saved" in cmd:
            landmark_count += 1
            # 🚀 6 Elements: [X, Z, Label, Yaw, Note, Total_Dist]
            recorded_path.append([current_x, current_z, f"point_{landmark_count}", current_yaw, "", total_dist])
            STATE = "CONFIRM_NOTE"
            speak_offline(f"Point {landmark_count} saved. Do you want to add a voice note?")
            is_listening = True
            
        elif "finish" in cmd or "stop" in cmd:
            pending_command = "finish" if "finish" in cmd else "stop"
            previous_state = "RECORDING"
            STATE = "CONFIRM_FINISH"
            speak_offline(f"{pending_command.capitalize()} recording. Is this correct?")
            is_listening = True 
        
        else:
            speak_offline("Command not recognized. Say point saved, finish, or stop.")

    # ---------------- OPERATIONAL NAVIGATING ---------------- #
    elif STATE == "NAVIGATING":
        if "update" in cmd:
            status = nav_engine.get_instruction(current_x, current_z, current_yaw, total_dist, is_on_demand=True)
            if status: speak_offline(status)
        elif "pause" in cmd:
            STATE = "PAUSED"; speak_offline("Navigation paused.")
        elif "finish" in cmd or "stop" in cmd:
            pending_command = "stop"; previous_state = "NAVIGATING"; STATE = "CONFIRM_FINISH"
            speak_offline("Stop navigation. Is this correct?"); is_listening = True 
            
        else:
            speak_offline("Command not recognized. Say update, pause, or stop.")

    elif STATE == "PAUSED":
        if "resume" in cmd: 
            STATE = "NAVIGATING"
            speak_offline("Resuming navigation.")
        else:
            speak_offline("Navigation is paused. Say resume to continue.")

def trigger_listening():
    global is_listening
    if not is_speaking and not is_listening:
        is_listening = True
        print(" Listening...")
        speak_offline("Listening")

def get_pipeline():
    p = dai.Pipeline()
    
    # 1. RGB Camera
    cam = p.create(dai.node.ColorCamera)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam.setIspScale(2, 3) 
    cam.setPreviewSize(640, 640) 
    cam.setInterleaved(False)
    cam.setFps(15)
    
    # 🚀 FIXED FOCUS: Set manual focus to 0
    cam.initialControl.setManualFocus(0)
    
    # 2. Mono Cameras
    left = p.create(dai.node.MonoCamera)
    left.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    
    right = p.create(dai.node.MonoCamera)
    right.setBoardSocket(dai.CameraBoardSocket.CAM_C)
    right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    
    # 3. 🚀 OPTIMIZED STEREO DEPTH (No Warning)
    stereo = p.create(dai.node.StereoDepth)
    # Changed from HIGH_ACCURACY to DEFAULT to stop the warning
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    
    # Smoothing settings
    stereo.setExtendedDisparity(False) 
    stereo.setSubpixel(True) 
    stereo.setLeftRightCheck(True)
    stereo.initialConfig.setConfidenceThreshold(230) 
    stereo.initialConfig.setMedianFilter(dai.MedianFilter.KERNEL_7x7) 
    
    left.out.link(stereo.left); right.out.link(stereo.right)
    
    # 4. IMU
    imu = p.create(dai.node.IMU)
    imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 100)
    imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 100)
    imu.setBatchReportThreshold(1)
    
    # XLink Outputs
    x_isp = p.create(dai.node.XLinkOut); x_isp.setStreamName("isp"); cam.isp.link(x_isp.input)
    x_pre = p.create(dai.node.XLinkOut); x_pre.setStreamName("pre"); cam.preview.link(x_pre.input)
    x_dep = p.create(dai.node.XLinkOut); x_dep.setStreamName("depth"); stereo.depth.link(x_dep.input)
    x_imu = p.create(dai.node.XLinkOut); x_imu.setStreamName("imu"); imu.out.link(x_imu.input)
    
    return p

def play_sequence(inst):
    global is_speaking
    is_speaking = True
    
    # 1. Announce Arrival
    print(f"🔊 Sequence: Reached {inst['label']}")
    cmd_msg = f'echo "Reached {inst["label"]}." | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | aplay -D default -r 22050 -f S16_LE -t raw'
    subprocess.run(cmd_msg, shell=True)
    
    time.sleep(0.5)
    
    # 2. Play the arrival WAV
    note = inst["note_file"]
    if note and note.endswith(".wav"):
        note_path = os.path.join(DOC_PATH, note)
        if os.path.exists(note_path):
            print(f"🔊 Sequence: Playing {note_path}")
            # 🚀 FIX: Use -D default for guaranteed hardware access
            subprocess.run(['aplay', '-D', 'default', '-q', note_path])
            
    # 3. Announce Next Turn
    if inst.get("next_instruction"):
        print(f"🔊 Sequence: {inst['next_instruction']}")
        cmd_turn = f'echo "{inst["next_instruction"]}" | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | aplay -D default -r 22050 -f S16_LE -t raw'
        subprocess.run(cmd_turn, shell=True)
    
    is_speaking = False
#---------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------

def run():
    global total_dist, current_yaw, last_wp_dist, recorded_path, nav_path, is_listening, is_speaking, STATE, current_x, current_z
    global mic_stream, native_rate, mic_idx, audio_callback, rec, vosk_model
    global trigger_voice_note_record
    global is_ticking
    
    tick_confidence = 0 
    TICK_THRESHOLD_START = 10 # Frames of clear path needed to START ticking
    TICK_THRESHOLD_STOP = 3   # Frames of blockage needed to STOP ticking (faster for safety)
    
    # --- EXPLORATION CONSTANTS ---
    CENTER_CLEAR_METERS = 2.0  # Must be 2m clear to play centering tick
    SIDE_OPEN_METERS = 2.5    # Threshold to announce a side aisle
    AISLE_CONFIRM_FRAMES = 12 # Stability check before speaking
    # Exploration Stability Vars
    wall_frames = 0
    dead_end_frames = 0
    left_confirm = 0
    right_confirm = 0
    aisle_cooldown = 0
    is_ticking = False
    trigger_voice_note_record = False
    
    # 🚀 INITIALIZE LOCAL HAPTIC SOCKET BRIDGE
    import socket
    haptic_sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    UDP_TARGET = ('127.0.0.1', 5005)
    
    # 1. INITIALIZE CORE VARIABLES
    curr_yaw, curr_pitch, curr_roll = 0.0, 0.0, 0.0
    smooth_yaw = 0.0 
    gx, gy, gz = 0.0, 0.0, 0.0 
    last_imu_t = None
    motion_window = [] 
    warmup_frames = 0
    
    # 🚀 HAPTIC HARDWARE INITIALIZATION
    try:
        m1 = PWMOutputDevice(17); m2 = PWMOutputDevice(27) # Left
        m3 = PWMOutputDevice(22); m4 = PWMOutputDevice(23) # Center
        m5 = PWMOutputDevice(24); m6 = PWMOutputDevice(25) # Right
        motor_map = {"L": [m1, m2], "C": [m3, m4], "R": [m5, m6]}
    except Exception as e:
        print(f"⚠️ Haptic Error: {e}"); motor_map = {"L":[], "C":[], "R":[]}

    print("⏳ Loading Vosk & Hailo NPU...")
    vosk_model = vosk.Model(VOSK_MODEL_PATH)
    rec = vosk.KaldiRecognizer(vosk_model, 16000, json.dumps(ALLOWED_WORDS))
    
    try:
        import hailo_platform
        hailo_platform.pyhailort.pyhailort.VDevice.release_all_devices()
    except: pass
    
    target = VDevice(); hef = HEF(HEF_PATH)
    conf = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
    group = target.configure(hef, conf)[0]
    in_p = InputVStreamParams.make(group, format_type=FormatType.UINT8)
    out_p = OutputVStreamParams.make(group, format_type=FormatType.FLOAT32)
    input_name = hef.get_input_vstream_infos()[0].name
    
    if btn: btn.when_pressed = trigger_listening
    
    try:
        mic_stream = sd.InputStream(samplerate=native_rate, device=mic_idx, channels=1, dtype='float32', blocksize=4000, callback=audio_callback)
        mic_stream.start()
    except: pass

    with dai.Device(get_pipeline()) as device:
        q_isp = device.getOutputQueue("isp", 4, False)
        q_pre = device.getOutputQueue("pre", 4, False)
        q_dep = device.getOutputQueue("depth", 4, False)
        q_imu = device.getOutputQueue("imu", 20, False)
        
        with group.activate():
            with InferVStreams(group, in_p, out_p) as pipe:
                print("✅ SENSEY Exploration Engine Ready.")
                
                while True:
                    # 🚀 A. FRAME FETCHING (ISP + Depth are 1280x720, Preview is 640x640)
                    rgb_isp = q_isp.get().getCvFrame()   
                    rgb_pre = q_pre.get().getCvFrame()   
                    depth_raw = q_dep.get().getFrame()   

                    # 🚀 B. HAILO INFERENCE (Object Detection)
                    res = pipe.infer({input_name: np.expand_dims(rgb_pre, axis=0)})
                    raw_dets = list(res.values())[0]
                    active_boxes = []
                    
                    if len(raw_dets) > 0:
                        detections_list = raw_dets[0]
                        for class_list in detections_list:
                            for det in class_list:
                                if len(det) >= 5 and det[4] > 0.45:
                                    ymin, xmin, ymax, xmax = det[:4]
                                    # Map 640x640 detection back to 1280x720 visualizer
                                    bx1 = int(xmin * 640) + 320
                                    by1 = int(ymin * 640) + 40
                                    bx2 = int(xmax * 640) + 320
                                    by2 = int(ymax * 640) + 40
                                    active_boxes.append([bx1, by1, bx2, by2])

                    # 🚀 C. SPATIAL MATH (L, C, R Zones)
                    H, W = 720, 1280
                    w_third = W // 3
                    h_mid = H // 2
                    slice_depth = depth_raw[h_mid-100:h_mid+100, :]
                    
                    def get_dist(zone):
                        valid = zone[zone > 200]
                        return np.median(valid) / 1000.0 if valid.size > 0 else 0.0

                    l_dist = get_dist(slice_depth[:, 0:w_third])
                    c_dist = get_dist(slice_depth[:, w_third:2*w_third])
                    r_dist = get_dist(slice_depth[:, 2*w_third:W])

                    # 🚀 D. ENVIRONMENTAL GEOMETRY (Wall & Dead End)
                    is_flat = (abs(l_dist - c_dist) < 0.15) and (abs(r_dist - c_dist) < 0.15)
                    detected_wall = (c_dist < 1.5) and (c_dist > 0.3) and is_flat
                    detected_dead_end = (l_dist < 1.1) and (c_dist < 1.1) and (r_dist < 1.1) and not is_flat

                    if detected_wall: wall_frames += 1
                    else: wall_frames = 0
                        
                    if detected_dead_end: dead_end_frames += 1
                    else: dead_end_frames = 0

                    # 🚀 E. VIRTUAL RAIL (Audio Tick Stability)
                    is_path_physically_clear = (c_dist > CENTER_CLEAR_THRESHOLD) and not detected_wall and not detected_dead_end
                    
                    if is_path_physically_clear:
                        tick_confidence = min(tick_confidence + 1, TICK_THRESHOLD_START)
                    else:
                        tick_confidence = max(tick_confidence - 2, 0)

                    if tick_confidence >= TICK_THRESHOLD_START: stable_tick_trigger = True
                    elif tick_confidence <= 0: stable_tick_trigger = False
                    else: stable_tick_trigger = is_ticking

                    if stable_tick_trigger:
                        if not is_ticking: tick_sound_effect.play(loops=-1); is_ticking = True
                    else:
                        if is_ticking: tick_sound_effect.stop(); is_ticking = False

                    # Duck tick volume when AI speaks
                    tick_sound_effect.set_volume(0.3 if is_speaking else 1.0)

                    # 🚀 F. EXPLORATION ANNOUNCEMENTS
                    if aisle_cooldown > 0:
                        aisle_cooldown -= 1
                    else:
                        if wall_frames > 15:
                            audio_queue.put({"type": "text", "msg": "Facing a wall."})
                            aisle_cooldown = 150; wall_frames = 0
                        elif dead_end_frames > 15:
                            audio_queue.put({"type": "text", "msg": "Dead end detected."})
                            aisle_cooldown = 150; dead_end_frames = 0
                        elif l_dist > SIDE_OPENING_THRESHOLD:
                            left_confirm += 1
                            if left_confirm > AISLE_CONFIRM_FRAMES:
                                audio_queue.put({"type": "text", "msg": "Aisle detected on left."})
                                aisle_cooldown = 150; left_confirm = 0
                        elif r_dist > SIDE_OPENING_THRESHOLD:
                            right_confirm += 1
                            if right_confirm > AISLE_CONFIRM_FRAMES:
                                audio_queue.put({"type": "text", "msg": "Aisle detected on right."})
                                aisle_cooldown = 150; right_confirm = 0

                    # 🚀 G. SIDE-BY-SIDE VISUALIZER (The "CV Window" fix)
                    # Normalize depth 0-5m for JET colormap
                    depth_clipped = np.clip(depth_raw, 0, 5000)
                    depth_norm = (depth_clipped / 5000.0 * 255).astype(np.uint8)
                    depth_inverted = cv2.bitwise_not(depth_norm)
                    depth_vis = cv2.applyColorMap(depth_inverted, cv2.COLORMAP_JET)
                    depth_vis[depth_raw == 0] = [0, 0, 0] # Black for no-data

                    # Draw Zone Separators
                    for img in [rgb_isp, depth_vis]:
                        cv2.line(img, (w_third, 0), (w_third, H), (255, 255, 255), 1)
                        cv2.line(img, (2*w_third, 0), (2*w_third, H), (255, 255, 255), 1)

                    # Create combined display
                    combined = np.hstack((rgb_isp, depth_vis))
                    display = cv2.resize(combined, (1280, 480))
                    
                    # HUD Text
                    conf_bar = "|" * tick_confidence
                    if wall_frames > 0: status_txt = f"WALL {wall_frames}"
                    elif dead_end_frames > 0: status_txt = f"DEAD END {dead_end_frames}"
                    elif is_ticking: status_txt = f"RAIL ACTIVE {conf_bar}"
                    else: status_txt = f"BLOCKAGE {conf_bar}"

                    cv2.rectangle(display, (0,0), (500, 50), (0,0,0), -1)
                    cv2.putText(display, status_txt, (10, 35), 0, 0.7, (0, 255, 0), 2)
                    cv2.putText(display, f"L:{l_dist:.1f}m C:{c_dist:.1f}m R:{r_dist:.1f}m", (10, 460), 0, 0.7, (255, 255, 255), 2)
                    
                    # 🚀 THE SHOW COMMANDS
                    cv2.imshow("SENSEY Exploration Engine", display)
                    if cv2.waitKey(1) == ord('q'):
                        break
                        
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run()