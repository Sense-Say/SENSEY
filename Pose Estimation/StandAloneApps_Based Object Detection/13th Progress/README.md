# 13th Progress: Visual-Inertial Odometry (VIO) & Tactical Compass Navigation

## 🚀 Overview
The 13th progress marks a significant shift in the **SENSEY** navigation logic. We have moved away from computationally expensive 3D AR "carpet" projections to a high-stability **Visual-Inertial Odometry (VIO)** system. This update utilizes the **Hailo-8 (26 TOPS)** for object detection while leveraging the **OAK-D Lite’s BMI270 IMU** and **Feature Tracker** to create a "Game-Style" navigation HUD.

## 🛠 Key Improvements

### 1. Tactical Compass HUD (CODM Style)
*   **360° Sliding Tape:** A horizontal compass slider at the top of the screen provides real-time Yaw feedback in 15° increments.
*   **Pinned Waypoints:** Navigation goals (Green Arrows) are now "pinned" to absolute world degrees. If a point is saved at 90°, the arrow stays locked to the 90° mark on the slider, regardless of camera translation.
*   **Distance Countdown:** Real-time Euclidean distance calculation displayed directly under the target arrow (e.g., `2.5m -> 0.6m`).

### 2. Visual-Inertial Odometry (VIO) Pedometer
*   **Rotational Drift Correction:** Integrated a **Gyroscope Gate**. The pedometer now automatically "freezes" when the user rotates their head or body. This prevents "fake distance" accumulation during stationary scanning.
*   **Z-Axis Depth Filtering:** The system now ignores horizontal pixel shifts (translation) and only calculates distance based on **Median Depth Change (dZ)**.
*   **Outlier Rejection:** Switched from Mean to **Median math** for feature tracking. This allows the system to ignore dynamic obstacles (like students walking past) and focus on the static classroom environment.

### 3. Clew-Style Audio Feedback
*   **Gated Ticking:** The "Watch Tick" audio (`.wav`) is now gated by the **Center Path Boundary**. 
*   **Logic:** The tick sound plays **only** when the Green Arrow is within the center 1/3 of the screen. If the user veers off-course, the sound stops immediately, providing an "Invisible Tunnel" for the blind user.
*   **Non-Blocking Audio:** Migrated to `pygame.mixer` to ensure low-latency audio that doesn't freeze the video feed or conflict with the Piper TTS voice.

### 4. 4:3 Widescreen Optimization
*   **Max FOV:** Switched to **12MP (4:3)** sensor resolution with a custom ISP scale (1344x1008).
*   **Vertical Awareness:** This provides the maximum **54° Vertical FOV**, allowing the teacher to see both floor-level obstacles (backpacks) and high-level landmarks (clocks/signs) simultaneously.

## 📂 Updated JSON Structure
The navigation files now include a 4th data point: **Recorded Yaw**.
```json
[
  [0.0, 0.0, "start", 0.0],
  [0.5, 1.2, "path", 5.2],
  [1.2, 4.5, "point_1", 90.0]
]
```
*The 90.0 represents the absolute heading the teacher was facing when the point was saved, ensuring the HUD arrow is perfectly aligned.*

## 🚦 Operational Workflow
1.  **Record:** Walk a path and save landmarks. The system captures $(X, Z)$ via Feature Tracking and $(Yaw)$ via IMU.
2.  **Navigate:** Load the route. The HUD slider appears.
3.  **Guidance:** Turn until the Green Arrow is centered. Follow the "Tick" sound.
4.  **Safety:** If the ticks stop, you are either facing the wrong way or have drifted physically off the recorded path.

## 💻 Hardware Stack
*   **Raspberry Pi 5** (Host Controller)
*   **Hailo-8 AI HAT+** (YOLOv8 Inference)
*   **OAK-D Lite** (Stereo Depth + BMI270 IMU)
*   **Piper TTS** (Offline Voice Synthesis)

***

**Next Steps:**
*   Integration of **AprilTags** for absolute "Zero-Drift" resets at classroom entrances.
*   **Safety Override:** Linking Hailo-8 "Person/Chair" detections to the audio gate to pause navigation if the path is physically blocked.

---
***

# 13th Progress: Technical Deep-Dive & Implementation Guide

## 🧠 System Philosophy: "The Invisible Tunnel"
The core philosophy of this update is to reduce **cognitive load** for the visually impaired teacher. Instead of the system constantly speaking ("Turn left," "Walk forward"), it creates an **Audio-Spatial Tunnel**. As long as the teacher hears the rhythmic "Tick," they are safe and on-path. Silence indicates a need for correction.

---

## 🛠 Technical Notes for Developers

### 1. Visual-Inertial Odometry (VIO) Fusion
Standard pedometers on mobile phones rely on accelerometers (step counting). In a classroom, a teacher might take small, shuffling steps or move sideways. 
*   **The Solution:** We use **Depth-Weighted Feature Tracking**. By measuring how the distance to static features (corners, posters) changes in millimeters, we calculate movement.
*   **The IMU Gate:** We use the Gyroscope as a "Logic Gate." If the Gyro detects angular velocity > 0.1 rad/s, the pedometer is temporarily disabled. This is the "Anti-Drift" secret that prevents the distance from increasing when the user simply looks around the room.

### 2. The 360° Compass HUD Math
To prevent the "Green Arrow" from jumping when crossing North (359° to 0°), we implemented **Circular Subtraction**:
```python
relative_angle = (target_yaw - current_yaw + 180) % 360 - 180
```
This ensures the arrow always takes the shortest path to the center of the HUD, making the navigation feel smooth and "game-like."

### 3. 4:3 Aspect Ratio & Spatial Awareness
Most AI models use 16:9 (1080p), which crops the top and bottom of the sensor. 
*   **Why 4:3?** For a blind user, the floor (trip hazards) and the ceiling (door signs/clocks) are equally important. By using the full **1344x1008** resolution, we maximize the **Vertical Field of View (54°)**, providing the Hailo-8 with more data to detect objects that would otherwise be "off-screen."

---

## ✅ Pros and ❌ Cons of this Architecture

### Pros
*   **Ultra-Low Latency:** By offloading YOLOv8 to the **Hailo-8 (26 TOPS)** and Depth/Tracking to the **OAK-D Lite**, the Raspberry Pi 5 CPU remains free for Voice Processing and Navigation math.
*   **High Stability:** The combination of IMU + Feature Tracking is significantly more stable than using IMU alone, which typically drifts by 5-10 degrees per minute.
*   **Non-Intrusive Audio:** The "Tick" sound allows the teacher to hear their students' voices clearly, unlike Text-to-Speech which can "drown out" the classroom environment.
*   **Offline Privacy:** 100% of the processing (Vosk STT, Piper TTS, Hailo Inference) happens locally on the Pi 5. No classroom data ever leaves the device.

### Cons
*   **Lighting Dependency:** Because the pedometer relies on the Feature Tracker, it requires a well-lit classroom. In very dark environments, the distance tracking will degrade.
*   **Accumulative Drift:** While VIO is stable, it is not perfect. Over a long 30-minute session, the $(X, Z)$ coordinates may drift by ~5%. (This will be solved in the next progress using AprilTags).
*   **Hardware Bulk:** The combination of the OAK-D Lite and the Hailo-8 HAT+ requires a sturdy chest-mount or harness for the teacher.

---

## 💡 Implementation Highlights (For Replicators)

| Feature | Implementation Detail |
| :--- | :--- |
| **Audio Engine** | Switched to `pygame.mixer`. Unlike `aplay`, it allows for simultaneous "Ticks" and "Voice" without hardware locking. |
| **State Machine** | Uses a "Confirmation Loop" (Yes/No). This prevents the system from accidentally starting a recording if it mishears a student's conversation. |
| **Pedometer Math** | Uses **Median** instead of **Mean**. This makes the system "immune" to a single student walking across the camera view. |
| **HUD Sensitivity** | Set to **12 pixels per degree**. This provides a balance between a smooth sliding feel and enough precision to hit a 0.5m wide aisle. |

---

## 🎯 Best Practices for Testing
1.  **Calibration:** Ensure the OAK-D Lite IMU is calibrated in the environment where it will be used. Magnetic interference from metal desks can affect the initial heading.
2.  **Landmark Selection:** When recording a path, always "Save Point" while looking directly at a high-contrast object (like a door frame or whiteboard edge).
3.  **Walking Speed:** The system is optimized for a natural walking pace (approx. 1.0 m/s). Rapid running or jumping may cause the Feature Tracker to lose "lock."

---

## ⏭️ What's Next?
The next phase of **SENSEY** will introduce **Absolute Relocalization**. We will place **AprilTags** at key classroom junctions. When the camera "sees" a tag, it will instantly reset any accumulated IMU/Pedometer drift to zero, ensuring 100% accuracy for all-day classroom use.

---
---

# 🛠 Code Architecture & Function Reference

The system is divided into two primary Python scripts: the **Orchestrator** (`oakd_blind_runner.py`) and the **Visual Processor** (`object_detection_post_process.py`).

## 1. `oakd_blind_runner.py` (The Brain)
This script manages the hardware (OAK-D, Hailo-8, GPIO), the Voice State Machine, and the Navigation math.

### Key Functions & Logic:
*   **`get_pipeline()`**: 
    *   **Location:** Hardware Initialization.
    *   **Role:** Configures the OAK-D Lite. It unlocks the **4:3 FOV** (1344x1008), sets the **FeatureTracker** to use extra hardware resources (`setHardwareResources(2, 2)`), and locks the camera focus to infinity for consistent AI detection.
*   **`NavigationManager` (Class)**:
    *   **Location:** Logic Layer.
    *   **Function `load_path`**: Filters the JSON data to skip "breadcrumb" points and lock onto actual landmarks (`point_X`).
    *   **Function `get_instruction`**: Calculates the **Euclidean Distance** and the **Target Yaw** (World Degree) required to reach the next point.
*   **`play_navigation_tick()`**:
    *   **Location:** Audio Layer.
    *   **Role:** The "Clew" logic. It calculates if the Green Arrow is within the center 1/3 of the screen. If true, it triggers `tick_sound.play(loops=-1)`. If the user turns away, it calls `.stop()` immediately.
*   **`execute_action()`**:
    *   **Location:** State Management.
    *   **Role:** Handles the "Heavy Lifting" of saving and loading. It ensures that when a point is saved, the **Current Yaw** is recorded as a 4th element in the JSON array. It also uses `os.fsync()` to force the Raspberry Pi to write the navigation file to the SD card immediately.
*   **`run()` (Main Loop)**:
    *   **Location:** Execution Layer.
    *   **Role:** The high-speed loop (30+ FPS). It performs the **IMU Fusion** (Yaw/Pitch/Roll), runs the **Motion-Filtered Pedometer**, and feeds the raw frames into the Hailo-8 NPU for inference.

---

## 2. `object_detection_post_process.py` (The Eyes)
This script handles the AI output and renders the Tactical HUD.

### Key Functions & Logic:
*   **`extract_detections()`**:
    *   **Location:** AI Post-Processing.
    *   **Role:** Takes the raw tensors from the Hailo-8 and converts them into bounding boxes. It maps the 640x640 AI coordinates back to the 1344x1008 widescreen coordinates.
*   **`calculate_spatial_coords()`**:
    *   **Location:** Spatial AI Layer.
    *   **Role:** Crops the Depth Map at the center of a detected object (e.g., a chair) and calculates the **Median Depth**. This tells the teacher exactly how many meters away an obstacle is.
*   **`draw_detections()`**:
    *   **Location:** UI/UX Layer.
    *   **The Compass Slider:** Uses a `for` loop to draw degree markers that "slide" based on the current IMU Yaw.
    *   **The Pinned Arrow:** Calculates the relative offset of the target degree and draws the Green Arrow. It changes the arrow color to **Green** only when it is in the "Safe Center Path."
    *   **Object Labels:** Restores the `[L]`, `[C]`, `[R]` indicators and distance tags (e.g., "Person [C] 2.1m") onto the video feed.
*   **`inference_result_handler()`**:
    *   **Location:** Integration Layer.
    *   **Role:** The bridge between the two scripts. It receives the `target_yaw` and `target_dist` from the Brain and passes them to the UI renderer.

---

## 🔄 Data Flow Summary

1.  **Capture:** OAK-D Lite captures 4:3 RGB + Depth + IMU data.
2.  **Filter:** `run()` loop uses the Gyroscope to decide if the Pedometer should count distance (Visual-Inertial Odometry).
3.  **Think:** Hailo-8 processes the RGB frame to find students and furniture.
4.  **Navigate:** `NavigationManager` looks at the JSON "Breadcrumbs" and calculates the degree the teacher needs to face.
5.  **Feedback (Visual):** `draw_detections` pins a Green Arrow to that degree on the sliding compass HUD.
6.  **Feedback (Audio):** `play_navigation_tick` starts the "Watch Tick" sound if the Green Arrow is centered.
7.  **Voice:** If the teacher says "Update," `speak_offline` (Piper) announces the distance and turn angle.

---

## ⚠️ Critical Implementation Detail: The "Yaw Offset"
When replicating this code, ensure your **IMU Axis Realignment** matches your camera mounting. In our code, we re-mapped the BMI270 axes:
*   `ax, ay, az = raw_accel.x, raw_accel.z, raw_accel.y`
*   `gx, gy, gz = raw_gyro.x, raw_gyro.z, raw_gyro.y`
This ensures that **Pitch is 0** when the teacher is looking straight ahead, and **Yaw increases** correctly when turning right. If your HUD slides the wrong way, you must flip the sign of `gz`.
