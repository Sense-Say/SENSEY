# 7th Progress: Kinect-Style Diagnostic Dashboard & Precision Calibration

**Focus:** Real-World Reprojection (MM), Focal Length Locking, and 17-Point Numerical Readout.

In this update, the SENSEY system introduces a **Diagnostic Dashboard**. This tool is designed to eliminate "guessing" in behavioral logic by providing the exact physical coordinates ($X, Y, Z$) of every joint in millimeters, relative to the camera lens.

## 🚀 Key Features Added

### 1. Fixed-Focus Stability (The "Infinity Lock")
One of the primary hazards of the OAK-D Lite (IMX214 sensor) is its active Auto-Focus. 
*   **The Problem:** As students move, the lens "hunts" for focus. This physical movement changes the camera's focal length, which causes the $Z$ (depth) math to fluctuate and become inaccurate.
*   **The Fix:** We implemented `cam.initialControl.setManualFocus(0)`. By locking the lens at "Infinity," the intrinsic parameters ($fx, fy$) remain constant, ensuring the 3D math is perfectly stable 100% of the time.

### 2. Spatial Reprojection (Pixel to Millimeters)
The system now performs a full mathematical reprojection for all 17 body joints. It no longer just reports pixel positions; it calculates the student's position in 3D space.
*   **The Math:** Using the camera's internal calibration matrix (Intrinsics), the script calculates:
    *   **$X_{mm}$**: Horizontal distance from the lens center.
    *   **$Y_{mm}$**: Vertical distance from the lens center.
    *   **$Z_{mm}$**: Linear distance from the camera (Depth).

### 3. Multi-Student Diagnostic Table
A high-resolution numerical table was added to the UI to allow for "Set B" behavioral logic calibration.
*   **ID Selector:** A segmented toggle allows the developer to switch focus between Student 0, 1, and 2.
*   **17-Point Grid:** Displays a live scrolling table of every joint (Nose, Wrists, Hips, etc.) with color-coded $X, Y, Z$ parameters.
*   **Action Feedback:** Displays the live output of `action_logic.py` alongside the raw numbers to verify trigger accuracy.

---

## 📂 New File Roles

| File Name | Location | Role Update |
| :--- | :--- | :--- |
| **`calibration_gui.py`** | `~/Documents/` | **New Developer Tool.** Split-screen GUI for real-time coordinate calibration and skeleton inspection. |
| **`action_logic.py`** | `~/Documents/` | **3D Refinement.** Now uses the confirmed millimeter distances to trigger "Aggressive Lean" and "Huddle" rules. |
| **`pose_estimation_utils.py`** | `hailo-apps/...` | **Stable Production Script.** Runs the efficient monitor feed without the heavy diagnostic table. |

---

## 🔧 Technical Specification: Reprojection Logic

The core logic used to generate the "Kinect-style" output is as follows:
```python
# Convert 2D Pixel (u, v) and Depth (z) to World MM (x, y, z)
x_mm = (u - center_x) * z_depth / focal_length_x
y_mm = (v - center_y) * z_depth / focal_length_y
```
This ensures that if a student is 2 meters away and moves their hand 10cm to the right, the $X$ value in the dashboard changes by exactly **100mm**, regardless of their distance from the camera.

---

## 📊 Calibration Workflow

### Step 1: Precision Tuning
Run the Diagnostic Dashboard:
```bash
python3 /home/raspberrypi/Documents/calibration_gui.py
```
1.  Stand in the camera field.
2.  Perform a specific action (e.g., Lean Forward).
3.  Note the **Z-difference** between the **Nose** and **Shoulder** rows in the table.
4.  Update your `action_logic.py` with this exact millimeter value to prevent false positives.

### Step 2: Production Run
Once calibrated, return to the high-speed monitor:
```bash
python3 /home/raspberrypi/Documents/oakd_pose_monitor.py
```

---
*Next Progress: Implementation of the "Huddle/Cheating" logic based on 3D Euclidean distances between multiple students.*
