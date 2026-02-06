import subprocess
import os
import sys
import time

# 1. SETUP
env = os.environ.copy()
env["QT_QPA_PLATFORM"] = "xcb"
env["DISPLAY"] = ":0"
env["HAILO_SCHEDULER"] = "1"

PYTHON_EXE = "/home/raspberrypi/hailo-apps/venv_hailo_apps/bin/python3"
POSE_SCRIPT = "/home/raspberrypi/hailo-apps/hailo_apps/python/standalone_apps/pose_estimation/pose_estimation.py"
HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m_pose.hef"

# Updated Path
SNAP_SCRIPT = "/home/raspberrypi/Documents/cpu_process_screenshot.py"
TRIGGER_FILE = "/home/raspberrypi/Documents/trigger.txt"

cmd_pose = [PYTHON_EXE, POSE_SCRIPT, "--hef-path", HEF_PATH, "--input", "usb", "--show-fps", "--frame-rate", "15"]
cmd_snap = [PYTHON_EXE, SNAP_SCRIPT]

if __name__ == "__main__":
  
    print("🚀 Starting Loop Manager (Documents Mode)...")
    os.chdir(os.path.dirname(POSE_SCRIPT))

    while True:
        # A. RUN POSE MONITOR
        print("\n🔵 Starting Pose Monitor...")
        pose_proc = subprocess.Popen(cmd_pose, env=env)
        pose_proc.wait() 
        
        # B. CHECK WHY IT CLOSED
        if os.path.exists(TRIGGER_FILE):
            print("🔴 Trigger detected! Running CPU Face Scan...")
            os.remove(TRIGGER_FILE)
            
            # Run the Face Processor
            subprocess.run(cmd_snap, env=env)
            
            print("✅ Scan complete. Restarting Pose Monitor...")
            time.sleep(1) 
        else:
            print("🏁 Quit signal received. Exiting.")
            break