# 21st Progress: VIO Pedometer Perfection & Rotation Shielding

## 🚀 Overview
Following the integration of AprilTag Absolute Relocalization in the 20th progress, the 21st progress finalizes the **Dead Reckoning (Pedometer) Engine**. We achieved a monumental milestone: a custom visual-inertial pedometer that accurately measures real-world distance (verified via physical tape measure at 2.4 meters across multiple sharp turns) without accumulating "ghost distance" from camera panning, hardware shaking, or stereo depth reconstruction.

---

## 🧠 The Core Problem: The "Rotation Leak"
During rigorous testing, a critical hardware phenomenon was discovered: **Stereo Depth Rebuilding**. 
When the user rapidly turned the OAK-D Lite (e.g., 180 degrees in 1 second), the distance would artificially increase. 

**Why this happened:**
1.  **Centripetal G-Force:** Spinning the camera quickly generated physical forces that tricked the Accelerometer Step Gate (`is_stepping = True`).
2.  **The "Snap-Back" Effect:** When the rapid rotation stops, the stereo depth algorithm takes roughly 150-200 milliseconds to re-calculate the depth map. During this micro-delay, pixels "snap" from a blurred depth to their true depth. 
3.  **The False Positive:** The Feature Tracker interpreted this "depth snapping" as a massive forward movement (positive `d_z`), bypassing the standard `!is_rotating` shield because the physical turn had already stopped.

---

## 🛠 Technical Implementation: The "Cooldown" Buffer

To fix this, we transitioned the rotation shield from a "binary switch" to a **Temporal Memory Buffer**.

### The Rotation Cooldown Logic
We introduced `rotation_cooldown = 5`. Instead of instantly re-engaging the pedometer the millisecond the gyroscope stabilizes, the system forces a **5-frame (0.25 second) blind period**.

```python
# 🚀 THE FIX: ROTATION COOLDOWN BUFFER
if abs(gz) > 0.05 or abs(gx) > 0.05 or abs(gy) > 0.05:
    rotation_cooldown = 5 # Reset timer on any twist
                    
if rotation_cooldown > 0:
    is_rotating = True
    rotation_cooldown -= 1
else:
    is_rotating = False

# Pedometer only executes if completely stable
if not is_rotating:
    # ... feature tracking logic ...
```
*Result:* The camera is given time to refocus and stabilize its depth map. The artificial "snap-back" pixels are completely ignored, locking the distance perfectly to `0.00m` during and immediately after a turn.

---

## 📏 Real-World Calibration & Validation

To ensure the system works for a visually impaired user, we abandoned raw camera metrics in favor of **Human Gait Calibration**.

### The Tape Measure Benchmark
*   **Test:** A physical tape measure was laid out. The user walked 80cm, executed a sharp turn, walked another 80cm, turned, and walked a final 80cm.
*   **Result:** The system accurately mapped the total distance traveled to **~2.40 meters**, proving that the `CALIBRATION_SCALE` and `rotation_cooldown` work perfectly in tandem.

### The Math Stack
1.  **Optical Flow Delta (`d_z`):** Capped between `0.01m` and `0.40m` to ignore micro-vibrations and massive depth errors.
2.  **Sliding Window (`smooth_move`):** A 10-frame array averages out the standard positive/negative noise of the stereo sensor to exactly `0.00` when stationary.
3.  **The Scale Factor (`1.66`):** Compensates for features that "slip" off the screen during movement. If the raw math sees 60cm of optical flow, the scale translates it to 100cm of real-world walking.

---

## 🚦 Operational Methodology (O&M Guidelines)

To maximize the accuracy of the 6-DOF mapping, we established a strict protocol for how the system should be physically used during the two operational states:

### 1. RECORDING Mode: "Stop and Shoot"
When building a map, the "Corners" (Turn Nodes) must have a pristine Yaw reading. 
*   **Rule:** The user must walk to a corner, **STOP completely**, turn their body to face the new aisle, and say *"Point Saved."*
*   **Why:** Stopping ensures the IMU is perfectly stable, pinning the "Green Arrow" on the HUD to an exact, wobble-free degree.

### 2. NAVIGATING Mode: "Fluid Flow"
When using a saved map, the user does not need to stop at waypoints.
*   **Rule:** The user simply walks. When the system says *"Reached Point 1. Turn right,"* the user turns and keeps walking in one fluid motion.
*   **Why:** The `motion_window` and `rotation_cooldown` easily handle the temporary camera shaking. The system already possesses the "perfect map" generated during recording, allowing the navigation to be highly forgiving of natural human gait wobbles.

***

**Next Steps (Progress 22):**
With the Audio UI, VIO Pedometer, and AprilTag Anchor systems fully completed and strictly calibrated, the final integration will be **Haptic Hardware**. We will map the 3-Zone Dynamic Safety Shield (Left/Center/Right obstacle warnings) to an ESP32 via Bluetooth Low Energy (BLE) to trigger variable-intensity PWM vibration motors on the user's shoulders/waist.
