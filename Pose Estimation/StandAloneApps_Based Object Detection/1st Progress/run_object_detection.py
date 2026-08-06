import subprocess
import os
import sys
import time

# 1. SETUP ENVIRONMENT
env = os.environ.copy()
env["QT_QPA_PLATFORM"] = "xcb"
env["DISPLAY"] = ":0"
env["HAILO_SCHEDULER"] = "1" 

# 2. DEFINE PATHS
PYTHON_EXE = "/home/raspberrypi/hailo-apps/venv_hailo_apps/bin/python3"
SCRIPT_PATH = "/home/raspberrypi/hailo-apps/hailo_apps/python/standalone_apps/object_detection/object_detection.py"
HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m.hef"

# 3. BUILD COMMAND (Fixed Arguments)
cmd = [
    PYTHON_EXE,
    SCRIPT_PATH,
    "--hef-path", HEF_PATH,
    "--input", "usb",
    "--show-fps",
    "--frame-rate", "15"
    # Removed invalid --labels-json argument
]

if __name__ == "__main__":
    
    print("🚀 Launching Blind Navigation System...")
    print(f"📂 Model: {os.path.basename(HEF_PATH)}")
    
    os.chdir(os.path.dirname(SCRIPT_PATH))
    
    try:
        process = subprocess.Popen(cmd, env=env)
        process.wait()
    except KeyboardInterrupt:
        print("\nStopping...")
        process.terminate()