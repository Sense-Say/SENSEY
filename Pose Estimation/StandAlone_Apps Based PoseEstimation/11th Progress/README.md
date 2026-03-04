# 11th Progress: Spatial 3D Fusion & Offline Audio Orchestration

**Focus:** Real-World Coordinate Reprojection, Ground-Height Calibration, and Offline TTS (Piper).

In this 11th Progress, the SENSEY system achieves **Full Spatial Awareness**. We have moved beyond "pixels on a screen" to "objects in a 3D room." By using the teacher's physical height as a constant, the system now calculates every student's joint position relative to the classroom floor.

---

## 🎓 Learning the Architecture: How it works

If you are studying this program, you must understand the **Three Pillars of SENSEY**:

### 1. The Optical Baseline (Fixed-Focus 4:3)
To ensure the math never changes, we lock the OAK-D Lite hardware:
*   **Resolution:** We use the **12MP Sensor** in 4:3 mode ($1344 \times 1008$). This provides the **Maximum Vertical FOV (54°)**, ensuring we see both the ceiling and the floor.
*   **Focus:** Locked at **0 (Infinity)**. This ensures that a student 5 meters away is just as sharp as a student 2 meters away, keeping the ArcFace recognition consistent.

### 2. The 3D Fusion Logic (X, Y, Z in Millimeters)
The system performs a "Spatial Lookup" for every body joint found by the Hailo NPU.
*   **Per-Joint Depth:** We don't just measure the distance to the student's chest. We measure the distance to their **Nose, Wrists, and Shoulders** individually. 
*   **Ground-Height Math:** Since the teacher wears the camera at **1.2m (1200mm)**, we calculate the joint's height from the floor:
    *   `World_Y = (Pixel_Y - Center_Y) * Z_Depth / Focal_Length`
    *   `Ground_Height = 1200mm - World_Y`
*   **Result:** The system knows if a hand is physically $1.5\text{m}$ high or if a head is only $0.8\text{m}$ from the floor.

### 3. The Offline Voice (Piper TTS)
To make the system truly portable, we replaced Google TTS (online) with **Piper TTS** (offline).
*   **Speed:** Piper is optimized for the RPi 5 CPU. We set the `length_scale` to **0.85** for fast, natural classroom reporting.
*   **Reliability:** No internet is required. The system pipes text directly into the audio driver using a high-speed shell command.

---

## 🛠️ Step-by-Step Setup Guide

### 1. Library Installation
Ensure your virtual environment is updated with the interaction and audio libraries:
```bash
source /home/raspberrypi/hailo-apps/venv_hailo_apps/bin/activate
pip install gpiozero rpi.gpio
# Ensure Piper binary is downloaded to ~/Documents/piper/
```

### 2. Hardware Wiring (Physical Snap Button)
*   **Button Pin A:** Connect to **GPIO 26** (Physical Pin 37).
*   **Button Pin B:** Connect to **GND** (Physical Pin 39).
*   *Pressing this button triggers the 1080p high-res face identification scan.*

### 3. Folder Structure Requirements
The following files must be present in `~/Documents/` for the handover logic to work:
*   `cpu_encodings.pickle`: The face database.
*   `cpu_process_screenshot.py`: The identity engine.
*   `action_logic.py`: The behavioral rules.
*   `piper/`: The folder containing the `piper` executable and `.onnx` voice model.

---

## 💻 How to Run the Program

### Phase 1: Enrollment
Run `python3 cpu_face_enrollment.py`. Capture 5 angles of each student. This creates the "math brain" of the classroom.

### Phase 2: Monitoring
Run `python3 standalone_poseversion2.py`. 
1.  The OAK-D Lite starts in **Natural Color 4:3 mode**.
2.  The Hailo NPU starts tracking **17-point skeletons**.
3.  The system identifies students as "Student 1, 2, 3..." by default.

### Phase 3: Identification
Press the **GPIO 26 Button**.
1.  The Pose Monitor saves a **High-Res Screenshot** and **Spatial Box Data**.
2.  The system closes the NPU context (to prevent Error 74) and runs the **Face Recognition**.
3.  The system **restarts automatically**.
4.  **Audio Output:** The Pi speaks: *"Edward and 2 Students are Attentive."*

---

## 📊 Technical Data Readout
*   **Inference Speed:** ~15-20 FPS (Hailo + OAK-D).
*   **Audio Latency:** < 500ms (Piper Offline).
*   **Accuracy:** Millimeter-level 3D joint tracking.
*   **FOV:** 69° Horizontal / 54° Vertical (Maximum possible on OAK-D Lite).

---
*Next Progress (Final): Perfecting the Set B Behavioral Logic - Turning 3D coordinates into advanced student analytics.*
