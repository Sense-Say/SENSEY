# 🎓 SENSEY 13th Progress: Final Production Release

This is the final developmental milestone for Project SENSEY. This phase focused on **Setup Automation**, **Cultural Gesture Logic**, and **Blind-Accessible UI** to transition the project from a prototype to a finished, deployable classroom tool.

## 🚀 Final Revisions & Features

### 1. SENSEY Setup Orchestrator (`sensey_setup.py`)
To ensure the system can be deployed on any Raspberry Pi 5 in minutes, we developed a master installation script. 
*   **Automation:** Installs all 15+ Python libraries, system-level dependencies (GUI & Audio), and AI resources.
*   **Smart Downloader:** Automatically fetches the **Piper TTS binary**, the **Voice Model**, and the **OAK-D Face Detector** only if they are missing.
*   **Environment Protector:** Enforces the specific versions of `OpenCV` and `NumPy` required to prevent Hailo NPU math crashes.

### 2. Philippine-Context Behavioral Logic
The `action_logic.py` was refined to support specific cultural and environmental needs in Philippine schools:
*   **Conducting National Anthem:** Uses a **4-Point Geometric Center** (Midpoint of shoulders and wrists) to create a dynamic "Heart Zone." This allows the system to detect the hand-on-chest gesture regardless of where the student is sitting.
*   **Conducting Patriotic Oath:** Features a **High-Tolerance 90-degree check**. It allows for $\pm 45^\circ$ of elbow movement and $\pm 30^\circ$ of wrist tilt to account for natural human posture during the *Panatang Makabayan*.
*   **Hands-Together (Praying):** Implements a **3D Euclidean Distance** check between wrists ($< 150\text{mm}$) to differentiate from regular sitting.

### 3. Blind Teacher Accessibility (Vocal Interface)
The entire system was converted into a **Voice-First** experience:
*   **Vocal Guidance:** The Face Enrollment GUI now speaks to the teacher, providing instructions on where to turn the student's head (e.g., "Now turn slightly to the left").
*   **System Readiness:** The Master Monitor speaks a confirmation message once the Hailo NPU and OAK-D Lite are fully initialized and tracking.
*   **Zero-Restart Reporting:** Recognition results now appear in roughly **3 seconds** by utilizing background threading, keeping the video feed live while the CPU processes the identity math.

---

## 📂 Final Production Folder Map

| Directory | Contents |
| :--- | :--- |
| **`~/Student Monitoring/`** | `standalone_poseversion2.py`, `cpu_process_screenshot.py`, `action_logic.py`, `name_map.json` |
| **`~/TTS-STT-AUDIO/`** | `fast_face.blob`, `en_US-lessac-medium.onnx`, `piper/` (binary) |
| **`~/Documents/`** | `vpu_face_enrollment.py` (for high-res training) |

---

## 🔧 Final Production Specifications

*   **Processor Balance:**
    *   **Hailo-8 NPU:** 100% Pose Estimation (17 Keypoints).
    *   **OAK-D VPU:** 100% Face Detection (Continuous Boxes).
    *   **RPi 5 CPU:** Behavioral Math, Background Face Matching, and Piper TTS.
*   **Optical Settings:**
    *   **Resolution:** 4:3 Full-Sensor (1344x1008) for maximum vertical classroom view.
    *   **Focus:** Fixed at 0 (Infinity) for mathematical stability.
*   **Audio Output:** Piper TTS at **0.85 Length Scale** (Fast/Clear).

---

## 🏁 Final Step-by-Step Operation Guide

1.  **Environment Check:** Run `python3 sensey_setup.py` to ensure all files and libraries are perfect.
2.  **Enrollment:** Run `cpu_face_enrollment.py`. Follow the voice guide to enroll students.
3.  **Monitor:** Run `standalone_poseversion2.py`. Wait for the device to say "Ready."
4.  **Identify:** Press the **GPIO 26 Button**. Wait ~3 seconds for the names to update on screen and hear the spoken classroom report.

***
**Project SENSEY is now a fully integrated, accessible, and high-performance AI Classroom Assistant.**
