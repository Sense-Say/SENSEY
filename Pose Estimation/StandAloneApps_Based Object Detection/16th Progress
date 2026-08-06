# 16th Progress: Audio Sequencing & Robust State-Machine Integration

## 🚀 Overview
The 16th milestone marks the stabilization of the audio-navigation pipeline. We have successfully solved the **"Device Busy/Timeout" hardware locking issues** while establishing a professional sequence of operations for Blind Navigation. The SENSEY system now functions as a true autonomous agent, managing state, sensor fusion, and multi-channel audio without manual user triggers.

---

## 🛠 Major Architectural Upgrades

### 1. Queue-Based Audio Worker Pattern
*   **The Problem:** `Subprocess.run` for `piper` and `aplay` was blocking the Main Loop. Simultaneously, the `sounddevice` Vosk-listener and the Audio-Output system were fighting for the same USB mic, leading to ALSA/PulseAudio Deadlocks (`Device busy` errors).
*   **The Solution:** Implemented a global `audio_queue`. The `NavigationManager` no longer plays sounds directly. Instead, it places audio *tasks* (text, wav, or beeps) into a thread-safe Queue. A background `audio_worker` thread consumes this queue sequentially.
*   **Result:** Audio instructions are perfectly serialized. No more "Reached Point" colliding with "Turn left," and zero audio driver timeouts.

### 2. Arrival Sequence Synchronization
*   **The Problem:** The teacher needed an automated sequence: `Arrival Voice -> Pause -> Play Note -> Next Instruction`. Doing this manually created audio-overlapping bugs.
*   **The Solution:** The `play_sequence` and `NavigationManager` arrival logic now works as a blocking sequence in the background worker. Once you hit an `ANCHOR`, the system initiates the chain and completes it atomically before returning to the next instruction set.

### 3. Pedometer Stabilization (Jolt-Gating)
*   **The Problem:** Pedometer drifting (adding distance while standing still) caused by "Pixel Shimmer" from static surfaces (laptops/screens).
*   **The Fix:** Integrated a 2-stage filter:
    1.  **Accelerometer Jolt-Gate:** Distance is hard-locked to 0.0 unless the IMU detects a specific G-Force spike (footfall) $> 0.3g$.
    2.  **Forward-Only Positive Motion:** Eliminated absolute values (`abs()`) from distance math so positive and negative pixel noise cancels out, while only real forward movement increases total distance.

---

## 💻 Technical Troubleshooting Reference

### Handling `Device Unavailable` [ALSA/PulseAudio Errors]
**Lesson Learned:** You cannot use `sounddevice.rec()` and `vosk_listener.InputStream` simultaneously. 
*   **Current fix:** The audio worker leaves the hardware mic active. If you need to switch tasks, we do **not** close the microphone; we set a global `is_recording_note` flag that "mutes" the Vosk recognizer while leaving the hardware stream open. 

### Why the Distance Measurement is "Accurate"
We moved from a linear breadcrumb list to a **Node Graph**.
1.  **Nodes:** Points saved manually (Points) or automatically at turn-nodes.
2.  **Edges:** The space between nodes. 
3.  **Instruction Trigger:** The system now triggers turn instructions by looking at `current_target_index` and `next_index`—it calculates the angle of the path *after* you have left the current node, eliminating the "instant arrival" bugs we faced.

---

## 🚦 Deployment & Recording Checklist (For New Routes)

1.  **Route Recording:**
    *   Command: `"Record [Name]"` (e.g., "Record Kitchen to Hall").
    *   Walk the path. The script handles the breadcrumb cleaning.
    *   Add landmarks with **"Point saved."**
    *   Use the **Automatic Voice Note Trigger** to add human context (e.g., *"Table here"*).
    *   **Always end** by saying "Finish" or "Stop" so the `.json` graph file saves correctly to the Documents folder.

2.  **Starting Navigation:**
    *   Move to your start location.
    *   Command: `"Navigate [End Name] to [Start Name]"` or vice versa.
    *   The `nav_engine` automatically detects the reverse condition, calls `nav_path.reverse()`, and prompts the user to "Please turn around."

---

## 📝 Directory & Files

*   **`oakd_blind_runner.py`**: The Orchestrator. Manages IMU, VIO (Pedometer), Hailo NPU, and Voice IO.
*   **`object_detection_post_process.py`**: The HUD Processor. Renders the Compass, Safety Indicators (Red boxes/boxes), and Status Bar.
*   **`/home/raspberrypi/Documents/`**: Persistence layer. Stores all `.json` graph files and recorded `.wav` notes.

***

### 🎯 Looking Forward: AprilTag Anchors
Now that the distance accumulation and navigation sequencing are rock-solid, your path is paved for **Absolute Relocalization**. By integrating the `dai.AprilTag` pipeline (Phase 16), we can turn the classroom into a coordinate system. The system will look for specific AprilTag IDs on your N, S, E, W walls to "zero-out" IMU drift, ensuring the teacher stays aligned even on hour-long routes.

**This baseline code is ready for final deployment.** All logic gates are closed, thread safety is established, and the audio experience is optimized.
