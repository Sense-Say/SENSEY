from gpiozero import Button
import time
import subprocess
import os
import sys
import threading

# --- CONFIGURATION ---
PIN_BLIND_NAV = 5     # GPIO 5
PIN_STUDENT_MON = 6   # GPIO 6

# 🚀 NEW SSD PATHS
PYTHON_EXE = "/home/raspberrypi/hailo-apps/venv_hailo_apps/bin/python3"
SCRIPT_BLIND = "/home/raspberrypi/BlindNavigation/oakd_blind_runner.py"
# Assuming student monitor also moved to the new folder, update if needed:
SCRIPT_STUDENT = "/home/raspberrypi/Student Monitoring/standalone_poseversion2.py" 

# 🚀 OFFLINE AUDIO PIPER PATHS
PIPER_EXE = "/home/raspberrypi/TTS-STT-AUDIO/piper/piper"
PIPER_MODEL = "/home/raspberrypi/TTS-STT-AUDIO/en_US-lessac-medium.onnx"

# Environment Variables
env = os.environ.copy()
env["QT_QPA_PLATFORM"] = "xcb"
env["DISPLAY"] = ":0"
env["HAILO_SCHEDULER"] = "1" 

# 🚀 ADD THIS LINE: 
# This forces Python to instantly print all logs to your visible terminal!
env["PYTHONUNBUFFERED"] = "1"

# --- INITIALIZE SWITCHES ---
switch_blind = Button(PIN_BLIND_NAV, pull_up=True)
switch_student = Button(PIN_STUDENT_MON, pull_up=True)

# --- STATE MANAGEMENT ---
current_mode = "STANDBY"
process_handle = None

def speak(text):
    """🚀 REVISED: Uses Offline Piper via paplay (Non-blocking)"""
    print(f"🔊 Master Controller: {text}")
    def _speak():
        cmd = f'echo "{text}" | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | paplay --raw --format=s16le --rate=22050 --channels=1'
        subprocess.run(cmd, shell=True)
    # Run in a thread so the physical switch isn't delayed while talking
    threading.Thread(target=_speak, daemon=True).start()

def kill_process():
    """Forcefully kills the active AI process and frees hardware locks."""
    global process_handle
    
    # 1. Kill the Python subprocess with NO MERCY
    if process_handle:
        print("🛑 Stopping active script...")
        process_handle.kill() # 🚀 FIX: Changed from terminate() to kill()
        # 🚀 FIX: Removed process_handle.wait() so it never gets stuck here
        process_handle = None
    
    # 2. Aggressive System-Wide Hardware Cleanup
    # -9 sends the SIGKILL signal directly from the Linux kernel
    subprocess.run(["pkill", "-9", "-f", "oakd_blind_runner.py"], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-9", "-f", "standalone_poseversion2.py"], stderr=subprocess.DEVNULL)
    
    # 3. Free the microphone and speaker
    subprocess.run(["pkill", "-9", "-f", "arecord"], stderr=subprocess.DEVNULL)
    
    # We give the hardware 1 second to drop all USB/PCIe connections before launching the next script
    time.sleep(1)

def start_mode(mode_name, script_path):
    """Starts the requested AI script."""
    global process_handle
    kill_process() # Ensure clean slate
    
    print(f"🚀 Starting {mode_name}...")
    speak(f"{mode_name} Mode INITIALIZING.")
    time.sleep(2) # Give Piper time to say the activation phrase before opening the heavy AI script
    
    try:
        script_dir = os.path.dirname(script_path)
        # Launch the target script
        process_handle = subprocess.Popen([PYTHON_EXE, script_path], env=env, cwd=script_dir)
    except Exception as e:
        print(f"❌ Error launching script: {e}")
        speak("Error launching script.")

def set_standby():
    """Enters Standby Mode."""
    global process_handle
    if current_mode != "STANDBY":
        kill_process()
        print("💤 Entering Standby Mode...")
        speak("Standby Mode.")

print("🎛️ Master Controller Active. Waiting for switch input...")
speak("System BUTTON CONTROL Ready.")

try:
    while True:
        # Check Switch Positions
        if switch_blind.is_pressed:
            if current_mode != "BLIND":
                current_mode = "BLIND"
                start_mode("Blind Navigation", SCRIPT_BLIND)
        
        elif switch_student.is_pressed:
            if current_mode != "STUDENT":
                current_mode = "STUDENT"
                start_mode("Student Monitoring", SCRIPT_STUDENT)
        
        else:
            # CENTER (OFF) position
            if current_mode != "STANDBY":
                set_standby()
                current_mode = "STANDBY"

        time.sleep(0.5) # Check every half second

except KeyboardInterrupt:
    print("\n👋 Exiting Master Controller.")
    kill_process()