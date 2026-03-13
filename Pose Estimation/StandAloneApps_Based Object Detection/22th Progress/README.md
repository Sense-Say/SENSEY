# 22nd Progress: 3-Zone Proximity Shield & Thread-Safe Audio Handover

## 🚀 Overview
The 22nd progress represents a major milestone in **User Safety** and **Hardware Stability**. We successfully bypassed the inherent physical limitations of stereo depth cameras (MinZ errors) by fusing depth data with 2D Bounding Box "Fill Ratios". Additionally, we solved the notorious Linux ALSA/PulseAudio deadlock issues (`Device Unavailable -9985`), creating a perfectly thread-safe pipeline for seamless Voice Note recording.

---

## 🧠 Core Technical Pillars

### 1. The 3-Zone Dynamic Safety Shield
*   **The Hardware Limitation:** Stereo depth cameras (like the OAK-D Lite) suffer from "Minimum Z" (MinZ) errors. If an object is closer than 0.4m, the stereo matching algorithm fails, often returning `0.0m` or "hallucinating" a distance of `2.0m+`. 
*   **The AI Solution (Fill Ratio):** To prevent the user from walking into objects that the depth camera miscalculates, we implemented a **Screen Occupancy Gate**.
    *   *The Math:* `fill_ratio = box_area / ZONE_AREA`. If a Hailo-8 bounding box covers more than 50% of a specific vertical zone (Left, Center, or Right), the system assumes the object is at point-blank range, regardless of what the depth map claims.
*   **Contextual Overrides:**
    *   **Left/Right Zones (< 0.5m & > 50% Fill):** Triggers a non-blocking voice warning: *"Person is very close on your front left."*
    *   **Center Zone (< 0.7m OR > 50% Fill):** Triggers a **Critical Halt**. The navigation `Tick` sound is instantly muted, and the system announces: *"Path blocked ahead."*

### 2. Thread-Safe Audio Hardware Handover
*   **The OS Limitation:** The Raspberry Pi's audio server aggressively locks USB microphones to single processes. Attempting to record a 5-second `.wav` using `arecord` or `pyaudio` while `sounddevice` was actively listening for Vosk resulted in fatal `pthread_join` deadlocks and `PaErrorCode -9985` (Device Busy) crashes.
*   **The "Muted Sponge" Architecture:**
    *   We abandoned multi-process recording. Instead, we use the *already active* `sounddevice` stream. 
    *   When the user confirms a Voice Note, the system sets `is_recording_note = True`. This acts as a software gate, forcing the Vosk callback to drop frames.
    *   A synchronous `sd.rec()` command captures the raw `int16` array in the background thread. Because `sounddevice` manages both streams internally, PulseAudio never panics.

### 3. Asynchronous Audio Queue (`paplay`)
*   **The Issue:** Playing overlapping audio files via `subprocess.run` caused "Device or resource busy" errors.
*   **The Fix:** Migrated all audio outputs (Piper TTS, Beeps, Arrival Chimes) to a single-threaded Python `Queue` executing Linux `paplay` (PulseAudio Play). This allows the OS to mix multiple audio streams seamlessly without hardware lockouts.

---

## 🛠 Bug Resolution Log

| Error / Bug | Root Cause | Resolution Strategy |
| :--- | :--- | :--- |
| `ValueError: Truth value of an array... is ambiguous` | Hailo-8 returns confidence scores as `[0.55]` instead of `0.55` in certain tensor layers. | Applied NumPy flattening: `float(np.array(det[4]).flatten()[0])`. |
| `UnboundLocalError: 'is_ticking'` | Python assumed `is_ticking` was local when executing `tick.stop()` during a safety override. | Enforced `global is_ticking` definition explicitly inside the `run()` namespace. |
| **Instant Voice Note Skipping** | Audio driver initialization lagged, causing `sd.rec` to skip the 5-second block. | Implemented a strict blocking `sd.wait()` coupled with system beeps (`Front_Center.wav`) to delineate the recording window. |

---

## 📂 Code Implementation Highlights

### The "Fill Ratio" Safety Math
This block runs continuously during navigation to protect the user from MinZ hardware blindspots:

```python
# Calculate bounding box area vs Screen Zone area
x1, y1, x2, y2 = int(xmin*WIDTH), int(ymin*HEIGHT), int(xmax*WIDTH), int(ymax*HEIGHT)
box_area = (x2 - x1) * (y2 - y1)
fill_ratio = box_area / ZONE_AREA

# Center Blocked Logic
if 0.33 < cx < 0.66:
    if obj_z < 0.7 or fill_ratio > 0.5:
        path_blocked = True
        critical_warning = f"{label_name} blocks your path."
```

### The Thread-Safe Mic Reassignment
Instead of killing the stream, we lock Vosk out of the buffer:

```python
# Inside audio_callback:
if is_recording_note:
    return # Block Vosk from interpreting the Voice Note as a command!

# Inside handle_voice_command (Background Thread):
is_recording_note = True
myrecording = sd.rec(int(5.0 * 44100), samplerate=44100, channels=1, dtype='int16')
sd.wait() # Freezes this specific thread for 5s, but keeps OpenCV/Pedometer alive!
wav.write(note_path, 44100, myrecording)
is_recording_note = False
rec.Reset() # Wipes Vosk buffer to prevent phantom commands
```

---

## ✅ System Status & UX
The system is now fully conversational and spatially aware. 
*   If the teacher walks too close to a desk, the ticks stop, they hear "Desk blocks your path," and they can simply step around it. Once the `fill_ratio` drops below 50%, the ticks instantly resume.
*   Voice Notes are captured reliably via the internal Python array, ensuring no audio drivers crash during a lesson.

***

**Next Steps (Progress 23):**
The final phase of the wearable is **Wireless Haptics**. We will transmit the 3-Zone Safety warnings (Left, Center, Right) as BLE (Bluetooth Low Energy) strings to an ESP32 microcontroller, translating the `fill_ratio` and `obj_z` proximity data into dynamic PWM vibration intensity.
