# 9th Progress: Heterogeneous Multi-AI Orchestration (NPU + VPU + CPU)

**Focus:** VPU Face Recognition, 1080p Precision, Smurf-Color Correction, and "Wait-for-Handover" Logic.

In this update, SENSEY achieves professional-grade stability and accuracy. We have completely removed Face Recognition from the CPU and moved it to the **OAK-D Lite VPU**, utilizing high-density 512-dimensional vectors (ArcFace) for industrial-strength identification.

## 🚀 Key Improvements & Features

### 1. VPU-Powered Recognition (The "Zero-CPU" ID)
We have migrated from the `face_recognition` CPU library to **ArcFace (MobileFaceNet)** running natively on the OAK-D Lite VPU.
*   **The Math:** Switched from 128-d vectors to **512-d mathematical fingerprints**. 
*   **Privacy by Design:** The system no longer saves raw photos of students. It captures the face math directly into `vpu_encodings.pickle`.
*   **Performance:** CPU load during identification has dropped from 100% (causing undervoltage) to nearly **0%**.

### 2. High-Res Data / Managed-Res Display
We solved the "Zoom" and "Small Window" issues by implementing a dual-resolution pipeline.
*   **Capture (Internal):** The OAK-D captures at **1080p (FHD)**. This provides maximum pixel density for ArcFace to identify students in the back of the classroom.
*   **Visual (GUI):** The live monitor window is automatically resized to **720p (HD)**. This fits perfectly on the Raspberry Pi desktop without sacrificing FOV or resolution quality.

### 3. Natural Color Correction (Smurf Fix)
Resolved the persistent BGR/RGB color-swap conflict.
*   **Logic:** The OAK-D/Hailo NPU pipeline operates in **RGB** for mathematical accuracy. The Master Script now performs a high-speed BGR conversion *just before* the drawing phase, ensuring skin tones look natural in the video feed while the AI math remains sharp.

### 4. Robust Sequential Handover
To ensure the NPU and VPU hardware contexts never conflict, we perfected the **"Pause and Scan"** workflow using a string-based flag system.
*   **Handover:** The utility returns a `"TRIGGERED"` signal $\rightarrow$ Master loop closes Pose $\rightarrow$ Launches Face Scan $\rightarrow$ Restarts Pose. This guarantees 100% hardware stability.

---

## 📂 Updated System Map

All custom logic and AI Blobs are now consolidated into `/home/raspberrypi/Documents/`.

| File Name | Hardware | Role |
| :--- | :--- | :--- |
| **`vpu_face_enrollment.py`** | **VPU** | **Mathematical Enrollment.** Uses ArcFace to save 512-d vectors. |
| **`vpu_process_screenshot.py`** | **VPU** | **Identity Engine.** Runs ArcFace on the 1080p snapshot. |
| **`standalone_poseversion2.py`** | **NPU+VPU** | **Master Orchestrator.** Manages the 1080p/720p scaling and color logic. |
| **`pose_estimation_utils.py`** | **CPU** | **Visual Fusion.** Fuses the 17-point NPU Pose with the VPU Face box. |

---

## 🔧 Installation & Hardware Setup

### 1. Download VPU AI Blobs
You must have the optimized Intel-format blobs in your Documents folder:
```bash
cd /home/raspberrypi/Documents

# 1. Download Face Detector (3-shave retail-0004)
python3 -c "import blobconverter; blobconverter.from_zoo(name='face-detection-retail-0004', shaves=3, version='2021.4', output_dir='/home/raspberrypi/Documents')"
mv face-detection-retail-0004_openvino_2021.4_3shave.blob fast_face.blob

# 2. Download Face Recognizer (6-shave ArcFace)
wget https://raw.githubusercontent.com/luxonis/oak-examples/main/gen2-face-recognition/models/arcface_mobilefacenet_openvino_2021.4_6shave.blob -O arcface.blob
```

### 2. Physical Button (GPIO 26)
*   **Pin 37 (GPIO 26)** $\rightarrow$ Button Side A.
*   **Pin 39 (GND)** $\rightarrow$ Button Side B.

---

## 💻 Operational Workflow

### Phase 1: Enrollment
Run `python3 vpu_face_enrollment.py`. 
*   Follow the guide to capture 15 vectors (Angles: Straight, Left, Right, Up, Down).
*   **Persistence:** The script automatically appends new students to the existing database without overwriting old ones.

### Phase 2: High-Resolution Monitoring
Run `python3 standalone_poseversion2.py`.
*   You will see a wide, 720p natural-color view of the classroom.
*   Press **'S'** or the **Physical Button** to identify everyone on screen.
*   The system will freeze briefly to process the 1080p image on the VPU and resume with updated names.

---

## 📊 Technical Performance Data
*   **Pose Accuracy:** 17 Keypoints (Hailo NPU).
*   **Face Accuracy:** 512-d ArcFace (OAK-D VPU).
*   **Latency:** ~1.5s per identification snap.
*   **Power:** Safe for standard RPi 5 supply (No undervoltage triggered).

---
*Next Progress: Transitioning to **PIPER TTS** for fully offline, high-quality audio reports.*
