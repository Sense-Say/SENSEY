import subprocess
import time
import os
import signal
import sys

# -------------------------------------------------------------------------
# AUDIO SETUP (MP3 PLAYBACK)
# -------------------------------------------------------------------------
AUDIO_DIR = "/home/raspberrypi/audio_files"

def play_audio(filename):
    """Plays a pre-recorded MP3 file"""
    file_path = os.path.join(AUDIO_DIR, f"{filename}.mp3")
    if os.path.exists(file_path):
        print(f"🔊 PLAYING: {filename}")
        # Run mpg123 in background so it doesn't block code, but give it a sec
        os.system(f"mpg123 -q {file_path} &") 
    else:
        print(f"⚠️ Missing Audio File: {file_path}")

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------

BASE_DIR = "/home/raspberrypi/hailo-apps-infra/hailo_apps/hailo_app_python/apps"
PATH_BEHAVIOR = os.path.join(BASE_DIR, "pose_estimation/pose_estimation.py")
PATH_BLIND = os.path.join(BASE_DIR, "detection/detection.py")

HEF_POSE = "/home/raspberrypi/hailo-apps-infra/resources/models/hailo8/yolov8m_pose.hef"
HEF_DETECT = "/home/raspberrypi/hailo-apps-infra/resources/models/hailo8/yolov8m.hef"

current_process = None

# -------------------------------------------------------------------------
# PROCESS MANAGEMENT
# -------------------------------------------------------------------------

def stop_current_process():
    global current_process
    if current_process:
        print("\n🛑 PINAPAHINTO ANG CURRENT PROCESS...")
        # Optional: play "stopping" sound
        # play_audio("stopping") 
        current_process.send_signal(signal.SIGINT)
        try:
            current_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            current_process.kill()
        current_process = None
        print("✅ HUMINTO NA.\n")

def start_behavior_mode():
    stop_current_process()
    
    # PLAY HUMAN VOICE
    play_audio("behavior_active")
    
    # Give audio a moment to finish before starting heavy AI
    time.sleep(2) 

    global current_process
    print("\n🏫 STARTING: BEHAVIOR MODE")
    
    cmd = [
        "python3", PATH_BEHAVIOR,
        "--input", "/home/raspberrypi/Downloads/STANDING.MOV",
        "--hef-path", HEF_POSE,
        "--show-fps",
        "--disable-sync"
    ]
    current_process = subprocess.Popen(cmd, cwd=os.path.dirname(PATH_BEHAVIOR))

def start_blind_mode():
    stop_current_process()
    
    # PLAY HUMAN VOICE
    play_audio("blind_active")
    
    time.sleep(2)

    global current_process
    print("\n🚶 STARTING: BLIND NAVIGATION MODE")
    
    cmd = [
        "python3", PATH_BLIND,
        "--input", "/dev/video0",
        "--hef-path", HEF_DETECT,
        "--show-fps",
        "--disable-sync"
    ]
    current_process = subprocess.Popen(cmd, cwd=os.path.dirname(PATH_BLIND))

# -------------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------------
def main():
    print("==================================================")
    print("   TAGALOG MASTER CONTROLLER (Natural Voice)      ")
    print("==================================================")
    
    play_audio("startup")
    
    print("   [1] Start Student Behavior Mode")
    print("   [2] Start Blind Navigation Mode")
    print("   [s] Stop / Standby")
    print("   [q] Quit")
    print("==================================================")

    try:
        while True:
            user_input = input("👉 Enter Command (1, 2, s, q): ").strip().lower()

            if user_input == '1':
                start_behavior_mode()
            elif user_input == '2':
                start_blind_mode()
            elif user_input == 's':
                stop_current_process()
                play_audio("standby")
                print("💤 Standby.")
            elif user_input == 'q':
                stop_current_process()
                play_audio("shutdown")
                time.sleep(2) # Wait for audio to finish
                print("👋 Exiting.")
                sys.exit(0)
            else:
                print("❌ Invalid command.")

    except KeyboardInterrupt:
        stop_current_process()
        print("\nExiting.")

if __name__ == "__main__":
    main()