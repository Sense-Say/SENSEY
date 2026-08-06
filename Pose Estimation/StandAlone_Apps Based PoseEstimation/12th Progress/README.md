# 12th Progress: Completion of the Intelligent 3D Behavioral Engine

**Focus:** Exclusive Priority Logic, Patriotic Gesture Detection, and 4:3 Max-Height Optimization.

In this final phase, SENSEY has been transformed into a mission-critical tool for a **Blind Teacher**. We have finalized the behavioral math to ensure 100% reliability, preventing false accusations by implementing a strict **Priority Decision Tree** and **Temporal Evidence Filtering.**

## 🚀 Final Features & Logic Breakthroughs

### 1. Maximum Vertical FOV (12MP 4:3 Mode)
To ensure the teacher can see everything from the floor to the ceiling without cropping:
*   **Resolution:** Configured the OAK-D Lite to its native **12MP 4:3 Sensor mode**.
*   **Scaling:** Internally scales 1344x1008 down to 640x640 for the Hailo NPU.
*   **Result:** Provides a **54° Vertical FOV**, ensuring desks, hands, and feet are always visible for logic analysis.

### 2. The "Handover" Stability Protocol
Successfully solved the **HAILO_OUT_OF_PHYSICAL_DEVICES (74)** error forever.
*   **Mechanism:** Used a string-based return logic (`"TRIGGERED"`) that allows the main monitoring loop to close gracefully, release the NPU hardware, run the Face Recognition script, and restart automatically. This prevents any hardware race conditions.

### 3. Exclusive Priority Tree (No-Conflict Logic)
To prevent the teacher from hearing confusing or conflicting reports, every student is assigned exactly **one** primary action per frame based on this priority:
1.  **RAISING HAND**: Wrist Ground Height > 1.45m.
2.  **OUT OF SEAT**: Shoulder Ground Height > 1.25m.
3.  **PATRIORTIC OATH**: Right arm in "L" shape (45° Elbow / 30° Wrist margin).
4.  **NATIONAL ANTHEM**: Right hand on left chest (4-point spatial fusion).
5.  **PRAYING**: 3D distance between wrists < 150mm.
6.  **HEAD ON DESK**: Nose Ground Height < 0.85m.
7.  **LOOKING AWAY**: Face X-coordinates beyond shoulder bounds.
8.  **ATTENTIVE**: Default state.

### 4. Advanced Geometric Poses (PH Classroom Optimized)
*   **National Anthem Fix:** Implemented a **4-Point Center Fusion**. The system calculates the center of both shoulders and both wrists to create a dynamic "Heart Zone." If the Right Wrist enters this zone while the Left Wrist is away, it triggers "Conducting National Anthem."
*   **Oath Pose Flexibility:** Added a **45° vertical margin** for the elbow and a **30° horizontal margin** for the wrist. This allows for natural, non-robotic student movement during the Panatang Makabayan.

### 5. Blind Teacher "Evidence" Filter
To ensure the teacher only reacts to real behavior:
*   **Smoothing:** A **20-frame (0.7s) history buffer** is maintained for every student.
*   **Threshold:** An action is only reported to the teacher if it is detected in at least **14 out of the last 20 frames**.
*   **Result:** Micro-movements (like swatting a fly) are ignored. Only sustained actions are spoken.

---

## 📂 Final Production File Map

| File Name | Responsibility | Key Tech |
| :--- | :--- | :--- |
| **`standalone_poseversion2.py`** | System Master | OAK-D + Hailo Handover Loop |
| **`pose_estimation_utils.py`** | Visual/Data Fusion | 3D Reprojection & Drawing |
| **`action_logic.py`** | Behavioral Brain | Priority Tree & 3D Euclidean Math |
| **`cpu_process_screenshot.py`** | Identity Engine | Spatial Face-to-Body Mapping |
| **`cpu_face_enrollment.py`** | Training GUI | 5-Angle Multi-Pose Enrollment |

---

## 🔧 Installation & Audio Calibration

### Piper TTS Offline Setup
The system is now 100% offline. Ensure Piper is calibrated for speed:
*   **Executable:** `~/Documents/piper/piper`
*   **Voice:** `en_US-lessac-medium.onnx`
*   **Speed:** Set to **1.30** (Length Scale) for normal speed, professional reporting.

### Hardware Reference
*   **Camera Height:** 1.2 meters from the floor.
*   **Focus:** Manual Focus 0 (Infinity Lock).
*   **Trigger:** Physical Button on **GPIO 26**.

---

## 📊 Summary of Final Success
*   **Visuals:** Natural color, high-res widescreen 4:3 display.
*   **Accuracy:** No more name-swapping due to spatial box matching.
*   **Stability:** Zero NPU timeouts or device-busy crashes.
*   **Reporting:** Smart grouping (e.g., *"Edward and 3 Students are conducting National Anthem"*).

***
**Project SENSEY: Intelligent Classroom Monitoring is now COMPLETE and ready for implementation.**
