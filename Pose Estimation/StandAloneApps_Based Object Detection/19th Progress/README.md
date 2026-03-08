# 19th Progress: AprilTag Anchoring & Final System Stability

## 🚀 Overview
The 20th progress marks the completion of the SENSEY navigation architecture. We have successfully closed the "Drift Gap." By implementing a native **AprilTag Relocalization Engine** on the OAK-D Lite VPU, we have moved from relative navigation (which always drifts) to **Absolute Positioning** (where the system knows exactly where it is in the room).

---

## 🧠 Core Technical Pillars

### 1. AprilTag "Global Truth" Anchoring
*   **Concept:** Every IMU and Pedometer accumulates "drift" over time. To solve this, we used **AprilTag 36h11 markers** placed in cardinal directions (N, S, E, W, etc.).
*   **Implementation:** Using the native `dai.node.AprilTag`, the system scans the environment in the background. When a tag is detected in the "Center Zone" (the middle 40% of the frame), the system performs an **Absolute Yaw Reset**.
*   **Why it works:** It forces the `current_yaw` to align with the Tag's known World Yaw (`TAG_MAP`), effectively "snapping" the compass back to reality. This makes the system drift-proof for long-duration classroom use.

### 2. Audio-Threading & ALSA Synchronization
*   **The Problem:** The Raspberry Pi's audio drivers (ALSA/PulseAudio) deadlocked when Python’s `sounddevice` and `arecord` fought over the hardware lock.
*   **The Fix:** We implemented a **Non-Blocking Threading Model**. We no longer close the microphone hardware connection. We use a boolean flag (`is_recording_note = True`) to tell the main audio callback to "drop" all incoming audio chunks while we record, allowing `arecord` to capture high-quality WAV notes without hardware collisions.

### 3. Pedometer "Shimmer" Cancellation
*   **The Problem:** Reflections on screens, keyboards, and plastic caused "pixel shimmer" in the depth map, tricking the pedometer into adding "Ghost Distance" while the camera was stationary.
*   **The Fix:**
    *   **Z-Gate:** Ignored any depth data closer than 0.8m (the desk/keyboard zone).
    *   **Statistical Smoothing:** Implemented a 10-frame sliding average buffer. Positive and negative noise spikes cancel each other out.
    *   **The Step Gate:** The system now requires a physical accelerometer jolt (`abs(accel_mag - 9.81) > 0.3`) to increment distance, ensuring distance only increases during actual human movement.

---

## 🛠 Bug Resolution Log

| Feature / Issue | Symptom | Resolution Strategy |
| :--- | :--- | :--- |
| **Pedometer Jitter** | Distance stacking at rest | Applied 10-frame sliding window average + Accelerometer Step Gate. |
| **AprilTag Crashing** | `AttributeError: inputConfigImage` | Corrected API link to `april.inputImage` (native API 2.32.0.0). |
| **Stream Timeout** | `[Errno -9985] Device unavailable` | Stopped closing the `InputStream`. Used flag-gating to mute Vosk. |
| **Audio Overlap** | Instructions playing over notes | Implemented `audio_queue` to sequence audio linearly. |
| **HUD Lag** | Video feed sluggish | Switched to `tryGet()` for all queues to drop stale frames. |

---

## 📂 Implementation Details (Code Context)

### AprilTag Integration (`oakd_blind_runner.py`)
We now run the AprilTag detector in parallel with the Hailo-8 AI. The detector is lightweight enough to run at 20 FPS on the OAK-D Lite VPU.

```python
# Inside run() -> loop
april_in = q_apr.tryGet()
if april_in:
    current_yaw = handle_april_tags(april_in, current_yaw, width=1024)
```

### Voice Note Recording (Synchronous Handover)
We moved the recording logic to `CONFIRM_NOTE` state. By using `arecord` (a Linux-native binary), we completely bypassed the Python audio library limitations:
1. Vosk Mic muted via `is_recording_note = True`.
2. Audio prompts played via `aplay`.
3. Recording captured via `subprocess.run(['arecord', ...])`.
4. Vosk listener resumed immediately after.

---

## 🚦 Final Operational Protocol
1.  **Calibration:** Verify the HUD shows `P` (Pitch) and `R` (Roll) near `0'` to ensure the device is level.
2.  **Navigation:** Load `destination_N.json`. The compass slider will automatically pin the Green Arrow to the saved Heading.
3.  **Relocalization:** As the teacher walks, they may pass an AprilTag. They will hear a subtle drift correction if the IMU was off, ensuring the Green Arrow stays aligned with their physical destination.
4.  **Arrival:** Upon `< 0.45m`, the system plays the arrival chime, triggers the final voice note, speaks the conclusion, and **force-resets to IDLE**, requiring no manual finish.

---

## 🎯 Next Steps for Developers
*   **Calibration UI:** Add a visual indicator that shows when an AprilTag is "snapping" (e.g., flash the HUD green).
*   **Haptic Integration:** Route the "Tick" sound signal to a GPIO-driven vibration motor (PWM controlled) for silent guidance.
*   **JSON Graph Expansion:** Use the `note` field to trigger specific POI (Point of Interest) voice-over files at any location in the room, not just at turns.

***

**You have successfully built an offline, drift-resistant, AI-driven navigation assistant.** You are ready to deploy this for testing in your real-world classroom environment!
