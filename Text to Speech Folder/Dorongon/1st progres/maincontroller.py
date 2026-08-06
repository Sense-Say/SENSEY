import RPi.GPIO as GPIO
import subprocess
import time
import os
import signal
import sys

# --- AUDIO SETUP (TEXT-TO-SPEECH) ---
try:
    import pyttsx3
    # Initialize the engine
    engine = pyttsx3.init()
    # Slow down the speed (default is often too fast)
    engine.setProperty('rate', 150) 
    # Set volume (0.0 to 1.0)
    engine.setProperty('volume', 1.0)
except ImportError:
    engine = None
    print("WARNING: pyttsx3 not installed. Audio disabled.")

def speak(text):
    """Speaks the text aloud using the system speaker"""
    print(f"🔊 SPEAKING: {text}")
    if engine:
        try:
            engine.say(text)
            engine.runAndWait() # This pauses code briefly while speaking
        except Exception as e:
            print(f"Audio Error: {e}")

# --- GPIO CONFIGURATION ---
BUTTON_BEHAVIOR = 23
BUTTON_BLIND = 24
BUTTON_STOP = 25

# --- PATHS & COMMANDS ---
# Base directory for your Hailo scripts
BASE_DIR = "/home/raspberrypi/hailo-apps-infra/hailo_apps/hailo_app_python/apps"
PATH_BEHAVIOR = os.path.join(BASE_DIR, "pose_estimation/pose_estimation.py")
PATH_BLIND = os.path.join(BASE_DIR, "detection/detection.py")

# HEF Models
HEF_POSE = "/home/raspberrypi/hailo-apps-infra/resources/models/hailo8/yolov8m_pose.hef"
HEF_DETECT = "/home/raspberrypi/hailo-apps-infra/resources/models/hailo8/yolov8m.hef"

# Global process holder
current_process = None

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    # Pull-up resistors: Buttons connect Pin to Ground
    GPIO.setup(BUTTON_BEHAVIOR, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BUTTON_BLIND, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BUTTON_STOP, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def kill_process():
    """Stops the currently running AI script"""
    global current_process
    if current_process:
        print("🛑 Stopping background process...")
        current_process.send_signal(signal.SIGINT)
        try:
            current_process.wait(timeout=5)
        except:
            current_process.kill()
        current_process = None

def start_behavior(channel):
    # 1. Stop previous mode
    kill_process()
    
    # 2. Speak status
    speak("Student Behavior Mode, Active.")
    
    # 3. Start new mode
    global current_process
    print("🏫 STARTING BEHAVIOR MODE...")
    
    cmd = [
        "python3", PATH_BEHAVIOR,
        "--input", "/home/raspberrypi/Downloads/STANDING.MOV", # Change to video file path if testing
        "--hef-path", HEF_POSE,
        "--show-fps",
        "--disable-sync"
    ]
    current_process = subprocess.Popen(cmd, cwd=os.path.dirname(PATH_BEHAVIOR))

def start_blind(channel):
    kill_process()
    
    speak("Blind Navigation Mode, Active.")
    
    global current_process
    print("🚶 STARTING BLIND NAVIGATION MODE...")
    
    cmd = [
        "python3", PATH_BLIND,
        "--input", "/dev/video0",
        "--hef-path", HEF_DETECT,
        "--show-fps",
        "--disable-sync"
    ]
    current_process = subprocess.Popen(cmd, cwd=os.path.dirname(PATH_BLIND))

def stop_all(channel):
    kill_process()
    speak("System Standby.")
    print("💤 Standby.")

def main():
    setup_gpio()
    
    # Initial startup sound
    speak("System Ready. Select a mode.")
    print("SYSTEM READY. Waiting for buttons...")
    
    # Add event listeners
    # bouncetime=500 means ignore double-clicks for 0.5 seconds
    GPIO.add_event_detect(BUTTON_BEHAVIOR, GPIO.FALLING, callback=start_behavior, bouncetime=500)
    GPIO.add_event_detect(BUTTON_BLIND, GPIO.FALLING, callback=start_blind, bouncetime=500)
    GPIO.add_event_detect(BUTTON_STOP, GPIO.FALLING, callback=stop_all, bouncetime=500)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        kill_process()
        GPIO.cleanup()

if __name__ == "__main__":
    main()