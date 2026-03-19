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
    """🚀 THE SINGLE-THREADED AUDIO MANAGER (Uses custom .wav files)"""
    while True:
        cmd = audio_queue.get()
        if cmd['type'] == 'text':
            print(f"\n[SPEECH SYSTEM] 🔊: {cmd['msg']}\n")
            cmd_string = f'echo "{cmd["msg"]}" | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | paplay --raw --format=s16le --rate=22050 --channels=1'
            subprocess.run(cmd_string, shell=True)
            
        elif cmd['type'] == 'wav':
            # Play a specific voice note file via pygame (non-blocking)
            if os.path.exists(cmd['path']):
                sound = pygame.mixer.Sound(cmd['path'])
                sound.play()
                time.sleep(sound.get_length())
            
        elif cmd['type'] == 'beep':
            # 🚀 FIX: Plays your custom recording_notes.wav
            if start_beep_sound: 
                start_beep_sound.play()
                time.sleep(start_beep_sound.get_length())
                
        elif cmd['type'] == 'arrival':
            # 🚀 FIX: Plays your custom arrived_destination.wav
            if arrival_sound:
                arrival_sound.play()
                time.sleep(arrival_sound.get_length())
        
        elif cmd['type'] == 'tag_chime':
            # 🚀 Play the confirmation chime when a tag is scanned
            chime_path = "/home/raspberrypi/TTS-STT-AUDIO/tag_voice_notes.wav"
            if os.path.exists(chime_path):
                sound = pygame.mixer.Sound(chime_path)
                sound.play()
                # We don't sleep here so it acts as a background chime
                
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

    def load_path(self, path_data):
        """🚀 CLEW AUTO-TURN LOGIC"""
        raw_nodes = []
        for p in path_data:
            label = str(p[2]).lower()
            node_type = "ANCHOR" if ("point" in label or "destination" in label or "start" in label) else "PATH"
            raw_nodes.append({
                "x": p[0], "z": p[1], "type": node_type, "label": p[2], 
                "yaw": p[3] if len(p) > 3 else 0.0,
                "note": p[4] if len(p) > 4 else "",
                "total_dist": p[5] if len(p) > 5 else 0.0 
            })
        
        self.path = [raw_nodes[0]] 
        for i in range(1, len(raw_nodes) - 1):
            prev, curr, next_n = raw_nodes[i-1], raw_nodes[i], raw_nodes[i+1]
            
            # Distance from previous saved point
            seg_dist = math.sqrt((curr['x'] - self.path[-1]['x'])**2 + (curr['z'] - self.path[-1]['z'])**2)
            
            # 🚀 THE FIX: Ignore points that are physically in the exact same spot!
            # If the distance is less than 10cm, it's just a "Turn-in-place" breadcrumb.
            if seg_dist < 0.1 and curr['note'] == "" and curr['type'] == "PATH":
                continue

            angle1 = math.atan2(curr['x'] - prev['x'], curr['z'] - prev['z'])
            angle2 = math.atan2(next_n['x'] - curr['x'], next_n['z'] - curr['z'])
            diff = abs(math.degrees(angle2 - angle1 + math.pi) % 360 - 180)
            
            if seg_dist > 0.6 or diff > 30 or curr['note'] != "":
                self.path.append(curr)
        
        self.path.append(raw_nodes[-1]) 
        self.active = True
        self.current_wp_index = 1 if len(self.path) > 1 else 0
        self.offset_x, self.offset_z, self.offset_yaw = 0, 0, 0

    def get_instruction(self, cur_x, cur_z, cur_yaw, is_on_demand=False):
        global STATE
        if not self.active or self.current_wp_index >= len(self.path): return None
        
        target = self.path[self.current_wp_index]
        tx, tz = target["x"] + self.offset_x, target["z"] + self.offset_z
        self.distance_to_wp = math.sqrt((tx - cur_x)**2 + (tz - cur_z)**2)
        
        # HUD YAW LOCK
        if self.distance_to_wp > 0.1:
            self.target_yaw = (math.degrees(math.atan2(tx - cur_x, tz - cur_z)) + self.offset_yaw) % 360

        if is_on_demand:
            # 🚀 ON DEMAND: Calculate the FULL distance to the next Anchor
            total_dist = self.distance_to_wp
            next_idx = self.current_wp_index
            prev_x, prev_z = tx, tz
            
            for i in range(self.current_wp_index + 1, len(self.path)):
                p = self.path[i]
                p_x, p_z = p["x"] + self.offset_x, p["z"] + self.offset_z
                total_dist += math.sqrt((p_x - prev_x)**2 + (p_z - prev_z)**2)
                prev_x, prev_z = p_x, p_z
                if p["type"] == "ANCHOR":
                    next_idx = i
                    break
                    
            turn_err = (self.target_yaw - cur_yaw + 180) % 360 - 180
            dist_str = f"{total_dist:.2f}"
            
            # 🚀 STRICT 4-RULE PHRASING (On Demand)
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
            node_type = target['type']
            note = target['note']
            
            self.current_wp_index += 1
            
            if self.current_wp_index >= len(self.path):
                self.active = False
                STATE = "IDLE"
                audio_queue.put({"type": "wav", "path": "/home/raspberrypi/TTS-STT-AUDIO/arrived_destination02.wav"})
                audio_queue.put({"type": "text", "msg": "Arrived at destination."})
                return None
            
            if node_type == "ANCHOR" or note:
                audio_queue.put({"type": "beep"})
                audio_queue.put({"type": "text", "msg": f"Reached {node_label}."})
                if note and note.endswith(".wav"):
                    audio_queue.put({"type": "wav", "path": os.path.join(DOC_PATH, note)})
                
                # 🚀 THE FIX: Calculate distance using the 1D total_dist tracker
                next_dist = 0.0
                next_yaw = cur_yaw
                
                # Current node we just arrived at
                current_node_dist = target["total_dist"]
                
                for i in range(self.current_wp_index, len(self.path)):
                    p = self.path[i]
                    if p["type"] == "ANCHOR" or i == len(self.path) - 1:
                        # 🚀 Exact walking distance!
                        next_dist = p["total_dist"] - current_node_dist 
                        
                        p_x, p_z = p["x"] + self.offset_x, p["z"] + self.offset_z
                        next_yaw = (p["yaw"] + self.offset_yaw) % 360 if p["type"] == "ANCHOR" else math.degrees(math.atan2(p_x - tx, p_z - tz)) % 360
                        break
                
                turn_err = (next_yaw - cur_yaw + 180) % 360 - 180
                dist_str = f"{next_dist:.2f}"
                
                # 🚀 STRICT 4-RULE PHRASING (Upon Arrival)
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
        # 🚀 THE FIX: For HUD, simply subtract where we are from where the goal is
        if not self.active or self.current_wp_index >= len(self.path): return 0.0
        target = self.path[self.current_wp_index]
        return max(0.0, target["total_dist"] - current_total_dist)

nav_engine = NavigationManager()

def play_navigation_tick(current_yaw, target_yaw, screen_width=1024):
    global is_ticking
    if target_yaw is None or STATE != "NAVIGATING":
        if is_ticking: 
            tick_sound_effect.stop()
            is_ticking = False
        return
        
    pixels_per_degree = screen_width / 90
    relative_angle = (target_yaw - current_yaw + 180) % 360 - 180
    arrow_x = (screen_width // 2) + int(relative_angle * pixels_per_degree)
    
    # 🚀 BOUNDARY: Center 1/3 only
    l_lim, r_lim = screen_width // 3, 2 * screen_width // 3
    
    if l_lim <= arrow_x <= r_lim:
        if not is_ticking: 
            tick_sound_effect.play(loops=-1)
            is_ticking = True
    else:
        if is_ticking: 
            tick_sound_effect.stop()
            is_ticking = False

def speak_offline(text):
    global is_speaking
    if not text.strip(): return
    
    print(f"\n[SPEECH SYSTEM] 🔊: {text}\n")
    
    def _speak_thread():
        global is_speaking
        is_speaking = True
        # 🚀 FIX: Changed to paplay
        cmd = f'echo "{text}" | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | paplay --raw --format=s16le --rate=22050 --channels=1'
        subprocess.run(cmd, shell=True)
        is_speaking = False
        
    threading.Thread(target=_speak_thread, daemon=True).start()

def execute_action(cmd):
    global STATE, recorded_path, nav_path, total_dist, current_yaw, last_wp_dist, current_route_filename, landmark_count, current_x, current_z, nav_engine
    global pending_route_key, pending_route_alias
    
    print(f"DEBUG: execute_action received '{cmd}'. Current STATE: {STATE}")
    
    # ------------- ALIAS RECORD SAVER -------------------
    if cmd == "start_recording_dest":
        STATE = "RECORDING"
        current_route_filename = pending_route_key
        
        mapping = {}
        if os.path.exists(ROUTE_MAP_FILE):
            try:
                with open(ROUTE_MAP_FILE, 'r') as f: 
                    mapping = json.load(f)
            except Exception as e:
                pass
                
        mapping[pending_route_key] = pending_route_alias
        
        with open(ROUTE_MAP_FILE, 'w') as f: 
            json.dump(mapping, f, indent=4) 

        # 🚀 6 Elements: [X, Z, Label, Yaw, Note, Total_Dist]
        # We record the ACTUAL current_yaw here
        recorded_path = [[0.0, 0.0, "start", current_yaw, "", 0.0]]
        
        # 🚀 THE FIX: DO NOT reset current_yaw to 0.0 here! 
        # Keep the Global Compass intact!
        total_dist, current_x, current_z, last_wp_dist = 0.0, 0.0, 0.0, 0.0
        
        landmark_count = 0
        speak_offline(f"Recording. Anchor set.")

    # 🚀 FIX: Distinct 'FINISH' routing natively ignores state to properly write output
    elif "finish" in cmd:
        if len(recorded_path) > 0:
            # 🚀 Append the final destination with all 6 elements!
            recorded_path.append([current_x, current_z, "destination", current_yaw, "", total_dist])
            
            file_path = os.path.join(DOC_PATH, f"{current_route_filename}.json")
            
            try:
                with open(file_path, "w") as f: 
                    json.dump(recorded_path, f, indent=4) 
                print(f"DEBUG: Successfully stored route locally to {file_path}")    
                speak_offline("Saving last point. Recording finished.")
            except Exception as e:
                print(f"Error saving route: {e}")
        
        # If we were navigating, stop it
        if STATE == "NAVIGATING":
            nav_engine.active = False
            speak_offline("Navigation stopped.")
            
        STATE = "IDLE"

    # 🚀 SEPARATE "STOP" LOGIC (CANCEL RECORDING) 
    elif "stop" in cmd:
        # 🚀 Use previous_state to know what we were actually stopping
        global previous_state
        if previous_state == "RECORDING":
            print(f"DEBUG: Purged active pathway. Aborting active routes!")
            speak_offline("Recording not saved.")
        elif previous_state == "NAVIGATING":
            nav_engine.active = False
            speak_offline("Navigation stopped.")
        
        STATE = "IDLE"

    elif "go to" in cmd or "navigate" in cmd:
        dest_key, _ = get_ordinal_key(cmd)
        is_reverse = "reverse" in cmd

        if not dest_key:
            speak_offline("Please specify an ordinal destination.")
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
                        # 🚀 REVERSE FIX: Set current_yaw to the EXACT OPPOSITE of the starting heading
                        first_node_yaw = nav_path[0][3] if len(nav_path[0]) > 3 else 0.0
                        current_yaw = (first_node_yaw + 180) % 360 - 180
                    else:
                        audio_queue.put({"type": "text", "msg": "Navigating."})
                        # 🚀 FORWARD FIX: Set current_yaw to the exact heading recorded at the start
                        first_node_yaw = nav_path[0][3] if len(nav_path[0]) > 3 else 0.0
                        current_yaw = first_node_yaw
                        
                    STATE = "NAVIGATING"
                    
                    # 🚀 THE FIX: DO NOT reset current_yaw to 0.0 here either!
                    total_dist, current_x, current_z = 0.0, 0.0, 0.0
                    
                    nav_engine.load_path(nav_path)
                    
                    # 🚀 The first update will now always say "Walk straight" because 
                    # we forced current_yaw to match the target_yaw!
                    first_upd = nav_engine.get_instruction(0, 0, current_yaw, is_on_demand=True)
                    if first_upd:
                        audio_queue.put({"type": "text", "msg": first_upd})

            except Exception as e:
                speak_offline("Failed to load destination data.")
        else:
            STATE = "IDLE"
            speak_offline("Destination not found.")

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
            STATE = "IDLE" 
            pending_command = "" 
            execute_action("start_recording_dest") 
        else:
            STATE = "WAIT_DEST_NAME"
            speak_offline("Please say the name for this destination again.")
            is_listening = True

    # ---------------- FINISH WORKFLOW STATES ---------------- #
    elif STATE == "CONFIRM_FINISH":
        if "yes" in cmd or "correct" in cmd: 
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
            status = nav_engine.get_instruction(current_x, current_z, current_yaw, is_on_demand=True)
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
    feat.setHardwareResources(2, 2)
    feat.initialConfig.setNumTargetFeatures(500)
    left.out.link(feat.inputImage)
    
    # 🚀 FIX: Correct link for AprilTag node (Must be inputImage)
    april = p.create(dai.node.AprilTag)
    april.initialConfig.setFamily(dai.AprilTagConfig.Family.TAG_36H11)
    left.out.link(april.inputImage) 
    
    # XLinkOuts
    x_isp = p.create(dai.node.XLinkOut); x_isp.setStreamName("isp"); cam.isp.link(x_isp.input)
    x_pre = p.create(dai.node.XLinkOut); x_pre.setStreamName("pre"); cam.preview.link(x_pre.input)
    x_dep = p.create(dai.node.XLinkOut); x_dep.setStreamName("depth"); stereo.depth.link(x_dep.input)
    x_imu = p.create(dai.node.XLinkOut); x_imu.setStreamName("imu"); imu.out.link(x_imu.input)
    x_fea = p.create(dai.node.XLinkOut); x_fea.setStreamName("feat"); feat.outputFeatures.link(x_fea.input)
    x_apr = p.create(dai.node.XLinkOut); x_apr.setStreamName("april"); april.out.link(x_apr.input)
    
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
# 🚀 8-Tag Cardinal Map (Tag ID : World Yaw)
# Updated to match the -180 to +180 format used by the IMU
TAG_MAP = {
    0: 0.0,      # North (Front Board)
    1: 45.0,     # North-East
    2: 90.0,     # East (Right Wall)
    3: 135.0,    # South-East
    4: 180.0,    # South (Back Door) - Can be 180 or -180
    5: -135.0,   # South-West (Previously 225.0)
    6: -90.0,    # West (Left Wall) (Previously 270.0)
    7: -45.0     # North-West (Previously 315.0)
}

# 🚀 Tag ID to Human Name Map for the Visualizer
TAG_NAMES = {
    0: "North",
    1: "North-East",
    2: "East",
    3: "South-East",
    4: "South",
    5: "South-West",
    6: "West",
    7: "North-West"
}

def handle_april_tags(april_data, current_yaw, current_x, current_z, depth_frame, display_frame):
    """
    🚀 UNIFIED APRILTAG SNAP: Now returns a list of successfully snapped tags.
    """
    l_lim = (640 * 0.33) + 50
    r_lim = (640 * 0.66) + 50
    scale_x = 1344 / 640
    scale_y = 1008 / 480
    
    snapped_tags = [] # 🚀 Track which tags were valid this frame

    for det in april_data.aprilTags:
        if det.id in TAG_MAP:
            cx_mono = (det.topLeft.x + det.topRight.x + det.bottomRight.x + det.bottomLeft.x) / 4
            cy_mono = (det.topLeft.y + det.topRight.y + det.bottomRight.y + det.bottomLeft.y) / 4
            dx, dy = int(cx_mono * scale_x), int(cy_mono * scale_y)
            
            if 0 <= dy < 1008 and 0 <= dx < 1344:
                z_meters = depth_frame[dy, dx] / 1000.0
                
                # Visualizer (Purple Box)
                pt1 = (int(det.topLeft.x * scale_x), int(det.topLeft.y * scale_y))
                pt2 = (int(det.topRight.x * scale_x), int(det.topRight.y * scale_y))
                pt3 = (int(det.bottomRight.x * scale_x), int(det.bottomRight.y * scale_y))
                pt4 = (int(det.bottomLeft.x * scale_x), int(det.bottomLeft.y * scale_y))
                pts = np.array([pt1, pt2, pt3, pt4], np.int32)
                cv2.polylines(display_frame, [pts], True, (255, 0, 255), 2)
                
                tag_name = TAG_NAMES.get(det.id, "Unknown")
                cv2.putText(display_frame, f"TAG {det.id} ({tag_name}) | {z_meters:.1f}m", 
                            (pt1[0], pt1[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)

                # --- THE SNAP LOGIC ---
                if l_lim < cx_mono < r_lim:
                    if 0.5 < z_meters < 3.0:
                        target_world_yaw = TAG_MAP[det.id]
                        # Only snap if there is actual drift (> 2 degrees)
                        if abs((target_world_yaw - current_yaw + 180) % 360 - 180) > 2.0:
                            current_yaw = target_world_yaw
                            print(f"⚓ ANCHOR SNAPPED! {tag_name} (Tag {det.id}) at {z_meters:.1f}m.")
                        
                        # 🚀 Even if we didn't drift, we still "saw" it perfectly
                        snapped_tags.append(det.id)
                            
    return current_yaw, current_x, current_z, snapped_tags
#--------------------------------------------------------------------------------------------------------------------

def run():
    global total_dist, current_yaw, last_wp_dist, recorded_path, nav_path, is_listening, is_speaking, STATE, current_x, current_z
    global mic_stream, native_rate, mic_idx, audio_callback, rec, vosk_model
    global trigger_voice_note_record
    global is_ticking # 🚀 FIX: Add this line right here!
    trigger_voice_note_record = False
    
    # 🚀 INITIALIZE LOCAL HAPTIC SOCKET BRIDGE
    import socket
    haptic_sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    UDP_TARGET = ('127.0.0.1', 5005)
    
    # 🚀 1. INITIALIZE CORE VARIABLES
    curr_yaw, curr_pitch, curr_roll = 0.0, 0.0, 0.0
    smooth_yaw = 0.0 
    gx, gy, gz = 0.0, 0.0, 0.0 
    last_imu_t = None
    feat_history = {} 
    motion_window = [] 
    pixel_path_history = {} 

    # Calibration & Configuration
    CALIBRATION_SCALE = 1.66 # Adjusts optical flow to physical meters
    warmup_frames = 0
    hud_dist = 0.0
    PERSON_CLASS_ID = 0
    tag_cooldowns = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0}

    
    print("⏳ Loading Vosk...")
    vosk_model = vosk.Model(VOSK_MODEL_PATH)
    rec = vosk.KaldiRecognizer(vosk_model, 16000, json.dumps(ALLOWED_WORDS))
    
    print("⏳ Loading Hailo NPU...")
    # Add try/except to catch hardware lockouts
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
    
    try: btn = Button(26, pull_up=True); btn.when_pressed = trigger_listening
    except: btn = None
    
    devices = sd.query_devices()
    mic_idx, native_rate = 0, 44100
    for i, dev in enumerate(devices):
        if "USB" in dev['name']: mic_idx, native_rate = i, int(dev['default_samplerate']); break
            
    def audio_callback(indata, frames, time_info, status):
        global is_listening, is_speaking, is_recording_note, voice_note_buffer
        
        # 🚀 THE SPONGE: Only captures data, no longer manages the timer
        if is_recording_note:
            audio_int16 = (indata.copy() * 32767).astype(np.int16)
            voice_note_buffer.append(audio_int16)
            return
            
        if not is_listening or is_speaking: return
        
        try:
            mono_data = np.mean(indata, axis=1) if indata.shape[1] > 1 else indata.flatten()
            audio = (mono_data * 32768).astype('int16')
            num_s = int(len(audio) * 16000 / native_rate)
            resampled = audio[np.linspace(0, len(audio) - 1, num_s).astype(int)]
            if rec.AcceptWaveform(resampled.tobytes()):
                result = json.loads(rec.Result()); cmd = result.get('text', '')
                if cmd: 
                    is_listening = False
                    threading.Thread(target=handle_voice_command, args=(cmd,), daemon=True).start()
                    rec.Reset()
        except Exception as e:
            pass

    button_was_pressed = False

    with dai.Device(get_pipeline()) as device:
        try:
            mic_stream = sd.InputStream(samplerate=native_rate, device=mic_idx, channels=1, dtype='float32', blocksize=4000, callback=audio_callback)
            mic_stream.start()
        except: pass

        q_isp = device.getOutputQueue("isp", 4, False)
        q_pre = device.getOutputQueue("pre", 4, False)
        q_dep = device.getOutputQueue("depth", 4, False)
        q_imu = device.getOutputQueue("imu", 20, False)
        q_fea = device.getOutputQueue("feat", 4, False)
        q_apr = device.getOutputQueue("april", 4, False) # 🚀 APRILTAG QUEUE
        
        with group.activate():
            with InferVStreams(group, in_p, out_p) as pipe:
                print("✅ SENSEY Ready."); speak_offline("System Ready.")
                
                while True:
                    # 🚀 A. SAFE HARDWARE HANDOVER FOR VOICE NOTES
                    if trigger_voice_note_record:
                        trigger_voice_note_record = False
                        print("🔊 Prompting: Start")
                        
                        # Use subprocess for synchronous Piper so we wait for it to finish
                        subprocess.run(f'echo "Start" | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | aplay -D default -r 22050 -f S16_LE -t raw > /dev/null 2>&1', shell=True) 
                        
                        try:
                            mic_stream.stop(); mic_stream.close()
                            time.sleep(0.5) 
                        except: pass
                        
                        note_filename = f"{current_route_filename}_note_{landmark_count}.wav"
                        note_path = os.path.join(DOC_PATH, note_filename)
                        print(f"🎙️ Recording 5s: {note_filename}")
                        
                        # 🚀 FIX: Use audio_queue to trigger your custom recording_notes.wav
                        audio_queue.put({"type": "beep"})
                        time.sleep(1.0) # Wait for the custom beep to finish
                        
                        try:
                            subprocess.run(['arecord', '-d', '5', '-f', 'S16_LE', '-r', '44100', '-c', '1', note_path], check=True)
                            if len(recorded_path) > 0: recorded_path[-1][4] = note_filename
                        except Exception as e: print(f"🔴 arecord Error: {e}")
                        
                        # 🚀 FIX: Use audio_queue for the ending beep
                        audio_queue.put({"type": "beep"})
                        time.sleep(1.0) # Wait for the custom beep to finish
                        
                        subprocess.run(f'echo "Voice note saved. Continue recording." | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | aplay -D default -r 22050 -f S16_LE -t raw > /dev/null 2>&1', shell=True)
                        
                        try:
                            rec.Reset()
                            mic_stream = sd.InputStream(samplerate=native_rate, device=mic_idx, channels=1, dtype='float32', blocksize=4000, callback=audio_callback)
                            mic_stream.start()
                        except: pass
                        STATE = "RECORDING"
                        continue

                    if btn and btn.is_pressed:
                        if not button_was_pressed: button_was_pressed = True; trigger_listening()
                    else: button_was_pressed = False
                    rotation_cooldown = 0 # 🚀 NEW: Timer to let the camera settle after a turn

                    # 🚀 1. IMU STEP DETECTOR & SMOOTH YAW
                    imuData = q_imu.tryGetAll() 
                    is_stepping = False
                    for data in imuData:
                        for packet in data.packets:
                            ts = packet.acceleroMeter.timestamp.get().total_seconds()
                            if last_imu_t is None: last_imu_t = ts; continue
                            dt = ts - last_imu_t; last_imu_t = ts
                            
                            ax, ay, az = packet.acceleroMeter.x, packet.acceleroMeter.z, packet.acceleroMeter.y
                            gx, gy, gz = packet.gyroscope.x, packet.gyroscope.z, packet.gyroscope.y
                            
                            accel_mag = math.sqrt(ax**2 + ay**2 + az**2)
                            if abs(accel_mag - 9.81) > 0.25: is_stepping = True

                            current_yaw -= (gz * (180.0 / math.pi) * dt)
                            curr_pitch = 0.98 * (curr_pitch + gx * (180.0/math.pi) * dt) + 0.02 * math.degrees(math.atan2(ay, math.sqrt(ax**2 + az**2)))
                            curr_roll = 0.98 * (curr_roll + gy * (180.0/math.pi) * dt) + 0.02 * math.degrees(math.atan2(ax, az))
                            current_yaw = (current_yaw + 180) % 360 - 180
                            smooth_yaw = (0.8 * smooth_yaw) + (0.2 * current_yaw)

                    # 🚀 2. FETCH SENSOR FRAMES
                    rgb_isp = q_isp.get().getCvFrame()
                    rgb_pre = q_pre.get().getCvFrame() 
                    depth_raw = q_dep.get().getFrame()
                    fea_data = q_fea.get().trackedFeatures

                    # 🚀 4. APRILTAG LOCALIZATION
                    april_in = q_apr.tryGet()
                    if april_in:
                        current_yaw, current_x, current_z, snapped_tags = handle_april_tags(
                            april_in, current_yaw, current_x, current_z, depth_raw, rgb_isp
                        )
                        
                        # 🚀 PLAY CHIME WITH 3-SECOND COOLDOWN
                        current_time = time.time()
                        for tag_id in snapped_tags:
                            # If 3 seconds have passed since we last chimed for THIS specific tag
                            if current_time - tag_cooldowns[tag_id] > 5.0:
                                audio_queue.put({"type": "tag_chime"})
                                print(f"🔔 Chime played for Tag {tag_id}")
                            
                            # Always update the timer so the 3-second cooldown keeps resetting 
                            # as long as they are staring at it.
                            tag_cooldowns[tag_id] = current_time

                    # 🚀 4. AI INFERENCE & MASKING BOXES
                    res = pipe.infer({input_name: np.expand_dims(rgb_pre, axis=0)})
                    raw_dets = list(res.values())[0]
                    active_boxes = []
                    if len(raw_dets) > 0:
                        detections_list = raw_dets[0] if isinstance(raw_dets, list) else raw_dets
                        for class_list in detections_list:
                            for det in class_list:
                                if len(det) >= 5:
                                    # 🚀 FIX: Safely extract the confidence score from the array
                                    score = float(np.array(det[4]).flatten()[0])
                                    if score > 0.45:
                                        ymin, xmin, ymax, xmax = det[:4]
                                        active_boxes.append([int(xmin*1344), int(ymin*1008), int(xmax*1344), int(ymax*1008)])

                   # 🚀 5. MOTION-FILTERED PEDOMETER (ALWAYS TRACKING)
                    deltas = []
                    
                    # 🚀 FIX 1: Loosen the rotation gate. 
                    # 0.3 rad/s ignores human walking wobble but catches deliberate turning.
                    is_turning = abs(gz) > 0.3 or abs(gy) > 0.3 
                    
                    current_feat_ids = set()

                    # 🚀 FIX 2: NEVER put this loop inside an 'if not is_turning' block. 
                    # The camera must always draw and track!
                    for f in fea_data:
                        current_feat_ids.add(f.id)
                        x, y = int(f.position.x), int(f.position.y)
                        dx, dy = int(x * 1344/640), int(y * 1008/480)
                        
                        if 0 <= dy < 1008 and 0 <= dx < 1344:
                            # --- MASKING ---
                            is_on_obj = any(b[0]<=dx<=b[2] and b[1]<=dy<=b[3] for b in active_boxes)
                            
                            # --- 🟢 VISUALIZER: LUXONIS SMOOTH TRAILS ---
                            if f.id not in pixel_path_history: 
                                pixel_path_history[f.id] = deque(maxlen=10)
                                
                            if is_on_obj: 
                                # Red dot = Masked (ignored)
                                cv2.circle(rgb_isp, (dx, dy), 2, (0, 0, 255), -1, cv2.LINE_AA)
                                continue 
                                
                            # Update trail memory
                            pixel_path_history[f.id].append((dx, dy))
                            path = list(pixel_path_history[f.id])
                            
                            # Draw purple trail
                            for i in range(len(path) - 1):
                                cv2.line(rgb_isp, path[i], path[i+1], (200, 0, 200), 1, cv2.LINE_AA)
                            
                            # Draw yellow dot at current location
                            cv2.circle(rgb_isp, (dx, dy), 2, (0, 255, 255), -1, cv2.LINE_AA)

                            # --- 📐 PEDOMETER MATH ---
                            z = depth_raw[dy, dx] / 1000.0
                            if 0.5 < z < 8.0:
                                if f.id in feat_history:
                                    d_z = feat_history[f.id] - z
                                    
                                    # 🚀 FIX 3: We only add to the distance math if NOT turning
                                    # We keep abs(d_z) so static noise cancels out to 0.0 in the window!
                                    if not is_turning and abs(d_z) < 0.40: 
                                        deltas.append(d_z)
                                        
                                feat_history[f.id] = z
                    
                    # 🧹 CLEANUP: Delete trails for points that left the screen
                    old_ids = set(pixel_path_history.keys()) - current_feat_ids
                    for old_id in old_ids:
                        del pixel_path_history[old_id]
                        if old_id in feat_history: del feat_history[old_id]
                    
                    # 🚀 6. NOISE-CANCELLING MATH & STEP GATE
                    frame_move = np.median(deltas) if deltas else 0.0
                    motion_window.append(frame_move)
                    if len(motion_window) > 10: motion_window.pop(0)
                    smooth_move = sum(motion_window) / len(motion_window)

                    if warmup_frames < 30: 
                        warmup_frames += 1
                        total_dist = 0.0
                    
                    # 🚀 ONLY move if the IMU feels a step AND the net trend is forward
                    elif is_stepping and smooth_move > 0.005: 
                        total_dist += (smooth_move * CALIBRATION_SCALE)
                        rad_yaw = math.radians(current_yaw)
                        current_x += (smooth_move * CALIBRATION_SCALE) * math.sin(rad_yaw)
                        current_z += (smooth_move * CALIBRATION_SCALE) * math.cos(rad_yaw)
                        
                        cv2.putText(rgb_isp, "WALKING >>", (1100, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

                    # 🚀 7. NODE-TO-NODE RECORDING LOGIC
                    if STATE == "RECORDING":
                        # We no longer drop automatic 'path' breadcrumbs.
                        # The route is now defined EXCLUSIVELY by the user's spoken Landmarks (Nodes).
                        # Distance is still tracked perfectly by total_dist in the background.
                        pass

                    # 🚀 7. NAVIGATION & 3-ZONE SAFETY SHIELD
                    if STATE == "NAVIGATING":
                        path_blocked = False
                        critical_warning = ""
                        WIDTH, HEIGHT = 1344, 1008
                        ZONE_AREA = (WIDTH / 3) * HEIGHT
                        
                        if len(raw_dets) > 0:
                            detections_list = raw_dets[0] if isinstance(raw_dets, list) else raw_dets
                            # 🚀 FIX: Iterate properly through class_id and class_list
                            for class_id, class_list in enumerate(detections_list):
                                for det in class_list:
                                    if len(det) >= 5:
                                        # 🚀 FIX: Safely extract the confidence score
                                        score = float(np.array(det[4]).flatten()[0])
                                        
                                        if score > 0.45: 
                                            ymin, xmin, ymax, xmax = det[:4]
                                            x1, y1, x2, y2 = int(xmin*WIDTH), int(ymin*HEIGHT), int(xmax*WIDTH), int(ymax*HEIGHT)
                                            box_area = (x2 - x1) * (y2 - y1)
                                            fill_ratio = box_area / ZONE_AREA
                                            
                                            cx = (xmin + xmax) / 2
                                            
                                            # Constrain bounds to prevent index errors
                                            sample_y = max(0, min(HEIGHT-1, int((ymin+ymax)/2*HEIGHT)))
                                            sample_x = max(0, min(WIDTH-1, int(cx*WIDTH)))
                                            obj_z = depth_raw[sample_y, sample_x] / 1000.0
                                            
                                            label_name = LABELS[class_id] if class_id < len(LABELS) else "Object"

                                     # ZONE 3: CENTER Blocked!
                                            if 0.33 < cx < 0.66:
                                                if obj_z < 0.5:
                                                    path_blocked = True
                                                    critical_warning = f"{label_name} blocks your path."
                                                    break
                        
                        if path_blocked:
                            if is_ticking: tick_sound_effect.stop(); is_ticking = False
                            if audio_queue.empty(): audio_queue.put({"type": "text", "msg": critical_warning})
                        else:
                            inst = nav_engine.get_instruction(current_x, current_z, current_yaw)
                            if inst: 
                                if isinstance(inst, dict):
                                    audio_queue.put(inst)
                                else:
                                    audio_queue.put({"type": "text", "msg": inst})
                                    
                            path_dist = nav_engine.get_path_remaining_distance(total_dist) # 🚀 FIX THIS LINE
                            play_navigation_tick(current_yaw, nav_engine.target_yaw, screen_width=1024)

                    # 🚀 9. RENDER UI (Headless Safe)
                    processed = inference_result_handler(
                        rgb_isp, raw_dets, LABELS, CONFIG_DATA, 
                        vio_data=(total_dist, smooth_yaw, curr_pitch, curr_roll), 
                        target_yaw=nav_engine.target_yaw if STATE == "NAVIGATING" else None, 
                        target_dist=nav_engine.distance_to_wp if STATE == "NAVIGATING" else None,
                        depth_frame=depth_raw, state_text=STATE
                    )
                    
                    try:
                        # Only attempt to draw the window if the OS allows it
                        # If running headless (no monitor/VNC), this fails silently
                        cv2.imshow("SENSEY 6-DOF AR Navigator", cv2.resize(processed, (1024, 768)))
                        if cv2.waitKey(1) == ord('q'): 
                            break
                    except Exception as e:
                        # 🚀 HEADLESS MODE FALLBACK: 
                        # We must still use a tiny sleep to keep the loop timing stable 
                        # so the IMU 'dt' math doesn't spin out of control.
                        time.sleep(0.001) 
                        pass
                        
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run()