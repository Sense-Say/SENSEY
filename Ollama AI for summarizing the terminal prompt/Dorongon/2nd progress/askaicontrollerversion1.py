import subprocess
import time
import os
import signal
import sys
import threading
from collections import deque
from pathlib import Path
from gpiozero import Button
try:
    import ollama
except ImportError:
    print("⚠️ Ollama library not found. Run: pip install ollama")

# -----------------------------------------------------------
# CONFIGURATION & PATHS
# -----------------------------------------------------------
PAUSE_FLAG = "/tmp/hailo_pause"

btn_behavior = Button(17, pull_up=True, bounce_time=0.2)
btn_blind    = Button(22, pull_up=True, bounce_time=0.2)
btn_ask      = Button(27, pull_up=True, bounce_time=0.2)

BASE_DIR = "/home/raspberrypi/SENSEY/Text to Speech Folder/Dorongon/1st progres"
PATH_BEHAVIOR = os.path.join(BASE_DIR, "pose_estimation.py")
PATH_BLIND    = os.path.join(BASE_DIR, "detection.py")
HEF_POSE   = "/home/raspberrypi/hailo-rpi5-examples/resources/models/hailo8/yolov8m_pose.hef"
HEF_DETECT = "/home/raspberrypi/hailo-rpi5-examples/resources/models/hailo8/yolov8m.hef"
AUDIO_DIR  = "/home/raspberrypi/audio_files"

current_process = None
active_mode = 0
log_buffer = deque(maxlen=10)
is_analyzing = False
is_busy = False

# -----------------------------------------------------------
# HELPERS
# -----------------------------------------------------------

def play_audio(filename):
    """Plays a pre-recorded MP3 file from your audio_files folder"""
    file_path = os.path.join(AUDIO_DIR, f"{filename}.mp3")
    if os.path.exists(file_path):
        os.system(f"mpg123 -q {file_path} &")

def speak_text(text):
    """Converts dynamic text to speech using espeak-ng"""
    # -s 150 makes the speech slightly slower and easier to understand
    # -a 200 makes it louder
    clean_text = text.replace("'", "") # Remove quotes to prevent shell errors
    os.system(f"espeak-ng -s 150 -a 200 '{clean_text}' &")

# -----------------------------------------------------------
# AI INTERPRETATION (OLLAMA)
# -----------------------------------------------------------

def explain_scenario():
    global is_analyzing, log_buffer, active_mode
    
    # 1. PRE-CHECK
    if active_mode == 0:
        speak_text("Please select a mode first.")
        return
    
    if is_analyzing:
        print("[DEBUG] AI is already busy.")
        return

    if len(log_buffer) < 2:
        speak_text("Not enough data. Wait a moment.")
        return

    try:
        # 2. START ANALYSIS STATE
        is_analyzing = True
        Path(PAUSE_FLAG).touch() # Tell vision scripts to pause drawing
        
        print("\n[AI] 🧠 Analyzing scene...")
        speak_text("Thinking") 

        # 3. DATA PREPARATION
        raw_text = " ".join(list(log_buffer)).lower()
        found_states = []
        # (Your detection logic here...)
        if "raised: 1" in raw_text: found_states.append("hand raised")
        if "walk: 1" in raw_text:   found_states.append("walking")
        if "stand: 1" in raw_text:  found_states.append("standing")
        if not found_states:
            for obj in ["person", "chair", "laptop", "cup", "door", "bottle"]:
                if obj in raw_text: found_states.append(obj)
        
        detected = ", ".join(set(found_states)) if found_states else "no significant movement"
        prompt = f"Describe in one short sentence what is happening. Use simple words. Data: {detected}."

        # 4. OLLAMA GENERATION
        response = ollama.generate(
            model='qwen2:0.5b', 
            prompt=prompt,
            options={'temperature': 0.1, 'stop': ["\n"]} 
        )
        summary = response['response'].strip().split('.')[0]
        
        print(f"\n[SUMMARY]: {summary}\n")
        speak_text(summary)
        
        # Give the user time to hear the audio
        time.sleep(4)

    except Exception as e:
        print(f"[AI ERROR]: {e}")
        speak_text("Error.")

    finally:
        # 5. THE RESET (This runs NO MATTER WHAT)
        # This is the most important part to allow a 2nd, 3rd, and 4th press.
        print("[SYSTEM] Resetting AI flag and resuming vision...")
        if os.path.exists(PAUSE_FLAG): 
            os.remove(PAUSE_FLAG)
        
        # Small delay to ensure the file system has updated
        time.sleep(0.5) 
        is_analyzing = False

# -----------------------------------------------------------
# MODE MANAGEMENT (Same logic as before)
# -----------------------------------------------------------

def stop_all_ai():
    global current_process, active_mode
    if os.path.exists(PAUSE_FLAG): os.remove(PAUSE_FLAG)
    if current_process:
        print("\n[SYSTEM] 🛑 Terminating AI Processes...")
        try:
            os.killpg(os.getpgid(current_process.pid), signal.SIGKILL)
            current_process.wait(timeout=2)
        except: pass
    os.system("pkill -9 -f pose_estimation.py")
    os.system("pkill -9 -f detection.py")
    time.sleep(5) 
    current_process = None
    active_mode = 0
    log_buffer.clear()

def log_reader_thread(pipe):
    global log_buffer, is_analyzing
    for line in iter(pipe.readline, b''):
        decoded = line.decode().strip()
        if decoded:
            log_buffer.append(decoded)
            if not is_analyzing: print(decoded)

def start_behavior():
    global active_mode, current_process, is_busy
    if is_busy or active_mode == 1: return
    is_busy = True
    stop_all_ai()
    print("\n🏫 ACTIVATING: STUDENT BEHAVIOR")
    speak_text("Classroom mode active")
    current_process = subprocess.Popen(
        ["python3", PATH_BEHAVIOR, "--input", "usb", "--hef-path", HEF_POSE, "--use-frame"],
        cwd=os.path.dirname(PATH_BEHAVIOR),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, preexec_fn=os.setsid
    )
    threading.Thread(target=log_reader_thread, args=(current_process.stdout,), daemon=True).start()
    active_mode = 1
    is_busy = False

def start_blind():
    global active_mode, current_process, is_busy
    if is_busy or active_mode == 2: return
    is_busy = True
    stop_all_ai()
    print("\n🚶 ACTIVATING: BLIND NAVIGATION")
    speak_text("Blind navigation mode active")
    current_process = subprocess.Popen(
        ["python3", PATH_BLIND, "--input", "usb", "--hef-path", HEF_DETECT, "--use-frame", "--disable-sync"],
        cwd=os.path.dirname(PATH_BLIND),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, preexec_fn=os.setsid
    )
    threading.Thread(target=log_reader_thread, args=(current_process.stdout,), daemon=True).start()
    active_mode = 2
    is_busy = False

# -----------------------------------------------------------
# MAIN
# -----------------------------------------------------------
btn_behavior.when_pressed = start_behavior
btn_blind.when_pressed    = start_blind
btn_ask.when_pressed      = explain_scenario

def main():
    speak_text("System online")
    try:
        while True:
            user_cmd = input("👉 Command: ").strip().lower()
            if user_cmd == '1': start_behavior()
            elif user_cmd == '2': start_blind()
            elif user_cmd == 's': stop_all_ai()
            elif user_cmd == 'a': explain_scenario()
            elif user_cmd == 'q':
                stop_all_ai()
                os._exit(0)
    except KeyboardInterrupt:
        stop_all_ai()
        sys.exit(0)

if __name__ == "__main__":
    main()