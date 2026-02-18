from gpiozero import Button
import time
import subprocess
import os
import sys

# Try to import audio, but don't crash if missing
try:
    from gtts import gTTS
    from playsound import playsound
    AUDIO_ENABLED = True
except ImportError:
    print("⚠️ Audio libraries missing.")
    AUDIO_ENABLED = False

# --- CONFIGURATION ---
PIN_BLIND_NAV = 5     # GPIO 5
PIN_STUDENT_MON = 6   # GPIO 6

# File Paths
PYTHON_EXE = "/home/raspberrypi/hailo-apps/venv_hailo_apps/bin/python3"
SCRIPT_BLIND = "/home/raspberrypi/Documents/run_object_detection.py"
SCRIPT_STUDENT = "/home/raspberrypi/Documents/standalone_poseversion2.py"

# Environment
env = os.environ.copy()
env["QT_QPA_PLATFORM"] = "xcb"
env["DISPLAY"] = ":0"
env["HAILO_SCHEDULER"] = "1" 

# --- INITIALIZE SWITCHES ---
# pull_up=True means the pin is HIGH by default.
# When the switch connects to GND, it becomes LOW (is_active).
switch_blind = Button(PIN_BLIND_NAV, pull_up=True)
switch_student = Button(PIN_STUDENT_MON, pull_up=True)

# --- STATE MANAGEMENT ---
current_mode = "STANDBY"
process_handle = None

def speak(text):
    print(f"🔊 Speaking: {text}")
    if AUDIO_ENABLED:
        try:
            tts = gTTS(text=text, lang='en')
            audio_file = "/tmp/mode_feedback.mp3"
            tts.save(audio_file)
            playsound(audio_file)
            os.remove(audio_file)
        except Exception as e:
            print(f"❌ TTS Error: {e}")

def kill_process():
    """Forcefully kills the current active AI process."""
    global process_handle
    
    # 1. Kill the python subprocess we started
    if process_handle:
        print("🛑 Stopping active script...")
        process_handle.terminate()
        process_handle = None
    
    # 2. Run system-wide cleanup to kill the actual Hailo apps
    # This ensures the camera and NPU are freed
    subprocess.run(["pkill", "-9", "-f", "object_detection.py"])
    subprocess.run(["pkill", "-9", "-f", "pose_estimation.py"])
    time.sleep(1) # Give the hardware a second to reset

def start_mode(mode_name, script_path):
    """Starts the requested AI script."""
    global process_handle
    kill_process() # Ensure clean slate
    
    print(f"🚀 Starting {mode_name}...")
    speak(f"{mode_name} Mode Activated.")
    
    try:
        # We change directory so the scripts find their local files
        script_dir = os.path.dirname(script_path)
        process_handle = subprocess.Popen([PYTHON_EXE, script_path], env=env, cwd=script_dir)
    except Exception as e:
        print(f"❌ Error launching script: {e}")

def set_standby():
    """Enters Standby Mode."""
    global process_handle
    # Only speak if we are actually CHANGING to standby
    if current_mode != "STANDBY":
        kill_process()
        print("💤 Entering Standby Mode...")
        speak("Standby M.")

print("🎛️ Master Controller Active. Waiting for switch input...")
speak("System Ready.")

try:
    while True:
        # Check Switch Positions
        # is_pressed means the pin is connected to GND (Switch is ON)
        
        if switch_blind.is_pressed:
            if current_mode != "BLIND":
                current_mode = "BLIND"
                start_mode("Blind Navigation", SCRIPT_BLIND)
        
        elif switch_student.is_pressed:
            if current_mode != "STUDENT":
                current_mode = "STUDENT"
                start_mode("Student Monitoring", SCRIPT_STUDENT)
        
        else:
            # If neither is pressed, the switch is in the CENTER (OFF) position
            if current_mode != "STANDBY":
                set_standby()
                current_mode = "STANDBY"

        time.sleep(0.5) # Check every half second

except KeyboardInterrupt:
    print("\n👋 Exiting Master Controller.")
    kill_process()