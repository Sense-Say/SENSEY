# Hailo-8 Pose Estimation for Raspberry Pi 5

This project provides an optimized implementation of YOLOv8 Pose Estimation using the Hailo-8/8L AI Accelerator on a Raspberry Pi 5. It includes custom UI enhancements (Real-time FPS and Person ID/Score labels) and a wrapper system to run seamlessly within the Thonny IDE.

## 📋 Prerequisites

* **Hardware**: Raspberry Pi 5 + Raspberry Pi AI Kit (Hailo-8L) or Hailo-8 PCIe Drive.
* **OS**: Raspberry Pi OS 64-bit (Bookworm).
* **Python**: 3.11 or 3.13 (Managed via Virtual Environment).
---
# Hailo-8 Pose Estimation: Implementation & UI Logic Guide

This guide explains the technical revisions made to the official Hailo standalone pose estimation application to ensure compatibility with **Raspberry Pi 5** and to enhance the **User Interface (UI)** for real-time monitoring.

## 🛠️ 1. Library Installation & Environment
To ensure the Hailo-8 hardware communicates correctly with the Python environment, the following dependencies are required:

* **OpenCV (`<=4.10.0.84`)**: Provides the graphical window and drawing functions.
* **NumPy (`< 2.0`)**: **Critical.** Hailo's pre-compiled drivers are incompatible with NumPy 2.0+. 
* **DepthAI**: Installed to prepare the environment for future OAK-D camera integration.
* **PyYAML & Pillow**: Required for internal model configuration and image handling.

### Setup Virtual Environment
Create a dedicated environment and install dependencies. **Note:** Hailo requires `numpy < 2.0`.
```bash
python3 -m venv venv_hailo_apps
source venv_hailo_apps/bin/activate

# Install specific versions to ensure compatibility
pip install "opencv-python<=4.10.0.84" "numpy<2.0" pillow python-dotenv PyYAML depthai
```

### Download Models
Download the pre-compiled `.hef` files:
```bash
./download_resources.sh
```
---
## 🖥️ 1.2. Thonny IDE Configuration

To run Hailo scripts in Thonny without import errors:
1. Open **Thonny**.
2. Go to **Run** -> **Configure interpreter...**
3. Select **Local Python 3**.
4. Set the path to: `/home/raspberrypi/hailo-apps/venv_hailo_apps/bin/python3`.
5. Click **OK**.
---

## 🚀 2. The Wrapper Script Logic (`standalone_poseversion2.py`)

The primary goal of this script is to act as a "Subprocess Bridge." Here is why we implemented specific logic blocks:

### A. Thonny `RecursionError` Fix
**Reason**: Thonny injects hidden background arguments (like `--port`) when running scripts. The Hailo `argparse` system sees these as "unknown," triggers an error loop, and crashes with a `RecursionError`.
**The Fix**: We used `subprocess.Popen` to launch a fresh Python process. This ensures the Hailo application only sees the specific arguments we provide (`--hef-path`, `--input`, etc.), bypassing Thonny's interference.

### B. Raspberry Pi 5 Display Fix (Wayland vs. XCB)
**Reason**: RPi 5 uses the Wayland display compositor by default. Many OpenCV/Qt versions lack the Wayland plugin, resulting in a "plugin not found" error.
**The Fix**: 
* `os.environ["QT_QPA_PLATFORM"] = "xcb"`: Forces the app to use the X11 compatibility layer.
* `os.environ["DISPLAY"] = ":0"`: Directs the video window to the main HDMI output.

---

## 🎨 3. Utility Revisions (`pose_estimation_utils.py`)

We revised the `visualize_pose_estimation_result` function to transform it from a basic diagnostic tool into a professional monitoring interface.

### A. Real-Time On-Screen FPS
**Reason**: The official script only prints FPS to the terminal. To monitor performance while looking at the video, the data must be overlaid on the frames.
**Logic**: We implemented a timestamp comparison (`time.time()`) within the visualization loop. By calculating the difference between the current and previous frame time, we generate a live FPS counter updated at every frame.

### B. Advanced Labeling: "Person [ID]: Score"
**Reason**: The original code only showed a raw detection score or a generic number on the head, making it difficult to distinguish individuals or judge model confidence.
**Logic**: 
* **Enumeration**: We added a counter to label detections as "Person 1", "Person 2", etc.
* **Float Conversion**: We added `float(detection_score)` to resolve a `TypeError`. In some versions, the score is returned as a 0-dimensional Numpy array which causes f-string formatting to crash.
* **Visual Backgrounds**: We added solid `cv2.rectangle` backgrounds behind the text to ensure readability regardless of the lighting or background complexity.

### C. Visual Color Coding
**Reason**: The default skeleton lines were difficult to see against certain backgrounds.
**Logic**: 
* **Bounding Boxes**: Set to Blue `(255, 0, 0)` for clear person-tracking boundaries.
* **Skeletons**: Changed to Yellow `(0, 255, 255)` to provide high contrast against the blue boxes and skin tones.
* **Joints**: Set to Magenta `(255, 0, 255)` for precise joint-point localization.

---

## 🎮 4. Operational Guide

### Control Interactions
* **`Q` Key**: Standard exit command. The script listens for this keypress on the video window to safely close the Hailo hardware session.
* **`Alt + Space`**: On RPi 5, the `xcb` layer may hide the window title bar. This keyboard shortcut forces the system menu to appear, allowing the user to Minimize or Maximize the feed.
* **Thonny Stop Button**: Because we used `subprocess.Popen`, clicking the red Stop button in Thonny sends a `SIGTERM` signal, killing the video window and the background process simultaneously.

### Summary of HEF Pathing
The script is configured to look for the **Hailo-8** model path by default. For users with the **AI Hat+**, the script includes logic to fall back to the `hailo8l` (Lite) resources to prevent architecture mismatch errors.

## 📁 Project Structure
* `hailo-apps/` : Main repository.
* `resources/models/` : Storage for `.hef` model files.
* `pose_estimation_utils.py` : UI drawing and post-processing logic.
* `run_pose.py` : Main entry point for Thonny users.

---
*Developed for Raspberry Pi 5 AI Kit with Hailo-8 Accelerator.*
