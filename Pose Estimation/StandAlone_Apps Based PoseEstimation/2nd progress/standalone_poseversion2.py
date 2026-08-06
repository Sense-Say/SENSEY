import subprocess
import os
import sys
# 1. SETUP ENVIRONMENT
env = os.environ.copy()
env["QT_QPA_PLATFORM"] = "xcb"
env["DISPLAY"] = ":0"

# 2. DEFINE PATHS
PYTHON_EXE = "/home/raspberrypi/hailo-apps/venv_hailo_apps/bin/python3"
SCRIPT_PATH = "/home/raspberrypi/hailo-apps/hailo_apps/python/standalone_apps/pose_estimation/pose_estimation.py"
HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8s_pose.hef"

# 3. CONFIGURE ARGUMENTS (Official Standalone Args Only)
cmd = [
    PYTHON_EXE,
    SCRIPT_PATH,
    "--hef-path", HEF_PATH,     # -n
    "--input", "usb",           # -i
    "--show-fps",               # --show-fps
    "--frame-rate", "15",       # -f
    "--camera-resolution", "sd" # --camera-resolution (sd=640x480, hd=1280x720)
    # "--save-output",          # -s (Uncomment to save)
]

def run_hailo():
    # Change directory so the script finds its internal resource files
    os.chdir(os.path.dirname(SCRIPT_PATH))
    
    print("🚀 Launching Pose Estimation (Official Args Mode)...")
    print(f"📊 Model: {os.path.basename(HEF_PATH)}")
    print("--------------------------------------------------")
    print("⌨️  CONTROLS:")
    print("   - Click Video Window + 'Q' : Quit")
    print("   - Alt + Space             : Window Menu (Minimize/Maximize)")
    print("   - Thonny Red Square       : Force Stop")
    print("--------------------------------------------------")
    
    try:
        # Use Popen to allow Thonny's 'Stop' button to work
        process = subprocess.Popen(cmd, env=env)
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_hailo()