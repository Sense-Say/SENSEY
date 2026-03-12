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
    Guarantees up to 10 precise structural keys without aliasing conflict crashes!
    """
    ord_map = {
        "first": "1", "one": "1", 
        "second": "2", "two": "2", 
        "third": "3", "three": "3", 
        "fourth": "4", "four": "4", 
        "fifth": "5", "five": "5", 
        "sixth": "6", "six": "6",
        "seventh": "7", "seven": "7", 
        "eighth": "8", "eight": "8", 
        "ninth": "9", "nine": "9", 
        "tenth": "10", "ten": "10"
    }
    
    words = text.lower().split()
    for word in words:
        if word in ord_map:
            num = ord_map[word]
            return f"destination_{num}", num
    return None, None

import queue
audio_queue = queue.Queue()

# 🚀 THE SINGLE-THREADED AUDIO MANAGER (No more aplay, no more busy errors)
def audio_worker():
    """🚀 THE SINGLE-THREADED AUDIO MANAGER: Plays one thing at a time."""
    while True:
        cmd = audio_queue.get()
        if cmd['type'] == 'text':
            subprocess.run(f'echo "{cmd["msg"]}" | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | aplay -r 22050 -f S16_LE -t raw > /dev/null 2>&1', shell=True)
        elif cmd['type'] == 'wav':
            # This is used for your recorded voice notes (which are already formatted perfectly for aplay)
            subprocess.run(['aplay', '-q', cmd['path']])
        elif cmd['type'] == 'beep':
            if start_beep_sound: 
                start_beep_sound.play()
                time.sleep(start_beep_sound.get_length())
            else:
                subprocess.run(['aplay', '-q', '/usr/share/sounds/alsa/Front_Center.wav'])
        
        # 🚀 FIX: Handle the arrival sound using Pygame
        elif cmd['type'] == 'arrival':
            if arrival_sound:
                arrival_sound.play()
                # Wait for the exact length of the sound to finish before Piper speaks
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
        self.stride_length = 0.75 
        self.last_arrival_time = 0.0
        
    def load_path(self, path_data):
        """🚀 CLEW AUTO-TURN LOGIC: Analyzes breadcrumbs to find corners."""
        raw_nodes = []
        for p in path_data:
            raw_nodes.append({
                "x": p[0], "z": p[1], "label": p[2], 
                "yaw": p[3] if len(p) > 3 else 0.0,
                "note": p[4] if len(p) > 4 else ""
            })
        
        self.path = [raw_nodes[0]] 
        for i in range(1, len(raw_nodes) - 1):
            prev, curr, next_n = raw_nodes[i-1], raw_nodes[i], raw_nodes[i+1]
            seg_dist = math.sqrt((curr['x'] - self.path[-1]['x'])**2 + (curr['z'] - self.path[-1]['z'])**2)
            angle1 = math.atan2(curr['x'] - prev['x'], curr['z'] - prev['z'])
            angle2 = math.atan2(next_n['x'] - curr['x'], next_n['z'] - curr['z'])
            diff = abs(math.degrees(angle2 - angle1 + math.pi) % 360 - 180)
            
            if seg_dist > 0.6 or diff > 30 or curr['note'] != "":
                self.path.append(curr)
        
        self.path.append(raw_nodes[-1]) 
        self.active = True
        self.current_wp_index = 1 if len(self.path) > 1 else 0
        self.offset_x, self.offset_z, self.offset_yaw = 0, 0, 0
############################################################################################
    def calculate_turn(self, cx, cz, cur_yaw, tx, tz):
        # 1. Calculate the Target Heading (Global 0-360)
        target_yaw = math.degrees(math.atan2(tx - cx, tz - cz)) % 360
        
        # 2. Calculate the Relative Turn (The "Clew" Logic)
        # This gives us a result between -180 and 180
        turn_error = (target_yaw - cur_yaw + 180) % 360 - 180
        
        # 3. Simplify the instruction
        if abs(turn_error) < 20:
            return "Continue straight"
        elif turn_error > 0:
            return f"Turn right {int(turn_error)} degrees"
        else:
            return f"Turn left {int(abs(turn_error))} degrees"
        
        if abs(turn_error) > 150:
            return "Turn around"

############################################################################################
    def get_instruction(self, cur_x, cur_z, cur_yaw, is_on_demand=False):
        global STATE
        if not self.active or self.current_wp_index >= len(self.path): return None
        
        target = self.path[self.current_wp_index]
        tx, tz = target["x"] + self.offset_x, target["z"] + self.offset_z
        self.distance_to_wp = math.sqrt((tx - cur_x)**2 + (tz - cur_z)**2)
        self.target_yaw = math.degrees(math.atan2(tx - cur_x, tz - cur_z)) % 360
        
        direction_word = self.get_human_direction(self.target_yaw, cur_yaw)
        steps = max(1, int(self.distance_to_wp / self.stride_length))

        if is_on_demand:
            return f"Target is {direction_word}. Walk {steps} steps."

        # Arrival Logic (Distance < 0.45m)
# ... inside get_instruction ...
        if self.distance_to_wp < 0.45:
            
            
            # 2. Play voice note if it exists
            if target['note'] and target['note'].endswith(".wav"):
                note_full_path = os.path.join(DOC_PATH, target['note'])
                if os.path.exists(note_full_path):
                    print({note_full_path})
                    audio_queue.put({"type": "wav", "path": note_full_path})
            
            self.current_wp_index += 1
            
            # 🚀 3. THE FIXED FINAL DESTINATION LOGIC
            if self.current_wp_index >= len(self.path):
                self.active = False
                STATE = "IDLE" # Forcefully end navigation visually
                
                # Push the Pygame sound to the queue
                print({"arrival"})
                audio_queue.put({"type": "arrival"})
                
                # Push the final speech (It will wait for the sound to finish automatically)
                print({"Navigation ended."})
                audio_queue.put({"type": "text", "msg": "Arrived at destination. Navigation ended."})
                
                return None             
            # If NOT final destination, queue the next turn instruction
            next_target = self.path[self.current_wp_index]
            nx, nz = next_target["x"] + self.offset_x, next_target["z"] + self.offset_z
            next_yaw = math.degrees(math.atan2(nx - tx, nz - tz)) % 360
            next_direction = self.get_human_direction(next_yaw, cur_yaw)
            
            if "ahead" in next_direction:
                print({"Continue straight."})
                audio_queue.put({"type": "text", "msg": "Continue straight."})
            else:
                print({f"Turn {next_direction}."})
                audio_queue.put({"type": "text", "msg": f"Turn {next_direction}."})
                
            return None
                
        return None

    def get_path_remaining_distance(self, cur_x, cur_z):
        if not self.active or self.current_wp_index >= len(self.path): return 0.0
        target = self.path[self.current_wp_index]
        d = math.sqrt((target["x"] + self.offset_x - cur_x)**2 + (target["z"] + self.offset_z - cur_z)**2)
        for i in range(self.current_wp_index, len(self.path) - 1):
            p1, p2 = self.path[i], self.path[i+1]
            d += math.sqrt((p2["x"] - p1["x"])**2 + (p2["z"] - p1["z"])**2)
        return d

    def get_path_remaining_distance(self, cur_x, cur_z):
        # This is used for the HUD display if you want total remaining distance
        if not self.active or self.current_wp_index >= len(self.path): return 0.0
        target = self.path[self.current_wp_index]
        d = math.sqrt((target["x"] + self.offset_x - cur_x)**2 + (target["z"] + self.offset_z - cur_z)**2)
        for i in range(self.current_wp_index, len(self.path) - 1):
            p1, p2 = self.path[i], self.path[i+1]
            d += math.sqrt((p2["x"] - p1["x"])**2 + (p2["z"] - p1["z"])**2)
        return d

nav_engine = NavigationManager()

def play_navigation_tick(current_yaw, target_yaw, screen_width=1024):
    global is_ticking
    if target_yaw is None or STATE != "NAVIGATING":
        if is_ticking: tick_sound_effect.stop(); is_ticking = False
        return
    pixels_per_degree = screen_width / 90
    relative_angle = (target_yaw - current_yaw + 180) % 360 - 180
    arrow_x = (screen_width // 2) + int(relative_angle * pixels_per_degree)
    l_lim, r_lim = screen_width // 3, 2 * screen_width // 3
    if l_lim <= arrow_x <= r_lim:
        if not is_ticking: tick_sound_effect.play(loops=-1); is_ticking = True
    else:
        if is_ticking: tick_sound_effect.stop(); is_ticking = False

def speak_offline(text):
    """Mouth: Uses Piper. Prints to terminal and speaks."""
    global is_speaking
    if not text.strip(): return
    
    # 🚀 EXPLICIT LOGGING: The teacher can see exactly what the AI says
    print(f"\n[SPEECH SYSTEM] 🔊: {text}\n")
    
    def _speak_thread():
        global is_speaking
        is_speaking = True
        cmd = f'echo "{text}" | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | aplay -D default -r 22050 -f S16_LE -t raw'
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
        
        # Build out clean aliased arrays explicitly over route Maps decoupled natively from previous bugs 
        mapping = {}
        if os.path.exists(ROUTE_MAP_FILE):
            try:
                with open(ROUTE_MAP_FILE, 'r') as f: 
                    mapping = json.load(f)
            except Exception as e:
                print(f"Mapping JSON init override: {e}")
                
        mapping[pending_route_key] = pending_route_alias
        
        with open(ROUTE_MAP_FILE, 'w') as f: 
            json.dump(mapping, f, indent=4) # cleanly formats array visually tracking indices flawlessly

        recorded_path = [[0.0, 0.0, "start", current_yaw, ""]]
        total_dist, current_yaw, current_x, current_z, last_wp_dist = 0.0, 0.0, 0.0, 0.0, 0.0
        landmark_count = 0
        print("🔊 Speaking: Recording. Anchor set.")
        speak_offline(f"Recording. Anchor set.")

    # 🚀 FIX: Distinct 'FINISH' routing natively ignores state to properly write output arrays mapped specifically when asked! 
    elif "finish" in cmd:
        if len(recorded_path) > 0:
            # Inject tracking parameters mapping immediately 
            recorded_path.append([current_x, current_z, "destination", current_yaw, ""])
            
            # Form file pathway locally generating arrays dynamically inside specific directory targeting! 
            file_path = os.path.join(DOC_PATH, f"{current_route_filename}.json")
            
            try:
                with open(file_path, "w") as f: 
                    json.dump(recorded_path, f, indent=4) # Ident added mapping formatting internally resolving debugging checks effectively.
                
                print(f"DEBUG: Successfully stored internal pathway constraints map locally {file_path}")    
                speak_offline("Saving last point. Recording finished.")
            except Exception as e:
                print(f"Error saving internal parameters string failure logic output tracking error! : {e}")
        
        elif STATE == "NAVIGATING":
            nav_engine.active = False
            print("🔊 Speaking: Navigation stopped.")
            speak_offline("Navigation stopped.")
            
        STATE = "IDLE"

    # 🚀 SEPARATE "STOP" LOGIC (CANCEL RECORDING) 
    elif "stop" in cmd:
        # Clear mapping state paths ignoring memory arrays seamlessly resetting configuration
        if len(recorded_path) > 0 and current_route_filename != "":
            print(f"DEBUG: Purged active pathway string configurations completely aborting active routes!")
            speak_offline("Recording not saved.")
        elif STATE == "NAVIGATING":
            nav_engine.active = False
            print("🔊 Speaking: Navigation stopped.")
            speak_offline("Navigation stopped.")
        STATE = "IDLE"

    elif "navigate" in cmd or "go to" in cmd:
        dest_key, _ = get_ordinal_key(cmd)
        is_reverse = "reverse" in cmd

        if not dest_key:
            print("🔊 Speaking: Please specify an ordinal destination.")
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
                    else:
                        audio_queue.put({"type": "text", "msg": "Navigating."})
                        
                    STATE = "NAVIGATING"
                    total_dist, current_yaw, current_x, current_z = 0.0, 0.0, 0.0, 0.0
                    nav_engine.load_path(nav_path)
                    
                    first_upd = nav_engine.get_instruction(0, 0, current_yaw, is_on_demand=True)
                    if first_upd:
                        audio_queue.put({"type": "text", "msg": first_upd})
      
            except Exception as e:
                print("🔊 Speaking: Failed to load destination data.")
                speak_offline("Failed to load destination data.")
        else:
            STATE = "IDLE"
            print("🔊 Speaking: Destination not found.")
            speak_offline("Destination not found.")

def handle_voice_command(cmd):
    global STATE, pending_command, is_listening, recorded_path, landmark_count, current_x, current_z, current_yaw, previous_state
    global mic_stream, native_rate, mic_idx, audio_callback, rec, is_recording_note
    global pending_route_key, pending_route_alias

    import scipy.io.wavfile as wav
    
    cmd = cmd.lower().strip()
    if not cmd: return
    print(f"✅ Voice Input: {cmd} (State: {STATE})")

    # ---------------- IDLE & BASE LEVEL COMMANDS ---------------- #
    if STATE == "IDLE":
        if "identify" in cmd:
            key, num = get_ordinal_key(cmd)
            if key:
                mapping = {}
                # Extract cleanly specifically targeting our brand new structured layout!
                if os.path.exists(ROUTE_MAP_FILE):
                    try:
                        with open(ROUTE_MAP_FILE, 'r') as f: mapping = json.load(f)
                    except: pass
                alias = mapping.get(key, "unnamed")
                print(f"Destination {num} is {alias}.")
                speak_offline(f"Destination {num} is {alias}.")
            else:
                print("Destination not specified.")
                speak_offline("Destination not specified.")

        elif any(x in cmd for x in ["record", "go to", "navigate"]):
            pending_command = cmd
            STATE = "CONFIRM_START"
            print(f"You said {cmd}. Is this correct?")
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
                    print("Please say the name for this destination.")
                    speak_offline("Please say the name for this destination.")
                    # 🚀 FIX: explicitly unfreeze Vosk callback gate AFTER prompt
                    is_listening = True 
                else:
                    STATE = "IDLE"
                    print("Ordinal required, like record first destination. Cancelled.")
                    speak_offline("Ordinal required, like record first destination. Cancelled.")
            else: # Navigating Mode 
                STATE = "IDLE"
                execute_action(pending_command)
        else: 
            STATE = "IDLE"
            print("Cancelled.")
            speak_offline("Cancelled.")

    elif STATE == "WAIT_DEST_NAME":
        pending_route_alias = cmd
        STATE = "CONFIRM_DEST_NAME"
        print(f"You said {cmd}. Is this correct?")
        speak_offline(f"You said {cmd}. Is this correct?")
        # 🚀 FIX: keep the chained workflow continuous and non-stagnating
        is_listening = True

    elif STATE == "CONFIRM_DEST_NAME":
        if "yes" in cmd or "correct" in cmd:
            STATE = "IDLE" 
            pending_command = "" 
            execute_action("start_recording_dest") # Saves directly in mapped routing!
        else:
            STATE = "WAIT_DEST_NAME"
            print("Please say the name for this destination again.")
            speak_offline("Please say the name for this destination again.")
            # 🚀 FIX: looping fallback to prevent mic-death error
            is_listening = True

    # ---------------- FINISH WORKFLOW STATES ---------------- #
    elif STATE == "CONFIRM_FINISH":
        if "yes" in cmd or "correct" in cmd: execute_action(pending_command)
        else: STATE = previous_state; speak_offline("Resuming.")
        pending_command = ""

    # ---------------- THREAD SAFE 5S WAV NOTES ("The Sponge") ---------------- #
    elif STATE == "CONFIRM_NOTE":
        import scipy.io.wavfile as wav
        global voice_note_buffer, note_recording_start_time

        if "yes" in cmd or "correct" in cmd:
            STATE = "RECORDING_NOTE"

            print("🔊 Prompting: Start")
            subprocess.run(f'echo "Start" | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | aplay -r 22050 -f S16_LE -t raw > /dev/null 2>&1', shell=True) 

            audio_queue.put({"type": "beep"})
            time.sleep(1.5)  # give it time to beep before record starts
            
            note_filename = f"{current_route_filename}_note_{landmark_count}.wav"
            note_path = os.path.join(DOC_PATH, note_filename)
            print(f"🎙️ Sponge active for 5s: {note_filename}")
            
            voice_note_buffer = [] 
            note_recording_start_time = time.time()
            is_recording_note = True # Flag shifts Audio Callback routing!
            
            # The Main Thread blocks here as a timeout (Callback loads data seamlessly)
            while is_recording_note:
                time.sleep(0.1)
                
            audio_queue.put({"type": "beep"})
            time.sleep(1.0)
            
            if len(voice_note_buffer) > 0:
                try:
                    audio_data = np.concatenate(voice_note_buffer, axis=0)
                    wav.write(note_path, native_rate, audio_data)
                    print(f"✅ Saved to {note_path}")
                    if len(recorded_path) > 0: recorded_path[-1][4] = note_filename
                except Exception as e:
                    print(f"🔴 Note fail: {e}")
                    
            print("✅ Recording finished. Saving...")
            subprocess.run(f'echo "Voice note saved. Continue recording." | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | aplay -r 22050 -f S16_LE -t raw > /dev/null 2>&1', shell=True)
            
            rec.Reset()
            STATE = "RECORDING"
        else:
            STATE = "RECORDING"
            print("Continuing recording.")
            speak_offline("Continuing recording.")


    # ---------------- OPERATIONAL RECORDING ---------------- #
    elif STATE == "RECORDING":
        if "point" in cmd and "saved" in cmd:
            landmark_count += 1
            recorded_path.append([current_x, current_z, f"point_{landmark_count}", current_yaw, ""])
            STATE = "CONFIRM_NOTE"
            print(f"Point {landmark_count} saved. Do you want to add a voice note?")
            speak_offline(f"Point {landmark_count} saved. Do you want to add a voice note?")
            is_listening = True
            
        # 🚀 DISTINCT "FINISH" COMMAND (Success wrap-up)
        elif "finish" in cmd:
            pending_command = "finish"
            previous_state = "RECORDING"
            STATE = "CONFIRM_FINISH"
            print("Finish recording. Is this correct?")
            speak_offline("Finish recording. Is this correct?")
            is_listening = True 
            
        # 🚀 DISTINCT "STOP" COMMAND (Abort)
        elif "stop" in cmd:
            pending_command = "stop"
            previous_state = "RECORDING"
            STATE = "CONFIRM_FINISH"
            print("Stop recording. Is this correct?")
            speak_offline("Stop recording. Is this correct?")
            is_listening = True 

    # ---------------- OPERATIONAL NAVIGATING ---------------- #
    elif STATE == "NAVIGATING":
        if "update" in cmd:
            status = nav_engine.get_instruction(current_x, current_z, current_yaw, is_on_demand=True)
            if status: speak_offline(status)
        elif "pause" in cmd:
            STATE = "PAUSED";
            print("Navigation paused.")
            speak_offline("Navigation paused.")
        elif "finish" in cmd or "stop" in cmd:
            pending_command = "stop"; previous_state = "NAVIGATING"; STATE = "CONFIRM_FINISH"
            print("Stop navigation. Is this correct?")
            speak_offline("Stop navigation. Is this correct?"); is_listening = True 

    elif STATE == "PAUSED":
        if "resume" in cmd: STATE = "NAVIGATING";
        print("Resuming navigation.")
        speak_offline("Resuming navigation.")

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
    feat.setHardwareResources(1, 1)
    feat.initialConfig.setNumTargetFeatures(100)
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
TAG_MAP = {
    0: 0.0,    # North 
    1: 45.0,   # North-East
    2: 90.0,   # East 
    3: 135.0,  # South-East
    4: 180.0,  # South
    5: 225.0,  # South-West
    6: 270.0,  # West 
    7: 315.0   # North-West
}

def handle_april_tags(april_data, current_yaw, current_x, current_z, depth_frame):
    """
    🚀 UNIFIED APRILTAG SNAP: Combines Center-Offset checking with Depth validation.
    """
    # The Mono camera is 640x480. 
    # Center 1/3 is normally 213 to 426. 
    # We shift it right by ~50 pixels to compensate for the Left lens physical offset.
    l_lim = (640 * 0.33) + 50
    r_lim = (640 * 0.66) + 50
    
    for det in april_data.aprilTags:
        if det.id in TAG_MAP:
            # 1. Calculate center of tag in Mono pixels (640x480)
            cx_mono = (det.topLeft.x + det.topRight.x + det.bottomRight.x + det.bottomLeft.x) / 4
            cy_mono = (det.topLeft.y + det.topRight.y + det.bottomRight.y + det.bottomLeft.y) / 4
            
            # 2. CENTER GATE: Only proceed if the tag is in the middle of the screen
            if l_lim < cx_mono < r_lim:
                
                # 3. Scale coordinates to match the 1344x1008 Depth Map
                dx = int(cx_mono * (1344 / 640))
                dy = int(cy_mono * (1008 / 480))
                
                # 4. DEPTH GATE: Ensure pixels are inside the frame
                if 0 <= dy < 1008 and 0 <= dx < 1344:
                    z_meters = depth_frame[dy, dx] / 1000.0
                    
                    # Only snap if the tag is between 0.5m and 3.0m away 
                    # (Prevents snapping to tiny printed tags far away)
                    if 0.45 < z_meters < 3.0:
                        
                        # 5. 🚀 THE HARD SNAP
                        target_world_yaw = TAG_MAP[det.id]
                        
                        # Only print/snap if there is an actual drift to correct (> 2 degrees)
                        # This prevents the terminal from spamming when you are already aligned
                        if abs((target_world_yaw - current_yaw + 180) % 360 - 180) > 2.0:
                            current_yaw = target_world_yaw
                            print(f"⚓ ANCHOR SNAPPED! Tag {det.id} at {z_meters:.1f}m. Yaw locked to {current_yaw}°")
                            
                        # Note: We do not reset current_x or current_z here unless we map the exact 
                        # X,Z coordinates of every tag in the room. Snapping Yaw is enough to fix drift!
                        
    return current_yaw, current_x, current_z

#--------------------------------------------------------------------------------------------------------------------

def run():
    global total_dist, current_yaw, last_wp_dist, recorded_path, nav_path, is_listening, is_speaking, STATE, current_x, current_z
    global mic_stream, native_rate, mic_idx, audio_callback, rec, vosk_model
    
    # 🚀 1. INITIALIZE CORE VARIABLES
    curr_yaw, curr_pitch, curr_roll = 0.0, 0.0, 0.0
    smooth_yaw = 0.0 
    gx, gy, gz = 0.0, 0.0, 0.0 
    last_imu_t = None
    feat_history = {} 
    pixel_path_history = {} # 🚀 NEW: Stores the (x,y) trails for the purple lines
    motion_window = [] 
    warmup_frames = 0
    CALIBRATION_SCALE = 1.66 
    PERSON_CLASS_ID = 0 
    # 1. Add q_apr queue
    
    print("⏳ Loading Vosk...")
    vosk_model = vosk.Model(VOSK_MODEL_PATH)
    rec = vosk.KaldiRecognizer(vosk_model, 16000, json.dumps(ALLOWED_WORDS))
    
    print("⏳ Loading Hailo NPU...")
    target = VDevice(); hef = HEF(HEF_PATH)
    conf = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
    group = target.configure(hef, conf)[0]
    in_p = InputVStreamParams.make(group, format_type=FormatType.UINT8)
    out_p = OutputVStreamParams.make(group, format_type=FormatType.FLOAT32)
    input_name = hef.get_input_vstream_infos()[0].name
    
    try: 
        btn = Button(26, pull_up=True)
        btn.when_pressed = trigger_listening
        print("✅ Button 26 initialized.")
    except: btn = None
    
    devices = sd.query_devices()
    mic_idx, native_rate = 0, 44100
    for i, dev in enumerate(devices):
        if "USB" in dev['name']: mic_idx, native_rate = i, int(dev['default_samplerate']); break
            
    def audio_callback(indata, frames, time_info, status):
        global is_listening, is_speaking, is_recording_note, voice_note_buffer, note_recording_start_time
        
        if is_recording_note:
            audio_int16 = (indata.copy() * 32767).astype(np.int16)
            voice_note_buffer.append(audio_int16)
            # Automatic shutoff constraint from Sponge memory mapping 
            if time.time() - note_recording_start_time >= 5.0:
                is_recording_note = False
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
        q_apr = device.getOutputQueue("april", 4, False) # 🚀 Add this line
        
        with group.activate():
            with InferVStreams(group, in_p, out_p) as pipe:
                print("✅ SENSEY Ready."); speak_offline("System Ready.")
                
                # 🚀 THERE IS ONLY ONE 'WHILE TRUE' LOOP NOW
                while True:
        
                    # 🚀 2. IMU FUSION & YAW SMOOTHING
                    imuData = q_imu.tryGetAll() 
                    
                    ax, ay, az = 0.0, 0.0, 0.0 
                    gx, gy, gz = 0.0, 0.0, 0.0
                    is_stepping = False 
                    
                    for data in imuData:
                        for packet in data.packets:
                            ts = packet.acceleroMeter.timestamp.get().total_seconds()
                            if last_imu_t is None: last_imu_t = ts; continue
                            dt = ts - last_imu_t; last_imu_t = ts
                            
                            ax, ay, az = packet.acceleroMeter.x, packet.acceleroMeter.z, packet.acceleroMeter.y
                            gx, gy, gz = packet.gyroscope.x, packet.gyroscope.z, packet.gyroscope.y
                            
                            current_yaw -= (gz * (180.0 / math.pi) * dt)
                            curr_pitch = 0.98 * (curr_pitch + gx * (180.0/math.pi) * dt) + 0.02 * math.degrees(math.atan2(ay, math.sqrt(ax**2 + az**2)))
                            curr_roll = 0.98 * (curr_roll + gy * (180.0/math.pi) * dt) + 0.02 * math.degrees(math.atan2(ax, az))
                            current_yaw = (current_yaw + 180) % 360 - 180
                            smooth_yaw = (0.8 * smooth_yaw) + (0.2 * current_yaw)
                            
                            # STEP DETECTION
                            accel_mag = math.sqrt(ax**2 + ay**2 + az**2)
                            if abs(accel_mag - 9.81) > 0.2: 
                                is_stepping = True

                    
                    # 🚀 3. FETCH SENSOR FRAMES
                    rgb_isp = q_isp.get().getCvFrame()
                    rgb_pre = q_pre.get().getCvFrame() 
                    depth_raw = q_dep.get().getFrame()
                    fea_data = q_fea.get().trackedFeatures
                    
                    # 🚀 NEW: FETCH APRILTAGS & APPLY SNAP
                    april_in = q_apr.tryGet()
                    if april_in:
                        current_yaw, current_x, current_z = handle_april_tags(
                            april_in, current_yaw, current_x, current_z, depth_raw
                        )
                        
                    # 🚀 4. AI INFERENCE (Masking)
                    res = pipe.infer({input_name: np.expand_dims(rgb_pre, axis=0)})
                    raw_dets = list(res.values())[0]
                    active_boxes = []
                    if len(raw_dets) > 0:
                        for class_list in (raw_dets[0] if isinstance(raw_dets, list) else raw_dets):
                            for det in class_list:
                                if len(det) >= 5 and det[4] > 0.45:
                                    ymin, xmin, ymax, xmax = det[:4]
                                    active_boxes.append([int(xmin*1344), int(ymin*1008), int(xmax*1344), int(ymax*1008)])

                    # 🚀 5. MOTION-FILTERED PEDOMETER 
                    deltas = []
                    is_rotating = abs(gz) > 0.1 or abs(gx) > 0.1
                    
                    # Track which IDs are currently visible to clean up old ones
                    current_feat_ids = set()

                    if not is_rotating:
                        for f in fea_data:
                            current_feat_ids.add(f.id)
                            
                            x, y = int(f.position.x), int(f.position.y)
                            dx, dy = int(x * 1344/640), int(y * 1008/480)
                            
                            if 0 <= dy < 1008 and 0 <= dx < 1344:
                                # --- DYNAMIC MASKING ---
                                is_on_person = False
                                if len(raw_dets) > 0:
                                    for class_id, class_list in enumerate(raw_dets[0] if isinstance(raw_dets, list) else raw_dets):
                                        if class_id == PERSON_CLASS_ID:
                                            for det in class_list:
                                                if len(det) >= 5 and det[4] > 0.5:
                                                    ymin, xmin, ymax, xmax = det[:4]
                                                    if (xmin*1344) <= dx <= (xmax*1344) and (ymin*1008) <= dy <= (ymax*1008):
                                                        is_on_person = True; break
                                        if is_on_person: break
                                
                                if is_on_person: continue # Skip points on moving students

                                # 🚀 LUXONIS VISUALIZER: The Deque Trail Logic
                                if f.id not in pixel_path_history:
                                    # Create a queue that automatically deletes points older than 10 frames
                                    pixel_path_history[f.id] = deque(maxlen=10)
                                
                                # Add current position to the history
                                pixel_path_history[f.id].append((dx, dy))
                                
                                # Draw the purple trail
                                path = list(pixel_path_history[f.id])
                                for i in range(len(path) - 1):
                                    cv2.line(rgb_isp, path[i], path[i+1], (200, 0, 200), 1, cv2.LINE_AA)
                                
                                # Draw the solid red dot at the head of the trail
                                cv2.circle(rgb_isp, (dx, dy), 2, (0, 0, 255), -1, cv2.LINE_AA)

                                # --- PEDOMETER MATH (Completely separate from drawing) ---
                                z = depth_raw[dy, dx] / 1000.0
                                if 0.8 < z < 8.0:
                                    if f.id in feat_history:
                                        d_z = feat_history[f.id] - z
                                        if abs(d_z) < 0.40: deltas.append(d_z)
                                    feat_history[f.id] = z
                    
                    # 🧹 CLEANUP: Delete trails and history for points that left the screen
                    old_ids = set(pixel_path_history.keys()) - current_feat_ids
                    for old_id in old_ids:
                        del pixel_path_history[old_id]
                        if old_id in feat_history:
                            del feat_history[old_id]
                    
                    # 🚀 APPLY PEDOMETER MATH (Step Gate)
                    # We check: Is the teacher physically moving? (is_stepping is defined in IMU loop)
                    if deltas and is_stepping:
                        avg_step = np.median(deltas)
                        # Forward-Only Gate
                        if avg_step > 0.005:
                            total_dist += (avg_step * CALIBRATION_SCALE)
                            rad_yaw = math.radians(current_yaw)
                            current_x = total_dist * math.sin(rad_yaw)
                            current_z = total_dist * math.cos(rad_yaw)

                    # 🚀 6. NAVIGATION LOGIC (Only runs when NAVIGATING)
                    if STATE == "NAVIGATING":
                        # DYNAMIC SAFETY OVERRIDE
                        path_blocked = False
                        critical_warning = ""
                        
                        global is_ticking # 🚀 Force explicit inheritance here locally!
                        
                        if len(raw_dets) > 0:
                            for class_list in (raw_dets[0] if isinstance(raw_dets, list) else raw_dets):
                                for det in class_list:
                                    if len(det) >= 5 and det[4] > 0.45:
                                        ymin, xmin, ymax, xmax = det[:4]
                                        cx = (xmin + xmax) / 2
                                        sample_y, sample_x = int((ymin+ymax)/2*1008), int(cx*1344)
                                        sample_y = max(0, min(1007, sample_y))
                                        sample_x = max(0, min(1343, sample_x))
                                        obj_z = depth_raw[sample_y, sample_x] / 1000.0
                                        
                                        if 0.1 < obj_z < 0.6:
                                            path_blocked = True
                                            if cx < 0.33: critical_warning = "Object very close on left."
                                            elif cx > 0.66: critical_warning = "Object very close on right."
                                            else: critical_warning = "Object directly in front. Stop."
                                            break
                                        elif 0.33 < cx < 0.66 and 0.6 <= obj_z < 1.2:
                                            path_blocked = True
                                            critical_warning = "Path blocked ahead."
                                            break
                        
                        if path_blocked:
                            if is_ticking:
                                tick_sound_effect.stop()
                                is_ticking = False
                            if not is_speaking:
                                # We enforce an instant warning dump on an imminent threat without wait buffering 
                                threading.Thread(target=speak_offline, args=(critical_warning,), daemon=True).start()
                        else:
                            if not is_speaking:
                                inst = nav_engine.get_instruction(current_x, current_z, current_yaw)
                                
                                if inst:
                                    # Since earlier revisions pushed output handling as nested strings directly instead of distinct subdictionaries here
                                    audio_queue.put({"type": "text", "msg": inst})

                            play_navigation_tick(current_yaw, nav_engine.target_yaw, screen_width=1024)

                    processed = inference_result_handler(
                        rgb_isp, raw_dets, LABELS, CONFIG_DATA, 
                        vio_data=(total_dist, smooth_yaw, curr_pitch, curr_roll), 
                        target_yaw=nav_engine.target_yaw if STATE == "NAVIGATING" else None, 
                        target_dist=nav_engine.distance_to_wp if STATE == "NAVIGATING" else None,
                        depth_frame=depth_raw, state_text=STATE
                    )
                    
                    # 🚀 RENDER UI
                    cv2.imshow("SENSEY 6-DOF AR Navigator", cv2.resize(processed, (1024, 768)))
                    if cv2.waitKey(1) == ord('q'): break
                    
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run()
