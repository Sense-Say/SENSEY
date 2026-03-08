# 17th Progress: The "Sponge" Audio Architecture & Thread Optimization

## 🚀 Overview
The 17th progress resolves the most complex hardware challenge in the SENSEY project: **Simultaneous Audio Operations on a Single USB Microphone**. Previous attempts to record user voice notes using `subprocess(arecord)` or parallel `sounddevice.rec()` calls resulted in catastrophic PulseAudio timeouts (e.g., `PaErrorCode -9985`) because Linux aggressively locks audio interfaces. 

We engineered a completely new, conflict-free audio architecture—the **"Sponge Method"**—which allows the AI to listen, speak, and record high-quality `.wav` files without ever closing the hardware stream.

---

## 🧠 Core Concept: The "Sponge" Method

### The Problem with Standard Recording
Standard Python logic dictates that to record a file, you must open an audio stream, capture the data, and close the stream. However, the Vosk Speech-to-Text engine requires a continuous, never-closing stream to detect wake words. Attempting to open a *second* stream on the Raspberry Pi caused ALSA (Advanced Linux Sound Architecture) to panic and lock the device permanently until a hard reboot.

### The "Sponge" Solution
Instead of opening a new stream, we utilize the **already running** Vosk callback stream. 
1. The microphone continuously feeds raw data chunks to the `audio_callback` 30 times a second.
2. Normally, this data is fed into the Vosk neural network.
3. When the user says "Yes" to record a note, a global flag (`is_recording_note = True`) acts as a "railway switch."
4. The callback stops feeding Vosk (effectively muting the AI) and instead **appends the raw audio arrays into a Python list** (the "Sponge").
5. After exactly 5.0 seconds, the switch flips back. The list of arrays is concatenated and squeezed into a `.wav` file on the hard drive using `scipy.io.wavfile`.

---

## 🛠 Technical Implementation & Code Highlights

### 1. The CallBack Switch
This logic lives inside the continuous `sd.InputStream` thread. It guarantees zero hardware conflicts because it never touches the device drivers.

```python
def audio_callback(indata, frames, time_info, status):
    global is_recording_note, voice_note_buffer, note_recording_start_time
    
    # 🚀 THE SPONGE: Divert audio from AI to Memory
    if is_recording_note:
        # Convert float32 to int16 for standard .wav format
        audio_int16 = (indata.copy() * 32767).astype(np.int16)
        voice_note_buffer.append(audio_int16)
        
        # Auto-stop safely inside the thread
        if time.time() - note_recording_start_time >= 5.0:
            is_recording_note = False 
        return # Block Vosk from hearing the note
```

### 2. The Main Thread Handler
The state machine now triggers the recording without ever calling a `subprocess` or `sd.rec()`, preventing UI freezing and thread deadlocks.

```python
elif STATE == "CONFIRM_NOTE":
    if "yes" in cmd:
        STATE = "RECORDING_NOTE"
        
        # 1. Provide auditory cues (Prompt + Beep)
        subprocess.run(...) # "Start"
        audio_queue.put({"type": "beep"})
        
        # 2. Activate the Sponge
        voice_note_buffer = [] 
        note_recording_start_time = time.time()
        is_recording_note = True 
        
        # 3. Wait for the background thread to fill the sponge
        while is_recording_note:
            time.sleep(0.1) 
            
        # 4. Squeeze to file
        audio_data = np.concatenate(voice_note_buffer, axis=0)
        wav.write(note_path, native_rate, audio_data)
```

---

## ✅ Pros and ❌ Cons of this Architecture

### Pros
*   **Zero Hardware Lockouts:** By never closing the stream, we bypass all ALSA/PulseAudio bugs specific to the Raspberry Pi environment.
*   **Instant Recovery:** Vosk resumes listening the *exact millisecond* the 5-second timer expires. There is no "boot-up" delay.
*   **High Performance:** Saving the arrays in memory (RAM) and writing to the disk once at the end uses significantly less CPU than writing a live audio file.

### Cons
*   **Memory Usage:** Storing 5 seconds of raw audio in RAM requires a small, temporary memory spike (negligible on Pi 5, but notable for microcontroller dev).
*   **Format Strictness:** Because we are hijacking a float32 stream meant for Vosk, we must manually scale and cast the arrays to `np.int16` so standard audio players can read the `.wav` file without static.

---

## 🚦 Verification Logs
The implementation successfully generates standard audio interactions:
```text
✅ Voice Input: saved point (State: RECORDING)
🔊 Speaking: Point 1 saved. Do you want to add a voice note?
✅ Voice Input: yes (State: CONFIRM_NOTE)
🔊 Prompting: Start
🎙️ Sponge active for 5s: path_1772935358_note_1.wav
✅ Saved 53 chunks to /home/raspberrypi/Documents/path_1772935358_note_1.wav
✅ Recording finished.
```

***

*(... continued from the 17th Progress README.md)*

## 🚦 The "Single-Lane" Audio Thread (Format Agnostic Queuing)

### The Problem with Mixed Audio
A modern navigation assistant uses three entirely different types of audio:
1.  **AI TTS (Piper):** Generates `22050Hz`, 16-bit Mono.
2.  **User Voice Notes:** Recorded dynamically at `44100Hz`, 16-bit Mono.
3.  **Downloaded Sound Effects:** Chimes or Beeps (e.g., `arrived.wav`) downloaded from the internet, which are typically `48000Hz`, 32-bit Stereo.

If you attempt to play a `48000Hz` Stereo file using a low-level hardware tool like `aplay` (which expects raw 16-bit PCM), the result is **severe radio static** or high-pitched screeching. Furthermore, if the system tries to play the "Arrival Chime" and the AI voice "Arrived at destination" simultaneously, the audio overlaps or crashes the ALSA driver.

### The Solution: The `audio_worker` Queue
To achieve a "Clew-level" professional audio experience, we implemented a dedicated **Single-Threaded Audio Queue**. This thread acts as a traffic cop, ensuring that no two sounds ever play at the same time, and routes each sound to the correct playback engine based on its format.

#### Implementation
We initialize a global `queue.Queue()` and run a background daemon thread that constantly waits for instructions:

```python
import queue
audio_queue = queue.Queue()

def audio_worker():
    """🚀 THE SINGLE-THREADED AUDIO MANAGER: Plays one thing at a time."""
    while True:
        cmd = audio_queue.get()
        
        # 1. AI Voice (Raw PCM piped directly to aplay)
        if cmd['type'] == 'text':
            subprocess.run(f'echo "{cmd["msg"]}" | {PIPER_EXE} ... | aplay ...', shell=True)
            
        # 2. User Voice Notes (Standardized 44.1k wav files)
        elif cmd['type'] == 'wav':
            subprocess.run(['aplay', '-q', cmd['path']])
            
        # 3. Custom Downloaded Sounds (Routed through Pygame to fix format mismatch)
        elif cmd['type'] == 'arrival':
            if arrival_sound:
                arrival_sound.play()
                time.sleep(arrival_sound.get_length()) # Block queue until sound finishes
                
        audio_queue.task_done()
```

### Why this Architecture is Bulletproof:

#### 1. Format Agnosticism via `pygame`
By loading downloaded `.wav` files into `pygame.mixer.Sound()`, Pygame automatically transcodes the 48kHz Stereo files into the 44.1kHz Mono output that the Raspberry Pi audio jack expects. This completely eliminates the "Radio Static" bug without requiring the developer to manually convert files in Audacity.

#### 2. The Sequential "Arrival Sequence"
When the mathematical pedometer detects that the user is `< 0.45m` from the final coordinate, it triggers the arrival logic. Because we use a Queue, we can "stack" the experience perfectly:
```python
# 1. Force the visual/haptic UI to stop instantly
STATE = "IDLE" 

# 2. Stack the audio experience
audio_queue.put({"type": "arrival"}) # Plays the 3-second chime
audio_queue.put({"type": "text", "msg": "Arrived at destination."}) # Speaks only after chime ends
```
**The Result:** The UI Green Arrow disappears instantly, the background ticking stops instantly, the 3-second victory chime plays, and *then* the AI voice announces arrival. This creates a highly polished, reassuring UX for the blind user.

#### 3. Zero UI Latency
Because `audio_queue.put()` executes in less than 1 millisecond, the main `run()` loop (which handles the OpenCV video feed and the Hailo-8 AI inference) never stutters. The heavy lifting of converting TTS text to audio and waiting for files to play happens entirely in the background thread.

***

**Next Steps:**
*   Implementing **AprilTags** for absolute global relocalization (Zero-Drift) to replace the relative VIO pedometer over long distances.
*   Translating the "Turn Left / Turn Right" audio instructions into tactile feedback via **Haptic Vibration Motors**.
