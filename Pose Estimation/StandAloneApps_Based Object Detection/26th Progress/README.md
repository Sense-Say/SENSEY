# 26th Progress: Odometer-Based Precision & Sequential Audio UX

## 🚀 Overview
The 26th progress cycle finalized the "Human-Machine Interface" (HMI) of the SENSEY system. We solved the critical "Hypotenuse Error" in navigation math by decoupling **Map Orientation (X/Z)** from **Walking Distance (Odometer)**. Additionally, we implemented a robust **Sequential Audio Pipeline** that allows the teacher to hear beeps, voice notes, and instructions in a perfectly timed sequence without system crashes.

---

## 🧠 Core Technical Pillars

### 1. The Odometer Math (1D vs 2D Distance)
*   **The Problem:** Calculating distance using the Pythagorean theorem between `[X, Z]` coordinates resulted in "shortcuts." If a user walked a curved path, the straight-line math would report a shorter distance than the physical walk (e.g., reporting 0.39m for a 1.17m walk).
*   **The Solution:** We introduced a **6th element in the JSON**: `total_dist`. 
*   **Logic:** 
    *   **X and Z** are used exclusively to determine **Turn Angles** (Where to look).
    *   **total_dist** (Odometer) is used exclusively to determine **Walking Distance** (How far to go).
*   **Implementation:** The distance to the next point is now calculated as `target_total_dist - current_total_dist`, ensuring 100% accuracy regardless of path curvature.

### 2. Sequential Audio Queue (The `audio_worker`)
*   **Concept:** Raspberry Pi audio drivers (ALSA) fail when multiple processes try to speak simultaneously.
*   **Implementation:** We created a single-threaded **FIFO (First-In, First-Out) Queue**.
*   **The Workflow:** When a teacher reaches a landmark, the system pushes three distinct tasks to the queue:
    1.  `{"type": "beep"}` -> Plays the custom `recording_notes.wav`.
    2.  `{"type": "text", "msg": "Reached Point 1"}` -> Generates Piper TTS.
    3.  `{"type": "wav", "path": "user_note.wav"}` -> Plays the user's raw voice recording.
*   **Result:** The system never "talks over" itself. Each sound waits for the previous one to finish, creating a professional, intelligible experience.

### 3. Human-Centric Turn Logic (Strict 4-Rule Phrasing)
*   **Concept:** Converting abstract degrees into intuitive physical commands.
*   **The Gatekeeper:**
    1.  **±5°:** "Walk straight for X meters." (Prevents jittery instructions).
    2.  **-6° to -174°:** "Turn [X] degrees to the left side..."
    3.  **+6° to +174°:** "Turn [X] degrees to the right side..."
    4.  **±175°+:** "Turn behind you..."
*   **Natural Language:** We use `abs(degrees)` to ensure the AI never says "negative 90 degrees," which is confusing for a user.

### 4. Headless Mode Stability (Wayland/X11 Fix)
*   **The Problem:** Unplugging the HDMI monitor on a Pi 5 caused the OpenCV `imshow` loop to hang or freeze the pedometer math.
*   **The Fix:** Implemented a **Headless Fallback**.
```python
try:
    cv2.imshow("SENSEY", processed)
except:
    time.sleep(0.001) # Simulate the waitKey(1) delay to keep math timing stable
```

---

## 🛠 Bug Resolution Log

| Feature / Issue | Symptom | Resolution Strategy |
| :--- | :--- | :--- |
| **"Reached path" Spam** | AI spoke every breadcrumb. | Added `if node_type == "ANCHOR"` gate to arrival logic. |
| **Jumping HUD Arrow** | Arrow flipped when standing on a point. | Implemented a 0.1m "Yaw Lock" to freeze the arrow upon arrival. |
| **Broken Voice Notes** | AI read filename instead of playing audio. | Decoupled `note` field into a `{"type": "wav"}` queue task. |
| **Precision Error** | Meters were rounded to 1 decimal. | Standardized all distance strings to `:.2f` for 1cm resolution. |

---

## 📂 System Architecture Reference

### Navigation Manager (`NavigationManager`)
The logic engine that transforms JSON path data into a real-time guidance stream. It now supports the `apply_anchor_snap` transformation matrix for AprilTag integration.

### Audio Worker (`audio_worker`)
The dedicated thread that manages all hardware output. It supports:
*   **Text:** Real-time Piper synthesis.
*   **Wav:** Playback of user-recorded notes via `pygame.mixer.Sound`.
*   **Beep:** Instant feedback upon landmark arrival.
*   **Arrival:** The 3-second final success chime.

---

## 🎯 Operational Best Practices
1.  **Recording:** Walk at a steady pace. The system automatically drops breadcrumbs every 0.6m. 
2.  **Voice Notes:** Wait for the "Start" prompt. Speak clearly for the full 5 seconds.
3.  **Navigation:** Follow the **Audio Ticks**. If the ticks stop, use the **Update** command to hear the 8-zone direction and distance.
4.  **Arrival:** The system will automatically go **IDLE** once the final destination chime finishes playing. No manual "Stop" is required.

***
---

# 🛠 Technical Implementation: Code Breakdown

## 1. Odometer-Based Path Calculation (1D Vector Integration)
To solve the "shortcut math" error, we transitioned from 2D coordinate subtraction to **Odometer Delta Calculation**. The JSON now stores the `total_dist` (pedometer reading) at the moment of recording.

**The Implementation (`NavigationManager.py`):**
```python
# 1. Store the odometer reading during recording
recorded_path.append([current_x, current_z, label, current_yaw, note, total_dist])

# 2. Calculate distance during navigation using the 6th element (index 5)
current_node_dist = target["total_dist"] 
for i in range(self.current_wp_index, len(self.path)):
    p = self.path[i]
    if p["type"] == "ANCHOR":
        # 🚀 THE FIX: Subtract the odometer readings to get true walking distance
        next_dist = p["total_dist"] - current_node_dist 
        break
```
**Purpose:** This ensures that if a user walks a 5-meter curve, the system says "Walk 5 meters," whereas the old coordinate-based math would have said "Walk 3.5 meters" (the straight line across the curve).

## 2. The Sequential Audio Pipeline (Thread Isolation)
To prevent the Raspberry Pi's audio hardware from locking up, we isolated all sound output into a dedicated worker thread using a **Thread-Safe Queue**.

**The Implementation (`audio_worker`):**
```python
def audio_worker():
    while True:
        cmd = audio_queue.get()
        if cmd['type'] == 'text':
            # Piper TTS synthesis via paplay (Mixer compatible)
            subprocess.run(f'echo "{cmd["msg"]}" | {PIPER_EXE} ... | paplay ...')
        elif cmd['type'] == 'wav':
            # Immediate low-latency playback for voice notes
            sound = pygame.mixer.Sound(cmd['path'])
            sound.play()
            time.sleep(sound.get_length()) # Ensure completion before next task
        audio_queue.task_done()
```
**Purpose:** By using `audio_queue.put()`, we can "stack" sounds (Beep → Arrival Msg → Voice Note). The worker thread ensures they play in a perfect row, never overlapping or crashing the ALSA driver.

## 3. Strict 4-Rule Guidance Logic
This logic converts raw floating-point degrees into four specific human-friendly commands. We use the **Angular Wrap-Around** formula to ensure turns are always calculated via the shortest path.

**The Implementation:**
```python
turn_err = (target_yaw - current_yaw + 180) % 360 - 180
dist_str = f"{distance:.2f}"

if abs(turn_err) <= 5:
    msg = f"Walk straight for {dist_str} meters."
elif turn_err < -5 and turn_err >= -174:
    msg = f"Turn {int(abs(turn_err))} degrees to the left side and walk {dist_str} meters."
elif turn_err > 5 and turn_err <= 174:
    msg = f"Turn {int(turn_err)} degrees to the right side and walk {dist_str} meters."
else:
    msg = f"Turn behind you and walk {dist_str} meters."
```
**Purpose:** 
*   **The ±5° Buffer:** Prevents the AI from telling the user to "Turn 1 degree left" constantly due to natural body sway.
*   **Absolute Values:** Uses `abs(turn_err)` so the AI speaks natural numbers (e.g., "90 degrees") rather than mathematical signs ("negative 90").

## 4. Headless-Safe UI Synchronization
Raspberry Pi 5 uses the Wayland compositor, which handles windowing differently than X11. Running without a monitor (Headless) typically breaks the `cv2.imshow` timing, which in turn ruins the IMU integration.

**The Implementation:**
```python
try:
    cv2.imshow("SENSEY HUD", processed)
    if cv2.waitKey(1) == ord('q'): break
except Exception:
    # 🚀 THE FIX: If no monitor is detected, manually simulate the 1ms waitKey delay
    # This keeps the loop timing consistent so the IMU 'dt' remains accurate.
    time.sleep(0.001) 
```
**Purpose:** This allows the wearable to operate as a standalone device with no screen attached, while maintaining the same mathematical accuracy as when it is plugged into a monitor in the lab.

## 5. Anchor-Gated Arrival Sequence
To eliminate the "Reached path" spam, we implemented a type-check during the arrival calculation.

**The Implementation:**
```python
if self.distance_to_wp < 0.45:
    # Only speak if the node was manually saved or is a major destination
    if node_type == "ANCHOR" or note:
        audio_queue.put({"type": "beep"}) # Custom audio feedback
        audio_queue.put({"type": "text", "msg": f"Reached {node_label}."})
```
**Purpose:** This keeps the "Invisible Tunnel" silent. The user only hears the rhythmic "Ticks" while on the path, and only receives voice instructions when a meaningful landmark or turn is reached.

---

### Summary of System Robustness
These code portions work together to create a **Fault-Tolerant System**:
1.  **Math:** Odometer tracking eliminates coordinate drift.
2.  **Audio:** The Queue eliminates hardware deadlocks.
3.  **Visuals:** The Headless Fallback eliminates timing jitters.
4.  **UX:** The 8-Zone Phrasing eliminates user confusion.
