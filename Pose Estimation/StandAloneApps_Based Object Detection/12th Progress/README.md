#  Blind Navigation System (12th Progress: 6-DOF Precision & Logic Calibration)

**Focus:** IMU Axis Realignment, 6-DOF Complementary Filtering, Object Class Remediation, and Mathematical Coordinate Normalization.

In this 12th phase, the SENSEY system has achieved **Total Mathematical Alignment**. We moved beyond simple 2.5D overlays to a stabilized 3D environment. This phase was dedicated to fixing the "fuzzy" sensor behavior, correcting the object detection labels, and ensuring that the navigation math follows real-world physical laws.

---

##  Key Technical Lessons & Revisions

### 1. The "180 = 20" Yaw Accuracy Fix
**The Problem:** Previously, turning 180 degrees only registered as ~20 degrees in the software.
**The Cause:** The Raspberry Pi CPU was busy with AI inference and was "skipping" incoming IMU data packets. 
**The Solution:** We migrated from `q_imu.tryGet()` to **`q_imu.tryGetAll()`**.
**Lesson:** In high-speed robotics, you must empty the hardware buffer completely every frame. By processing every micro-movement captured by the OAK-D during the "AI sleep time," we restored 100% accuracy to the turn calculation.

### 2. IMU Axis Realignment (Optical Frame Sync)
**The Problem:** Pitch was reading 70-80 degrees when looking forward, and Roll was oscillating wildly.
**The Cause:** The BMI270 IMU chip is mounted at a different orientation than the camera lenses. The math thought "Forward" was "Down," leading to a mathematical singularity known as **Gimbal Lock**.
**The Solution:** We remapped the raw data to align the IMU's $Y$ and $Z$ axes with the camera's optical path.

```python
# Re-mapping raw IMU data to Optical Frame
ax, ay, az = raw_accel.x, raw_accel.z, raw_accel.y
gx, gy, gz = raw_gyro.x, raw_gyro.z, raw_gyro.y
```

### 3. Coordinate Normalization (0-Centering)
**The Problem:** Roll was centered at 180 degrees, making the AR path jump whenever the user wobbled.
**The Logic:** We recalibrated the **Complementary Filter** to anchor the system at 0.
*   **Pitch:** 0° when facing the horizon.
*   **Roll:** 0° when standing straight.
*   **Yaw:** Left is now **Positive (+)** and Right is **Negative (-)** to match standard Cartesian navigation math.

```python
# Complementary Filter: Blending Gyro (Speed) and Accel (Gravity)
curr_pitch = 0.98 * (curr_pitch + gx * dt) + 0.02 * accel_pitch
curr_roll = 0.98 * (curr_roll + gy * dt) + 0.02 * accel_roll
```

### 4. Object Class Remediation
**The Problem:** Every detected object (TV, Chair, Table) was being labeled as a "Person."
**The Cause:** The post-processor was flattening the Hailo output tensor incorrectly, losing the Class ID index and defaulting to index `0`.
**The Solution:** We implemented a robust enumeration loop that preserves the `class_id` during the extraction phase.

```python
for class_id, class_list in enumerate(detections):
    # class_id now correctly represents COCO indices (56=chair, etc.)
    for det in class_list:
        score = float(np.array(det[4]).flatten()[0])
        all_detections.append((score, class_id, box))
```

---

##  Updated Software Roles

| File | Modification Focus |
| :--- | :--- |
| **`oakd_blind_runner.py`** | Implements the **High-Precision IMU Fusion** loop. Manages the 6-DOF state variables and handles the 2nd-stage Voice Confirmation logic. |
| **`object_detection_post_process.py`** | Implements **Robust Tensor Extraction**. Renders the 6-DOF Dashboard and projects the 3D Red Checkpoint cylinders onto the floor. |

---

## 🛠️ Operational Guide: Interaction States

The system now follows a strict conversational protocol for safety:

1.  **Trigger:** Tap Button 26 (GPIO 26).
2.  **Voice Input:** System says *"Listening"*. You say *"Navigate door to desk"*.
3.  **Confirmation:** System says *"You said navigate door to desk. Is this correct?"*
4.  **Automatic Re-Listen:** The system opens the mic automatically. You say *"Yes"*.
5.  **Execution:** System loads the path and provides the first turn-by-turn instruction.

---

## 📊 6-DOF Dashboard Verification
When standing straight and looking forward, the user should verify the following values on the dashboard:
*   **NAV:** 0.0m (Starting Point)
*   **YAW:** 0 (Heading Center)
*   **PITCH:** 0 (Horizontal Level)
*   **ROLL:** 0 (Lateral Level)

##  Value for Blind Navigation
This phase transforms the device from a shaky experimental tool into a **Stable Spatial Navigator**. The 6-DOF alignment ensures that the "Blue Carpet" path stays glued to the actual floor even as the teacher moves their torso, and the fixed object detection ensures they are warned about a "Chair" rather than a "Person" blocking the way.

##  Future Progress: Phase 13
The project is now mathematically and visually stabilized. Phase 13 will focus on **Proximity Haptics**—connecting the ESP32 via BLE to provide physical vibration alerts when the user deviates from the AR path or approaches a detected object.
