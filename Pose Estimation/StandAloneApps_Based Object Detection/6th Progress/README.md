# 🧭 Blind Navigation System (6th Progress: The Navigation Brain)

**Focus:** Manual VIO Engine, Pedometer Implementation, IMU Integration, and Navigation Dashboard.

In this 6th phase, the system moves beyond simply identifying obstacles. We have implemented a custom **Visual-Inertial Odometry (VIO)** engine. This allows the device to act as a high-tech "Pedometer" and "Compass," tracking the user's total distance traveled and their current heading (Yaw) without relying on external GPS or paid SDKs.

---

## 🧠 The "Navigation Brain" Logic

Unlike standard motion tracking, which relies on error-prone accelerometers, our system uses a **Hybrid Optical-Inertial approach**:

### 1. Heading Tracking (Inertial)
We utilize the **BMI270 IMU** inside the OAK-D Lite to track rotation.
*   **The Challenge:** The BMI270 on the OAK-D Lite provides **RAW Gyroscope data** (radians per second), not pre-calculated angles.
*   **The Solution:** We implemented **Euler Integration**. The script samples the Gyro's Z-axis at high speed, calculates the time delta ($dt$), and integrates the velocity to determine the user's **Yaw (Heading)** in degrees.
*   **Result:** A stable "Digital Compass" that tells the user if they are turning left or right.

### 2. Distance Traveled (Visual Pedometer)
We utilize the **OAK-D Feature Tracker** to calculate physical displacement.
*   **Mechanism:** The OAK-D tracks dozens of high-contrast "features" (edges, corners) in the room using the Left monochrome camera.
*   **Depth Fusion:** For every tracked feature, we query the **Depth Map** to find its exact distance ($Z$) from the user.
*   **The Math:** If a tracked point moves from $3.0m$ away to $2.8m$ away between two frames, the system concludes the user has moved forward exactly **0.2 meters**. 
*   **Robustness:** We average the displacement of all valid features and apply a "Motion Filter" (0.01m to 0.30m) to ignore sensor noise and glitches.

---

## 🎨 Integrated Navigation UI

The display now features a **Navigation Dashboard** at the bottom of the screen, providing a real-time summary of the user's journey.

*   **Overlay:** A semi-transparent black bar to ensure text readability.
*   **NAV Stats:** Displays total accumulated distance in meters (e.g., `NAV: 12.45m`).
*   **HEAD Stats:** Displays the current body heading in degrees (e.g., `HEAD: 90 deg`).
*   **Object Tags:** Objects are now labeled with three pieces of data: `[Class] [Zone] [Distance]`.
    *   *Example:* `Chair [LEFT] 1.2m`

---

## 🏗️ Hardware Orchestration (The Three-Way Split)

This progress represents the ultimate balance of the Raspberry Pi 5 system architecture:

1.  **Hailo-8 NPU**: Handles the **Visual Brain** (YOLOv8 Object Detection).
2.  **OAK-D Lite VPU**: Handles the **Spatial Brain** (Stereo Depth Map + Feature Tracking).
3.  **Raspberry Pi 5 CPU**: Handles the **Logic Brain** (IMU Integration, Pedometer Math, and UI Rendering).

---

## 📂 Updated Software Roles

| File | Location | Modification |
| :--- | :--- | :--- |
| **`oakd_blind_runner.py`** | `~/Downloads/` | **Master Runner.** Now manages the OAK-D Feature Tracker, IMU BMI270 data stream, and the VIO state variables. |
| **`object_detection_post_process.py`** | `hailo_apps/...` | **UI Engine.** Updated `inference_result_handler` to accept `vio_data` and render the Navigation Dashboard. |

---

## 🔧 Technical Notes: BMI270 Constraints

During this phase, we resolved a critical hardware constraint regarding the OAK-D Lite's IMU:
*   **Error:** `GYROSCOPE_CALIBRATED` is unsupported on BMI270 sensors.
*   **Fix:** The pipeline was updated to use `GYROSCOPE_RAW`. We manually handle the conversion and time-syncing on the host CPU to ensure accurate heading calculations.

## 🔭 Next Steps
With the "Navigation Brain" working, we are now ready to implement **Audio Guidance**. The system will soon be able to say: *"Walk forward 5 meters, then turn 90 degrees right to avoid the chair."*
