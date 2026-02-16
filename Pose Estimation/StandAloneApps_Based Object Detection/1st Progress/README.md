***
# 👁️ Blind Navigation System (1st Progress)

**Focus:** Environment Setup & Basic Object Detection Integration

This phase establishes the foundational computer vision capability for the Blind Navigation aid. We successfully integrated the Hailo-8 AI accelerator with a Raspberry Pi 5 to run real-time object detection (YOLOv8) through a custom Python wrapper, allowing for easy execution and debugging within the Thonny IDE.

## 📋 Prerequisites

*   **Hardware:** Raspberry Pi 5 + Hailo AI Hat (Hailo-8).
*   **OS:** Raspberry Pi OS 64-bit (Bookworm).
*   **Camera:** USB Webcam (mapped to `/dev/video0`).
*   **Repository:** The official `hailo-apps` repository must be cloned.

## 🛠️ 1. Installation & Setup

### A. Clone the Repository
We utilize the standalone python applications provided by Hailo.
```bash
cd /home/raspberrypi
git clone https://github.com/hailo-ai/hailo-apps.git
cd hailo-apps
```

### B. Setup Virtual Environment
To prevent library conflicts, all dependencies are installed in a specific virtual environment.
```bash
python3 -m venv venv_hailo_apps
source venv_hailo_apps/bin/activate

# Install core dependencies
pip install "opencv-python<=4.10.0.84" "numpy<2.0" pillow
```

### C. Download AI Models
We use **YOLOv8m** (Medium) for a good balance of speed and accuracy.
```bash
cd /home/raspberrypi/hailo-apps
./download_resources.sh
# Ensures 'yolov8m.hef' is present in resources/models/hailo8/
```

---

## 🚀 2. The Thonny Integration (Wrapper Script)

Directly running complex Hailo command-line scripts in Thonny often causes backend conflicts or "Recursion Errors." To solve this, we created a **Launcher Script**.

### File: `run_object_detection.py`
**Location:** `/home/raspberrypi/Downloads/run_object_detection.py`

This script handles:
1.  **Environment Management:** Sets `QT_QPA_PLATFORM="xcb"` to fix display issues on RPi 5.
2.  **Scheduler Control:** Sets `HAILO_SCHEDULER="1"` to ensure stable NPU access.
3.  **Process Isolation:** Uses `subprocess` to launch the official Hailo detection app cleanly.

```python
import subprocess
import os
import sys

# 1. SETUP ENVIRONMENT
env = os.environ.copy()
env["QT_QPA_PLATFORM"] = "xcb"
env["DISPLAY"] = ":0"
env["HAILO_SCHEDULER"] = "1" 

# 2. DEFINE PATHS
PYTHON_EXE = "/home/raspberrypi/hailo-apps/venv_hailo_apps/bin/python3"
SCRIPT_PATH = "/home/raspberrypi/hailo-apps/hailo_apps/python/standalone_apps/object_detection/object_detection.py"
HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m.hef"

# 3. BUILD COMMAND
cmd = [
    PYTHON_EXE,
    SCRIPT_PATH,
    "--hef-path", HEF_PATH,
    "--input", "usb",
    "--show-fps",
    "--frame-rate", "15"
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
```

---

## 💻 3. How to Run

1.  Open **Thonny IDE**.
2.  Navigate to `/home/raspberrypi/Downloads/`.
3.  Open **`run_object_detection.py`**.
4.  Click the **Green Play Button**.

### Expected Output
*   A window opens showing the live USB camera feed.
*   The system detects common objects (Person, Chair, Bottle, etc.) in real-time.
*   Bounding boxes are drawn around detected objects with confidence scores.
*   FPS counter is visible in the corner.

---

## 🎯 Next Steps
In the upcoming progress updates, we will modify the post-processing logic to provide spatial awareness (Left/Center/Right) and integrate audio feedback for the user.
