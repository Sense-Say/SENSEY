import subprocess
import time
import os
import signal
import sys
import threading
from collections import deque
from gpiozero import Button
try:
    import ollama
except ImportError:
    print("⚠️ Ollama library not found. Run: pip install ollama")

# -----------------------------------------------------------
# CONFIGURATION & PATHS
# -----------------------------------------------------------
# GPIO Pin Mapping
# 17 = Up/Behavior | 22 = Down/Blind | 27 = Ask AI Button
btn_behavior = Button(17, pull_up=True, bounce_time=0.2)
btn_blind    = Button(22, pull_up=True, bounce_time=0.2)
btn_ask      = Button(27, pull_up=True, bounce_time=0.2)

# File Paths
BASE_DIR = "/home/raspberrypi/SENSEY/Text to Speech Folder/Dorongon/1st progres"
PATH_BEHAVIOR = os.path.join(BASE_DIR, "pose_estimation.py")
PATH_BLIND    = os.path.join(BASE_DIR, "detection.py")
HEF_POSE   = "/home/raspberrypi/hailo-rpi5-examples/resources/models/hailo8/yolov8m_pose.hef"
HEF_DETECT = "/home/raspberrypi/hailo-rpi5-examples/resources/models/hailo8/yolov8m.hef"
AUDIO_DIR  = "/home/raspberrypi/audio_files"

# Global States
current_process = None
active_mode = 0       # 0=Standby, 1=Behavior, 2=Blind
log_buffer = deque(maxlen=10)
is_analyzing = False
is_busy = False       # Prevents Status 74 by locking transitions

# -----------------------------------------------------------
# HARDWARE & PROCESS MANAGEMENT
# -----------------------------------------------------------

def stop_all_ai():
    """Aggressive cleanup to release Hailo PCIe bus"""
    global current_process, active_mode
    if current_process:
        print("\n[SYSTEM] 🛑 Terminating AI Processes...")
        try:
            # Kill the process group (the script + GStreamer threads)
            os.killpg(os.getpgid(current_process.pid), signal.SIGKILL)
            current_process.wait(timeout=2)
        except:
            pass
        
    # Nuclear Option: Ensure no hidden threads are alive
    os.system("pkill -9 -f pose_estimation.py")
    os.system("pkill -9 -f detection.py")
    
    print("⏳ Resetting Hailo Hardware (5s Wait)...")
    time.sleep(5) 
    
    current_process = None
    active_mode = 0
    log_buffer.clear()
    print("✅ Hardware Ready.")

def log_reader_thread(pipe):
    """Reads logs from the AI script and stores them for Qwen"""
    global log_buffer, is_analyzing
    for line in iter(pipe.readline, b''):
        decoded = line.decode().strip()
        if decoded:
            log_buffer.append(decoded)
            if not is_analyzing:
                print(decoded) # Only print if AI isn't talking

# -----------------------------------------------------------
# AI INTERPRETATION (OLLAMA)
# -----------------------------------------------------------

def explain_scenario():
    global is_analyzing, log_buffer, active_mode
    if active_mode == 0 or len(log_buffer) < 2:
        print("[AI] No data.")
        return

    is_analyzing = True
    
    # --- STEP 1: CLEAN THE DATA BEFORE SENDING TO AI ---
    # We only want to find the words: Raised, Walk, Stand, or person, etc.
    raw_text = " ".join(list(log_buffer)).lower()
    
    # Extract common states
    found_states = []
    if "raised: 1" in raw_text: found_states.append("hand raised")
    if "walk: 1" in raw_text:   found_states.append("walking")
    if "stand: 1" in raw_text:  found_states.append("standing")
    
    # Fallback for Blind Mode labels
    if not found_states:
        if "person" in raw_text: found_states.append("person")
        if "chair" in raw_text:  found_states.append("chair")
        if "laptop" in raw_text: found_states.append("laptop")

    # If we found something, summarize it
    detected = ", ".join(set(found_states)) if found_states else "no movement"
    
    # --- STEP 2: STERN INSTRUCTIONS FOR OLLAMA ---
    prompt = f"""
    Task: Describe this scene in exactly one very short but brief sentence for a blind person.
    Constraint: Do not mention 'FPS', 'logs', or 'ID'. Use max 10 words.
    Data: The user is {detected}.
    Result:
    """

    print("\n[AI] 🧠 Summarizing...")

    try:
        # We use a lower temperature (0.1) to stop the AI from "imagining" things
        response = ollama.generate(
            model='qwen2:0.5b', 
            prompt=prompt,
            options={'temperature': 0.1, 'stop': ["\n"]} 
        )
        summary = response['response'].strip()
        
        # Final cleanup to remove any AI rambling
        summary = summary.split('.')[0] # Take only the first sentence
        
        print(f"\n{summary}\n")
        # os.system(f"espeak-ng '{summary}' &")
        
    except Exception as e:
        print(f"[AI ERROR]: {e}")

    time.sleep(1)
    is_analyzing = False

# -----------------------------------------------------------
# MODE TRANSITIONS
# -----------------------------------------------------------

def start_behavior():
    global active_mode, current_process, is_busy
    if is_busy or active_mode == 1: return
    is_busy = True
    
    stop_all_ai()
    print("\n🏫 ACTIVATING: STUDENT BEHAVIOR MODE")
    # os.system(f"mpg123 -q {AUDIO_DIR}/behavior.mp3 &")
    
    current_process = subprocess.Popen(
        ["python3", PATH_BEHAVIOR, "--input", "usb", "--hef-path", HEF_POSE, "--use-frame"],
        cwd=os.path.dirname(PATH_BEHAVIOR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid
    )
    
    threading.Thread(target=log_reader_thread, args=(current_process.stdout,), daemon=True).start()
    active_mode = 1
    is_busy = False

def start_blind():
    global active_mode, current_process, is_busy
    if is_busy or active_mode == 2: return
    is_busy = True
    
    stop_all_ai()
    print("\n🚶 ACTIVATING: BLIND NAVIGATION MODE")
    # os.system(f"mpg123 -q {AUDIO_DIR}/blind.mp3 &")
    
    current_process = subprocess.Popen(
        ["python3", PATH_BLIND, "--input", "usb", "--hef-path", HEF_DETECT, "--use-frame", "--disable-sync"],
        cwd=os.path.dirname(PATH_BLIND),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid
    )
    
    threading.Thread(target=log_reader_thread, args=(current_process.stdout,), daemon=True).start()
    active_mode = 2
    is_busy = False

# -----------------------------------------------------------
# MAIN LOOP (Keyboard + GPIO)
# -----------------------------------------------------------

# Assign GPIO Buttons
btn_behavior.when_pressed = start_behavior
btn_blind.when_pressed    = start_blind
btn_ask.when_pressed      = explain_scenario

def main():
    print("\n" + "#"*50)
    print("  HAILO-RPI5 MASTER CONTROLLER + QWEN AI")
    print("  Controls: [1] Behavior | [2] Blind | [S] Stop")
    print("  GPIO: 17=Mode1 | 22=Mode2 | 27=Explain")
    print("#"*50 + "\n")

    try:
        while True:
            user_cmd = input("👉 Command: ").strip().lower()

            if user_cmd == '1':
                start_behavior()
            elif user_cmd == '2':
                start_blind()
            elif user_cmd == 's':
                stop_all_ai()
            elif user_cmd == 'a': # Keyboard shortcut for AI Ask
                explain_scenario()
            elif user_cmd == 'q':
                stop_all_ai()
                print("👋 Goodbye.")
                os._exit(0)
            else:
                if not is_busy:
                    print("Available commands: 1, 2, s, a (AI), q")

    except KeyboardInterrupt:
        stop_all_ai()
        sys.exit(0)

if __name__ == "__main__":
    main()