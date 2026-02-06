# 🎓 SENSEY: Integrated Classroom Monitoring System (Phase 3)

### **Hybrid Architecture: Hailo NPU (Pose) + CPU (Identity)**

This update represents the finalized, stable integration of the SENSEY system. It resolves previous resource conflicts (Error 74) by decoupling the high-speed Pose Estimation from the high-accuracy Face Recognition using a process-switching manager.

##  Key Improvements & Features

### 1. Hybrid Processing Engine
*   **Pose Estimation (Continuous):** Runs on the **Hailo-8 NPU** at 30 FPS. This ensures the video feed is smooth and body tracking is instant.
*   **Face Recognition (On-Demand):** Runs on the **Raspberry Pi CPU** using the `face_recognition` library (HOG model). This activates *only* when triggered, preventing CPU overheating and undervoltage.

### 2. Spatial Identity Mapping (The "Sticky Name" Fix)
Previous versions relied on the detection index (0, 1, 2...), which caused names to swap when students moved.
*   **New Logic:** The system now saves the **Bounding Box Coordinates** of every body detected by the Pose AI.
*   **The Match:** When Face Recognition runs, it calculates the center of the face and asks: *"Is this face physically inside Body Box #1?"*
*   **Result:** Names are accurately linked to the correct body, regardless of detection order.

### 3. Action Logic Integration
The system now classifies student behavior into 5 distinct states based on keypoint geometry:
1.  **Raising Hand** (Wrist above Eye line)
2.  **Side Gaze / Cheating** (Nose outside Shoulder bounds)
3.  **Bracing / Boredom** (Elbow supporting Head)
4.  **Body Twist** (Shoulder alignment check)
5.  **Head Down** (Nose below Hip line)

---

##  System File Structure

All custom logic files have been consolidated into `/home/raspberrypi/Documents/` for stability.

| File Name | Location | Function |
| :--- | :--- | :--- |
| **`cpu_face_enrollment.py`** | `~/Documents/` | **GUI Training Tool.** Captures 5 photos per student and creates the `cpu_encodings.pickle` database. |
| **`standalone_poseversion2.py`** | `~/Documents/` | **The Wrapper / Launcher.** Manages the Hailo scheduler and handles the handoff between Pose and Face scripts. |
| **`cpu_process_screenshot.py`** | `~/Documents/` | **The Snapshot Engine.** Runs when 'S' is pressed. Performs spatial matching and updates `name_map.json`. |
| **`action_logic.py`** | `~/Documents/` | **Behavior Rules.** Pure math logic that determines "Raising Hand", etc. |
| **`pose_estimation_utils.py`** | `hailo-apps/...` | **The Core Utility.** Draws the skeleton, reads the Name Map, and calculates FPS. |

---

## 💻 Operational Workflow

This system runs in a specific order to ensure data integrity.

### Step 1: Enrollment (One-Time Setup)
Create the "Brain" of the system.
```bash
python3 /home/raspberrypi/Documents/cpu_face_enrollment.py
```
*   **Action:** Enter a name (e.g., "Edward") and capture 5 photos from different angles.
*   **Output:** Creates `cpu_encodings.pickle`.

### Step 2: Live Monitoring (Daily Use)
Run the Wrapper script. **Do not run the official pose script directly.**
```bash
python3 /home/raspberrypi/Documents/standalone_poseversion2.py
```
*   **State:** The video feed opens. Students are labeled "Student 1", "Student 2" initially. Action logic (Green/Red boxes) is active.

### Step 3: The Identity Snap (Trigger)
When you need to identify the students:
1.  **Click** the video window to ensure it has focus.
2.  **Press 'S'** on your keyboard.
3.  **Process:**
    *   The video freezes (Pose NPU releases the chip).
    *   A screenshot is saved.
    *   The CPU finds faces and matches them to the Pose Bounding Boxes.
    *   The Terminal prints the **Classroom Report** (e.g., `Edward is Raising Hand`).
4.  **Resume:** The video automatically restarts. The labels on screen update to **"Edward"** and **"Michael"**.

---

## 🔧 Technical Implementation Details (For Developers)

### The "Handover" Protocol
To prevent `HAILO_OUT_OF_PHYSICAL_DEVICES`, we implemented a file-based handover:
1.  **Pose Utils** writes `trigger.txt` and calls `os._exit(0)` to kill itself.
2.  **Wrapper Script** detects the exit, verifies `trigger.txt` exists.
3.  **Wrapper** launches `cpu_process_screenshot.py` (which is safe because Pose is dead).
4.  **Wrapper** restarts Pose, which reads the newly generated `name_map.json`.

### Spatial Logic Snippet
The core logic that fixed the naming issue:
```python
# From cpu_process_screenshot.py
if is_point_in_box((face_center_x, face_center_y), pose_box):
    current_map[body_id] = recognized_name
```
This ensures that even if the Pose AI re-orders the array of people, the Name is assigned based on physical location, not array index.

---

## 📊 Sample Output (Terminal)

```text
🚀 Starting Loop Manager (Documents Mode)...
🔵 Starting Pose Monitor...
INFO | common.core | Using HEF from path: /usr/local/hailo/resources/models/hailo8/yolov8m_pose.hef

[USER PRESSES 'S']

🛑 TRIGGER: Exiting Pose to run Face Scan (Spatial Mode)...
📸 Processing Screenshot...
   - Found 2 faces.
   ✅ Linked Edward to Body ID 0
   ✅ Linked Michael to Body ID 1
✅ Name Map Updated.

📊 LIVE CLASSROOM STATUS:
   👉 Edward is Raising Hand
   👉 Michael is Side Gaze
```
