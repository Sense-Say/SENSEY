
# 10th Progress: The "Optimized Hybrid" Identity Logic

**Focus:** CPU-VPU Data Handover, Greedy Identity Resolution, and USB Bandwidth Management.

In this 10th Progress, the SENSEY system transitions to a **Hybrid Architecture**. We utilize the **OAK-D VPU** for high-speed face detection and the **Raspberry Pi 5 CPU** for robust face recognition. This combination provides the highest reliability for identifying 20-30 students in a dynamic classroom environment.

## 🧠 Technical Lesson: How the Hybrid Logic Works

When building an advanced system like SENSEY, you encounter hardware limits that simple scripts cannot handle. Here are the three core engineering problems we solved in this phase:

### 1. Managing the USB "Bottle-Neck" (The 5MB Limit)
*   **The Problem:** A high-quality **1080p image** is approximately **6.2 MB**. However, the OAK-D Lite's USB transfer buffer is limited to **5 MB**. Trying to send a 1080p frame to the VPU for detection causes a `RuntimeError`.
*   **The Hybrid Solution:** 
    1.  The Pi **resizes** the screenshot to $300 \times 300$ (only 0.27 MB) on the CPU.
    2.  The **VPU Detector** uses this small image to find face coordinates.
    3.  The **CPU** then uses the **original 1080p image** (stored in RAM) to take high-resolution crops.
*   **Result:** High accuracy for students in the back row without crashing the USB connection.

### 2. Identity Conflict Resolution (Greedy Matching)
*   **The Problem:** In a classroom, two students might look similar (e.g., Edward and Michael). Simple logic might label both as "Edward" if the math score is close.
*   **The Logic:** We implemented a **"Greedy Match"** system.
    1.  The system calculates the similarity of every face against every student in the database.
    2.  It sorts these results from "Highest Confidence" to "Lowest."
    3.  Once a name (e.g., "Edward") is assigned to a body, that name is **locked**. It cannot be used for any other student in that frame.
*   **Result:** No more name-swapping. Every student gets a unique, most-likely identity.

### 3. The "Visibility Reset" (Fail-Safe Student X)
*   **The Problem:** If a student leaves the frame, the system shouldn't "remember" their name in that physical spot if a new person enters.
*   **The Logic:** Every time you press the **Snapshot Button**, the system performs a **Reset**. It deletes the names for all currently visible IDs in the `name_map.json`.
*   **Result:** If the Face AI is not 100% sure about a person, the system defaults them back to **"Student X"** instead of guessing incorrectly.

---

## 📂 System File Roles

| File Name | Process | Engine | Why? |
| :--- | :--- | :--- | :--- |
| **`cpu_face_enrollment.py`** | Enrollment | **CPU** | Creates robust 128-d encodings using the `face_recognition` library. |
| **`cpu_process_screenshot.py`** | Recognition | **Hybrid** | Uses VPU to find the "Where" and CPU to find the "Who." |
| **`standalone_poseversion2.py`** | Monitoring | **NPU+VPU** | Continuous Pose (Hailo) and Face Boxes (OAK-D). |
| **`action_logic.py`** | Behavior | **CPU** | Analyzes 3D Pose math for the 5 classroom rules. |

---

## 🔧 Operational Workflow for New Users

To achieve the results seen in our tests, follow these steps exactly:

### Step 1: High-Quality Enrollment
Run `python3 cpu_face_enrollment.py`. 
*   **Instruction:** You must capture **15 photos** for each student. 
*   **The Key:** Capture the "45-degree profiles" (Left and Right). This allows the system to recognize students even when they aren't looking directly at the teacher.

### Step 2: The Intelligent Monitor
Run `python3 standalone_poseversion2.py`.
*   The teacher sees a **Natural Color Widescreen** view.
*   Students are initially labeled as **"Student 1, 2, 3..."** based on their Pose IDs.

### Step 3: The Snapshot (Handover)
1.  Press the **GPIO 26 Button**.
2.  The Pose NPU **terminates** to free up the hardware.
3.  The **Hybrid Snapshot Processor** runs:
    *   Finds faces spatially.
    *   Matches them using Greedy Logic.
    *   Updates the `name_map.json`.
4.  The Monitor **automatically restarts** and speaks the report: *"Edward and 2 Students are Attentive."*

---

## 💡 Pro-Tip for Accuracy
The **Fixed Focus at 0 (Infinity)** is the most important hardware setting. It ensures that the face pixels are sharp from 1 meter to the back of the classroom. If the lens moves, the face recognition math will fail. Always ensure your scripts have `cam.initialControl.setManualFocus(0)`.

---
*Developed for the SENSEY Classroom Monitoring Project - Integrating Hailo-8 NPU and OAK-D Lite VPU.*
