#  Blind Navigation System (10th Progress: The Routing Engine)

**Focus:** Turn-by-Turn Math, Dynamic State Management, Audio Progress Reporting, and Two-Step Conversational UI.

In this 10th phase, the SENSEY system becomes a fully functional **Turn-by-Turn Navigator**. We have built a custom mathematics engine that compares the user's real-time VIO (Visual-Inertial Odometry) position against a saved 3D path, providing continuous, context-aware audio instructions without freezing the computer vision processes.

---

##  Key Features Added

### 1. The Navigation Manager (Routing Math)
We built a dedicated class (`NavigationManager`) to handle the complex trigonometry required for turn-by-turn routing.
*   **Distance Calculation:** Uses the Pythagorean theorem to calculate the exact distance (in meters) between the user's current $(X, Z)$ coordinate and the target waypoint.
*   **Heading Correction (Yaw):** Uses `math.atan2` to calculate the absolute angle to the target, then subtracts the user's current IMU Heading to generate a **Relative Turn Angle** (e.g., "Turn Right 45 Degrees").
*   **Threshold Trigger:** Automatically advances to the next waypoint and triggers an audio instruction when the user comes within 0.5 meters of their target.

### 2. "Conversational" Two-Step Voice UI
To prevent dangerous accidental triggers (e.g., the system mistakenly starting a recording when the user is trying to navigate), we implemented a strict **Confirmation State Machine**.
*   **The Flow:**
    1.  User: *"Navigate Door to Desk."*
    2.  System: *"You said navigate Door to Desk. Is this correct?"* (Locks state to `CONFIRM_START`).
    3.  User: *"Yes."*
    4.  System: *"Navigating. Go straight 2 meters."*
*   **Fail-Safe:** If the user says "No," the system cancels the pending action and safely returns to `IDLE`.

### 3. Dynamic "Resume" & "Update" Logic
The system is now fully aware of pauses or interruptions in the user's journey.
*   **Update Command:** If a user forgets their instruction or gets disoriented, they can tap the button and say *"Update."* The system calculates the math from their *current, updated position* and provides a fresh instruction.
*   **Resume Logic:** If the user attempts to stop navigation but says "No" to the confirmation prompt, the system says *"Resuming Navigation"* and immediately provides a fresh mathematical update to get them back on track.

### 4. Background Audio Processing (`threading.Thread`)
All audio instructions—from distance updates to confirmation prompts—are executed in a daemon thread.
*   **Why this matters:** The Hailo-8 NPU and OAK-D VPU generate frames at 30 FPS. If the main Python loop paused for 2 seconds to play an audio file, the VIO pedometer would miss footsteps, and the pathing math would break. By threading the audio, the "eyes" and the "math" never stop working while the "mouth" is talking.

---

##  System Architecture & State Machine

The master script (`oakd_blind_runner.py`) now operates within a strict State Machine to manage the flow of data:

| State | Hardware Activity | Audio Interaction |
| :--- | :--- | :--- |
| **`IDLE`** | YOLOv8 + OAK-D (Monitoring only) | Listens for "Record" or "Navigate". |
| **`RECORDING`** | Drops AR dots every 0.5m; listens for landmark clicks. | *"Point X Saved."* |
| **`NAVIGATING`** | Compares current XYZ to JSON path; draws green AR line. | *"Turn left 15 degrees and walk 2.1m."* |
| **`CONFIRMING`** | Halts mode switches; listens exclusively for "Yes/No". | *"Is this correct?"* |

---

##  File Roles & Integration

| File | Location | Modification |
| :--- | :--- | :--- |
| **`oakd_blind_runner.py`** | `~/Downloads/` | **The Brain.** Now contains the `NavigationManager` class, the `execute_action()` logic block, and the real-time XYZ updating loop. |
| **`[Route_Name].json`** | `~/Documents/` | **The Maps.** Contains the stacked arrays of $[X, Z, \text{Label}]$ generated during the `RECORDING` state. |

---

## 💻 Operational Workflow: How to Navigate

1.  **Start:** Run the system. Tap the GPIO button and say *"Record desk to window."*
2.  **Map:** Walk the path. The system records your footsteps. Say *"Finish"* when done.
3.  **Return:** Turn around. Tap the button and say *"Navigate desk to window."*
4.  **Confirm:** The system asks if this is correct. Say *"Yes."*
5.  **Reverse:** Because you are starting from the end of the file name, the system automatically runs a `.reverse()` on the JSON array and says *"Reversing Route."*
6.  **Walk:** Follow the audio instructions (e.g., "Walk 3 meters") until you hear *"Arrived at destination."*

---

### Voice Command Summary

You trigger the system by pressing the physical button (GPIO 26) and waiting for the "Listening" prompt.

#### 1. Core Actions (From IDLE State)
*   **"Record `[Route Name]`"** (e.g., *"Record front door to desk"*)
    *   **Response:** *"You said record front door to desk. Is this correct?"*
    *   **Action:** Enters confirmation mode. If you answer "Yes," it starts dropping AR waypoints.
*   **"Go to `[Route Name]`"** or **"Navigate `[Route Name]`"** (e.g., *"Navigate front door to desk"*)
    *   **Response:** *"You said navigate front door to desk. Is this correct?"*
    *   **Action:** Enters confirmation mode. If you answer "Yes," it loads the JSON file and projects the green guiding line.

#### 2. Actions During Recording (While in RECORDING State)
*   **"Point saved"**
    *   **Response:** *"Point `[X]` saved."*
    *   **Action:** Immediately tags your current physical (X, Z) coordinate as a landmark in the route. *No confirmation required.*
*   **"Stop"** or **"Finish"**
    *   **Response:** *"You said finish. Is this correct?"*
    *   **Action:** Enters confirmation mode. If you answer "Yes," it saves the JSON file and returns to IDLE.

#### 3. Actions During Navigation (While in NAVIGATING State)
*   **"Update"**
    *   **Response:** *"Turn [left/right] X degrees and walk Y meters."*
    *   **Action:** Instantly recalculates the distance and angle to the next waypoint from your current position.
*   **"Stop"** or **"Finish"**
    *   **Response:** *"You said stop. Is this correct?"*
    *   **Action:** Enters confirmation mode. If you answer "Yes," navigation cancels and returns to IDLE.

#### 4. Universal Confirmation Responses (When asked "Is this correct?")
*   **"Yes"** or **"Correct"**
    *   **Action:** Executes the pending command (starts recording, saves file, starts navigating).
*   **"No"** or **"Wrong"**
    *   **Action:** Cancels the pending command. If you were recording, it resumes recording. If you were idle, it stays idle.

