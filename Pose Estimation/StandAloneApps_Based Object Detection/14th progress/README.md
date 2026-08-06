# 14th Progress: Pedometer Stabilization & Motion-Gated Navigation

## 🚀 Overview
The 14th progress focuses on the "holy grail" of indoor navigation for the visually impaired: **absolute stability**. We successfully eliminated "ghost distance" (accumulated distance while the device is stationary) and refined our VIO (Visual-Inertial Odometry) pipeline to distinguish between real human steps and visual noise (shimmering pixels).

## 🛠 Key Technical Fixes

### 1. The "Ratchet Effect" Solution
*   **The Mistake:** Earlier iterations used "Forward-Only" filtering (discarding negative distance values). This caused positive-only pixel noise to "ratchet" the distance upward even when standing still.
*   **The Fix:** We implemented **Net-Average Motion Gating**. The system now captures both positive and negative depth fluctuations, allowing the "shimmer" to cancel itself out to zero (e.g., +2cm noise + -2cm noise = 0.00m).

### 2. Physical Motion Validation (Accelerometer Gate)
*   **The Problem:** Feature trackers often struggle with reflective surfaces (laptop screens, keyboards, phone glass), treating pixel shimmer as forward movement.
*   **The Fix:** We added a **Physical Step Gate**. The pedometer now ignores all visual data unless the BMI270 Accelerometer detects a physical "jolt" consistent with a human footstep (`accel_mag > 0.4`). If the device is sitting on a desk, distance is hard-locked to zero.

### 3. Dynamic AI Masking (The "Object Shield")
*   **The Problem:** Moving objects (like a student walking past the teacher) were triggering depth changes and confusing the tracker.
*   **The Fix:** We integrated **Inference-First Masking**. The Hailo-8 runs detection on the frame *before* the pedometer logic. Any feature points falling inside an active object bounding box are immediately masked out and discarded, ensuring the pedometer only tracks static background (walls, floor, ceiling).

### 4. Pedometer Smoothing Window
*   **The Fix:** Implemented a **10-frame sliding window average** for motion. By averaging the movement over 1/3 of a second, we eliminate high-frequency jitters from the depth sensor while maintaining high responsiveness for genuine walking.

---

## ✅ Summary of Navigation Logic

| Feature | Logic Applied |
| :--- | :--- |
| **Pedometer** | Median filtering of Depth-Delta (dZ) over 10 frames. |
| **Stability** | Accelerometer Gating (ignores movements without physical jolts). |
| **Masking** | Hailo-8 bounding boxes dynamically block pedometer feature points. |
| **Precision** | Increased tracking to 2 decimal places (`0.00m`) for fine-grained guidance. |
| **Drift Correction** | IMU + Feature Tracker + JSON Yaw Pinned Arrows. |

---

## 📈 Lessons Learned (Reflections for Future Developers)

1.  **The "Shimmer" Trap:** Never rely on depth data alone for a pedometer. Reflective surfaces (screens/keyboards) generate fake depth fluctuations. Always use an **IMU-based motion gate** to confirm if the user is actually walking.
2.  **Order of Operations:** Running AI inference *after* pedometer math creates a one-frame lag that causes jitter. Always run AI detection *first*, then use those boxes to mask the pedometer input for the same frame.
3.  **Positive vs. Net Movement:** Beware of "Forward-Only" filters. If your noise is positive, "Forward-Only" will build distance even at rest. **Always average the raw noise (pos + neg)** and only gate the *result*.

---

## 🚦 Operational Workflow Checklist
1.  **Start:** Run script -> Wait for "System Ready".
2.  **Record:** Button 26 -> "Record [Name]" -> "Yes" -> Walk -> "Point saved" (at landmarks) -> "Finish" -> "Yes".
3.  **Navigate:** Button 26 -> "Navigate [Name]" -> "Yes" -> Follow the "Tick".
4.  **Audio Guidance:** 
    *   **Tick Sound:** Indicates you are in the "Invisible Tunnel" (facing the center path).
    *   **Silence:** You have drifted left/right or are pointed away from the goal.
    *   **Distance Countdown:** Look at the screen (or ask "Update") to see precise 2-decimal distance to your target.

***

**Next Steps:**
*   **AprilTag Drift Reset:** Deploying physical tags in the room to trigger a 0.00m drift reset upon scan.
*   **Haptic Feedback:** Adding vibration motor integration to provide tactile "Left/Right" pulses alongside the audio Ticks.
