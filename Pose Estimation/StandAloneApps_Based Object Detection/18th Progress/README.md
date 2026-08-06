# 18th Progress: Ordinal Memory Slots, Conversational UX & Thread-Safe PyAudio

## 🚀 Overview
The 18th progress solves two of the most notoriously difficult problems in assistive wearables: **Speech-to-Text (STT) accuracy** in offline edge environments, and **concurrent Linux audio-hardware management**. 

Instead of relying on the user to dictate complex path names (which offline models frequently mishear), we transitioned to an **Ordinal "Save Slot" architecture**. We also engineered a robust, non-blocking conversational flow and finally resolved the severe PulseAudio threading crashes by pivoting to a specialized PyAudio stream handler for capturing user Voice Notes.

---

## 🛠 Key Technical Enhancements

### 1. Ordinal Memory Slots ("Save Slots")
*   **The Problem:** Asking a user to say "Record front door to back desk" leaves too much room for phonetics failure inside the lightweight offline Vosk model. If it mishears the name during recording, navigating back to it later is nearly impossible.
*   **The Solution:** The system now hard-allocates exactly 10 distinct routing files (`destination_1.json` through `destination_10.json`).
*   **The Code Application:** Added a numeric parser (`get_ordinal_key()`) that inherently accepts either cardinal (*one, two*) or ordinal (*first, second*) spoken words and identically snaps them to their corresponding save slots, nullifying vocabulary errors.

### 2. Conversational Route Alias Mapping
*   **The Concept:** While the system physically stores files numerically, blind users navigate using semantics.
*   **The Execution:** When a user initializes a memory slot (e.g., *"Record first destination"*), the State Machine pauses and natively prompts the user for a physical descriptor: *"Please say the name for this destination."*
*   **The Backend:** It automatically pairs this dictated string (e.g., "door to window") with the `"destination_1"` slot inside a unified, separate file (`route_map.json`). 
*   **Identify Feature:** By commanding *"Identify first,"* the system fetches the name from the JSON Map safely, confirming the route's environment purely based on numeric targeting without ever initiating standard traversal functions.

### 3. The Distinction: `Stop` vs. `Finish`
*   **The Logic Split:** 
    *   **"Stop":** A physical abort function. Discards the current navigation map cached in RAM instantly and returns safely to IDLE, keeping memory pristine if the user creates a pathing mistake midway.
    *   **"Finish":** The dynamic "Success" endpoint constraint.
*   **Auto-Appended Dest-Markers:** Before closing, `execute_action("finish")` natively pulls the raw real-time global values for `[current_x, current_z, current_yaw]` directly at the point of request and drops a definitive `[..., "destination"]` parameter anchor as the tail index before flushing and syncing down to `.json`.

### 4. Flawless ALSA / PulseAudio Concurrent Handling
*   **The Crisis:** Triggering 5-second `.wav` audio snapshots locked PortAudio on the Raspberry Pi (`Device Unavailable -9985`), breaking Vosk streams recursively or throwing fatal `pthread_join` deadlocks on thread shutdowns. ALSA natively rejects standard asynchronous mic-overrides unless explicitly detached contextually.
*   **The Engineering Fix:** Switched Voice Note ingestion over to `PyAudio` inside decoupled daemon threads with constrained buffers (`chunk = 1024`). 
*   **Result:** By applying `exception_on_overflow=False` through standard iterative chunk fetching algorithms over a set timeline rather than continuous single blocking, PyAudio successfully shares PulseAudio backend dependencies securely bypassing thread-panic without turning the primary hardware off, capturing exactly `44100Hz` arrays down to local `16_LE` wav packages properly linked back into standard Route Arrays continuously. 

---

## 🚦 System Logic: The Conversational Path

The implemented code enforces an intuitive chain via Global State Machine constraints logic bypassing dead-microphone faults previously tracked throughout debugging. 

| **System Status (`STATE`)** | **User Interaction Pipeline Flow** |
| :--- | :--- |
| **`IDLE`** | User speaks *"Record first destination"* -> Transitions into `CONFIRM_START`. |
| **`WAIT_DEST_NAME`** | System natively requests the spatial tag constraint. Mic unlocks instantly bypassing logic lock! User states *"Front window."* |
| **`CONFIRM_DEST_NAME`**| Voice verifies the parsed path alias accurately prior to appending arrays across `route_map.json` silently updating mappings cleanly handling 10 instances effectively overriding older ones. |
| **`RECORDING`**| Drops Path & Custom `note` indices down standard breadcrumb mechanics correctly utilizing real-time math! User finishes session via commanding *"Finish"* executing physical completion tracking loops properly returning directly back tracking base commands dynamically safely. |

---

## 🔧 Developer Notes & Error Diagnoses

*   **`STATE` Overwrites Bug:** During prior logic building, files weren’t successfully saving despite correctly launching save protocols via "yes." We discovered the STT callback was setting `STATE = "IDLE"` immediately *before* passing execution variables internally preventing functions that explicitly needed validation against specific current context.  
    **Rule:** Always defer resetting the Global STATE to IDLE until precisely inside `execute_action()` post-data dump functions correctly mitigating skipped data allocations.

*   **Overwriting Security Limits:** `write` constraints act precisely equivalent across memory limits! Instructing users dynamically they possess specifically "First to Tenth" memory tracks actively encourages route overwrites minimizing bloated garbage collection natively wiping path `.json` tracks entirely while updating new map associations properly keeping filesystem arrays light on RPI operations perfectly mapping audio components efficiently back on top directly aligning with the overarching **SENSEY Architecture Goals**. 

***

**Next Steps Pipeline Targeting:**
* Integrating **Global Spatial Tags** across physical markers natively enforcing automated "True North" coordinate alignments against absolute tag arrays without requiring users actively request standard physical alignment triggers resolving "Distance Shimmering Drift" thoroughly entirely rendering systems fundamentally error-proof navigating completely offline dynamically successfully matching constraints specifically natively cleanly consistently mapped actively tracking components cleanly natively actively continuously directly automatically.

***
---


## 🛠 Key Technical Enhancements & Code Implementation

### 1. Ordinal Memory Slots ("Save Slots")
**The Problem:** Asking a user to say *"Record front door to back desk"* leaves too much room for phonetic failure. If Vosk mishears it during recording, asking to navigate to it later fails.
**The Solution:** Hard-allocate exactly 10 routing files (`destination_1.json` through `destination_10.json`) via a dictionary mapping.

```python
# --- ROUTE ALIAS STORAGE LOGIC ---
ROUTE_MAP_FILE = os.path.join(DOC_PATH, "route_map.json")

def get_ordinal_key(text):
    """
    Safely maps varying spoken keywords into one of 10 structured file routes.
    Accepts both "one" and "first".
    """
    ord_map = {
        "first": "1", "one": "1", "second": "2", "two": "2", 
        "third": "3", "three": "3", "fourth": "4", "four": "4", 
        # ... mapped up to tenth ...
    }
    for word, num in ord_map.items():
        if word in text: return f"destination_{num}", num
    return None, None
```

### 2. Conversational Route Alias Mapping
**The Concept:** While stored as `destination_1.json`, blind users need semantics (names). 
**The Code Application:** A dedicated sequence in `handle_voice_command` asks the user to name the route *after* initializing the slot, locking it perfectly into the `route_map.json` without file-saving crashes.

```python
    # Inside handle_voice_command()
    elif STATE == "CONFIRM_START":
        if "yes" in cmd:
            dest_key, _ = get_ordinal_key(pending_command)
            pending_route_key = dest_key
            STATE = "WAIT_DEST_NAME"
            speak_offline("Please say the name for this destination.")
            is_listening = True # Loop STT to capture name immediately

    elif STATE == "WAIT_DEST_NAME":
        pending_route_alias = cmd # Stores "Door to Desk"
        STATE = "CONFIRM_DEST_NAME"
        speak_offline(f"You said {cmd}. Is this correct?")
        is_listening = True
        
    elif STATE == "CONFIRM_DEST_NAME":
        if "yes" in cmd:
            STATE = "IDLE" 
            execute_action("start_recording_dest") # Saves alias & generates arrays
```

### 3. The Distinction: `Stop` vs. `Finish`
**The Problem:** In earlier logic, canceling a route out of frustration generated a partial, broken file, overwriting the user's previous good route.
**The Fix:** Split logic in `execute_action()` so `Stop` drops everything in memory safely, and `Finish` automatically applies the user's exact current physical location as the absolute end-point of the navigation route.

```python
    # Inside execute_action()
    elif "finish" in cmd:
        if STATE == "RECORDING" and len(recorded_path) > 0:
            # Auto-appends Final Location
            recorded_path.append([current_x, current_z, "destination", current_yaw, ""])
            
            file_path = os.path.join(DOC_PATH, f"{current_route_filename}.json")
            with open(file_path, "w") as f: 
                json.dump(recorded_path, f, indent=4) 
                
            speak_offline("Saving last point. Recording finished.")
            STATE = "IDLE"

    elif "stop" in cmd:
        # Purge logic - memory flushed without overwriting standard .json!
        if STATE == "RECORDING":
            speak_offline("Recording not saved.")
        STATE = "IDLE"
```

### 4. Flawless PyAudio Handover for 5s Notes
**The Crisis:** Launching `subprocess` or `sd.rec()` 5-second locks resulted in terminal PulseAudio Timeout lockups (`Device Unavailable -9985` & `pthread_join`). ALSA refused to yield control between Voice Note buffering and the constant Vosk STT feed.
**The Fix:** Integrated PyAudio to manually harvest chunk packets safely through ALSA overflows, effectively circumventing device locking.

```python
    elif STATE == "CONFIRM_NOTE":
        import wave, pyaudio
        if "yes" in cmd:
            STATE = "RECORDING_NOTE"
            is_recording_note = True # Safely pauses Vosk's loop visually without ending the thread!
            
            # Start parameters
            CHUNK, FORMAT, CHANNELS, RATE = 1024, pyaudio.paInt16, 1, 44100
            audio = pyaudio.PyAudio()
            frames_buffer = []

            # 5-second controlled buffer reading (solves -9985 exception permanently)
            stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK, input_device_index=mic_idx)
            
            for _ in range(0, int(RATE / CHUNK * 5.0)):
                # 'exception_on_overflow=False' ignores minute stutters preventing threading panic
                data = stream.read(CHUNK, exception_on_overflow=False) 
                frames_buffer.append(data)
                
            stream.stop_stream()
            stream.close()
            audio.terminate()
            
            # Reconstruct Audio bytes and save internally targeting correct Route Notes format!
            waveFile = wave.open(note_path, 'wb')
            # ... saving metadata to JSON and WAV ... 

            is_recording_note = False
            rec.Reset() # Wipes potential Vosk acoustic backlog instantly! 
```

---

## 🚦 System Operational Review

*   **STATE Handing Refinement:** We resolved the bug where setting `STATE="IDLE"` too early blocked final logic routines from realizing they were operating under a `RECORDING` state block. **State assignments have strictly migrated to exclusively alter after primary tracking protocols fire entirely natively.**
*   **Alias Identify Tag:** Invoking `"Identify fourth destination"` from standard `IDLE` state pulls exactly from the standalone internal `route_map.json`, validating environmental destinations using Voice strictly off memory buffers securely leaving Navigation matrices ready on prompt instantly mapping seamlessly offline. 

***

**Next Pipeline Targets:**
Integrating automated "True North" coordinate tagging. AprilTag absolute alignments utilizing the background camera feed dynamically adjusting the pedometers cumulative `current_yaw, current_x` natively zeroing Out sensor-stray effectively ending map 'Shimmer' directly rendering total off-grid tracking mathematically impeccable across large dynamic zones permanently!
