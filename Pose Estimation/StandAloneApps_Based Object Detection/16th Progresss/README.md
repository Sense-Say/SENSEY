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
This is the **16th Progress README.md**, structured as a comprehensive developer guide. It documents the critical implementations of the **Dynamic Safety Override (Proximity Shield)** and the **Thread-Safe Real Voice Recording** system, detailing the profound audio-threading challenges faced and how they were resolved on the Raspberry Pi architecture.

***

# 16th Progress: Dynamic Safety Overrides & Thread-Safe Audio Architecture

## 🚀 Overview
The 16th progress shifts focus from *navigational mathematics* to **User Safety** and **UX Personalization**. We implemented a 3-Zone Dynamic Safety Override that overrides navigation instructions if physical obstacles are present. Furthermore, we replaced AI-transcribed text notes with **Real Voice Audio Notes**, requiring a complete re-architecture of how the Raspberry Pi handles ALSA/PulseAudio hardware threads to prevent deadlocks.

---

## 🧠 Core Concepts Applied

### 1. Dynamic Safety Override (The Proximity Shield)
*   **Concept:** A blind user cannot rely solely on a mapped path if a dynamic obstacle (like a student or a moved chair) enters that path. 
*   **Logic:** We combined the **Hailo-8 2D Bounding Boxes** with the **OAK-D Lite Depth Map**. If the AI detects a `Person` or `Chair`, we sample the depth at the center of that bounding box.
*   **The "Safety Brake":** The primary navigational cue is the continuous "Tick" sound. If an obstacle is detected within the threshold, the system **instantly mutes the Tick**. For a blind user, the sudden cessation of the expected audio signal is the fastest, most intuitive command to "Stop."

### 2. MinZ (Minimum Z) Awareness
*   **Concept:** Stereo depth cameras (like OAK-D) have a physical limitation where objects too close to the lenses (< 0.4m) fail stereo matching, resulting in wildly inaccurate "guesses" (e.g., reporting a wall 10cm away as being 3m away).
*   **Implementation:** We created a **Critical Proximity Shield**. Any detection where the depth registers between `0.1m and 0.6m` triggers an absolute stop, overriding all other logic, and specifies the location: *"Object very close on your left/right/front."*

### 3. Asynchronous vs. Synchronous Audio Handovers
*   **Concept:** The system runs a continuous microphone stream (`sounddevice`) for Vosk Speech-to-Text. To record a user's voice note, we must capture a high-quality `.wav` file *without* Vosk trying to interpret the note as a command.
*   **Implementation:** Instead of using Python libraries that fight over PortAudio locks, we implemented a **Deferred Hardware Handover**. The voice callback sets a global flag (`trigger_voice_note_record`). The Main Thread sees this flag, safely shuts down the Python audio stream, runs a native Linux `arecord` subprocess, and then reboots the Python stream.

---

## 🛠 Problems Encountered & Solutions

### Problem 1: `PulseAudio Timeout` & `Device Unavailable [-9985]`
*   **The Issue:** Attempting to record a 5-second `.wav` file using `sounddevice.rec()` or `pyaudio` while the Vosk `InputStream` was active resulted in immediate ALSA thread crashes. Linux audio servers on the Raspberry Pi aggressively lock USB microphones to a single process.
*   **The Fix:** We abandoned Python-level dual-recording. Instead, we use the native Linux ALSA tool `arecord`. 
    *   *Code applied:* `subprocess.run(['arecord', '-d', '5', '-f', 'S16_LE', '-r', '44100', '-c', '1', note_path])`
    *   We wrap this in a strict sequence: `mic_stream.stop()` -> `mic_stream.close()` -> `arecord` -> `mic_stream.start()`. This guarantees zero hardware contention.

### Problem 2: Freezing the OpenCV Video Feed
*   **The Issue:** Early attempts to record the voice note trapped the script in a secondary `while True` loop or blocked the main thread for 5 seconds. This caused the OAK-D Lite output queues to overflow and the OpenCV video feed to freeze completely.
*   **The Fix:** Single-Threaded Execution with Deferred Flags. The Vosk audio callback runs on a separate thread. When it hears "Yes" to record a note, it raises `trigger_voice_note_record = True` and exits. The main OpenCV loop catches this flag, handles the 5-second `arecord` (which correctly pauses the frame update safely), and then resumes the loop using `continue`, preventing UI tearing.

### Problem 3: AI Voice & Recording Overlap
*   **The Issue:** The system would prompt "Start," but `arecord` would initialize too fast, accidentally recording the AI's own prompt.
*   **The Fix:** Replaced threaded (non-blocking) speech for prompts with synchronous (blocking) `subprocess.run()`. This forces the Python script to wait until Piper has completely finished saying "Start" before opening the microphone for the user. We also added system Beeps (`Front_Center.wav`) as auditory Start/Stop markers.

---

## 📂 Code Implementation Highlights

### The 3-Zone Safety Shield (Inside `run()` -> `NAVIGATING`)
```python
# Check depth at the center of the Hailo-8 bounding box
sample_y, sample_x = int((ymin+ymax)/2*1008), int(cx*1344)
obj_z = depth_raw[sample_y, sample_x] / 1000.0

# 🛑 CRITICAL PROXIMITY SHIELD (< 0.6m) accounts for OAK-D MinZ error
if 0.1 < obj_z < 0.6:
    path_blocked = True
    if cx < 0.33: critical_warning = "Object very close on left."
    elif cx > 0.66: critical_warning = "Object very close on right."
    else: critical_warning = "Object directly in front. Stop."

# 🛑 CENTER PATH BLOCK (< 1.2m)
elif 0.33 < cx < 0.66 and 0.6 <= obj_z < 1.2:
    path_blocked = True
    critical_warning = "Path blocked ahead."
```

### The "Clew-Style" Audio Playback Sequence
```python
# When an Anchor with a .wav note is reached:
if note_file and note_file.endswith(".wav"):
    note_full_path = os.path.join(DOC_PATH, note_file)
    # Using Popen ensures the user's voice plays in the background
    # without freezing the visual pedometer or HUD.
    subprocess.Popen(['aplay', '-q', note_full_path])
```

---

## ✅ Pros and ❌ Cons of this Setup

### Pros
*   **Absolute Thread Safety:** The microphone never crashes, regardless of how many voice notes are recorded.
*   **Human Touch:** Hearing their own voice (or an O&M instructor's voice) reduces the robotic fatigue of standard GPS-style apps.
*   **Fail-Safe Braking:** The combination of stopping the Tick sound *and* issuing a directional warning ("Object on left") provides maximum reaction time for the user.

### Cons
*   **5-Second Freeze:** Because `arecord` is synchronous in the main loop, the visual UI freezes for exactly 5 seconds while recording the note. *(Note: This is acceptable because the user is standing still to leave a landmark note, not actively navigating).*

***

**Next Steps:**
*   Integration of **AprilTags** for absolute global relocalization (Zero-Drift).
*   Implementation of **Haptic Feedback (Vibration Motors)** to run concurrently with the audio "Ticks," providing multi-sensory guidance.
