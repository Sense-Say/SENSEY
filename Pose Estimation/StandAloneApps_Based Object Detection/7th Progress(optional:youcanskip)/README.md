# 🧭 Blind Navigation System (7th Progress: AR Pathfinding & Voice UI)

**Focus:** Augmented Reality Projection, Manual Path Recording, Path Reversing Logic, and Voice-Driven Command Interface.

In this 7th phase, the SENSEY system has been transformed into a functional **3D Wayfinder**. We have successfully integrated the "Navigation Brain" (VIO) with a visual AR overlay, allowing the system to not only detect obstacles but also remember and "redraw" paths in the physical world.

---

## 🚀 Key Features Added

### 1. Augmented Reality (AR) Projection Engine
We implemented a mathematical projection layer that "pins" digital waypoints to the physical floor.
*   **The Math:** Using the **Pinhole Camera Model**, the system projects 3D coordinates $(X, Z)$ back into 2D screen coordinates $(u, v)$. 
*   **Perspective Scaling:** Waypoints (red circles) dynamically resize based on distance—getting smaller as they recede into the background.
*   **Breadcrumb Logic:** In **Recording Mode**, the system automatically drops a breadcrumb every 0.5 meters, creating a visual trail of the user's journey.

### 2. "Click-and-Talk" Voice Command System
To simplify the user interface for a blind teacher, we integrated a voice-driven command system triggered by a single physical button (**GPIO 26**).
*   **Trigger:** Tap the button $\rightarrow$ Hear "Listening" cue $\rightarrow$ Speak command.
*   **Commands Supported:**
    *   *"Record Front Door to Desk"* $\rightarrow$ Initializes a new JSON path file.
    *   *"Point 1 Saved"* $\rightarrow$ Tags a specific 3D coordinate as a landmark (e.g., a chair or table).
    *   *"Finish Recording"* $\rightarrow$ Closes and saves the path data to the disk.
    *   *"Go to Desk to Front Door"* $\rightarrow$ Loads an existing path and starts navigation.

### 3. Automatic Path Reversing
The system is now capable of a "Return Journey" logic. 
*   **Mechanism:** If the user requests a path in reverse (e.g., they recorded "Door to Desk" but say "Go to Desk to Door"), the system detects the keyword swap, loads the JSON file, and runs a `.reverse()` on the coordinate list.
*   **Result:** The user is guided back to their starting point using the exact same path they took originally.

### 4. System Stability & Thread Management
Processing high-speed NPU data while listening for voice commands can cause memory crashes (`malloc` errors).
*   **Thread Locking:** We implemented an `is_busy` lock. The system ignores button presses if a voice command is already being processed, preventing thread-stacking.
*   **Audio Stability:** We migrated from `playsound` to **`mpg123`** (system-level) for audio playback to prevent the Python interpreter from crashing during speech events.

---

## 📂 System Architecture Update

The 7th Progress relies on a **State Machine** with three distinct modes:

| Mode | Status | Activity |
| :--- | :--- | :--- |
| **IDLE** | White Dashboard | Standard Object Detection & VIO only. |
| **RECORDING** | **Red Path** | Drops dots every 0.5m; saves X/Z coordinates to a new JSON file. |
| **NAVIGATING** | **Green Path** | Projects saved JSON coordinates onto the floor; guides user to landmarks. |

---

## 🔧 File Roles & Integration

| File | Location | Modification |
| :--- | :--- | :--- |
| **`oakd_blind_runner.py`** | `~/Downloads/` | **Master Controller.** Manages the State Machine, GPIO 26 interrupts, and Speech-to-Text (STT) processing. |
| **`object_detection_post_process.py`** | `hailo_apps/...` | **AR Renderer.** Contains the `draw_ar_elements` function which performs the 3D-to-2D projection math. |

---

## 💻 Operational Workflow for the User

1.  **Start System:** Launch the runner. Dashboard shows `MODE: IDLE`.
2.  **Start Mapping:** Tap the button. Say *"Record Door to Window."* Walk the path.
3.  **Mark Landmarks:** Tap the button at a specific spot. Say *"Point 1 saved."*
4.  **Save:** Tap the button at the destination. Say *"Finish Recording."* A file `door_to_window.json` is generated.
5.  **Return:** Turn around. Tap the button. Say *"Go to Window to Door."* Follow the **Green Path** lines appearing on the floor.

---

## 🛠️ Required Libraries (New)

To support the voice and AR features, the following must be installed in the virtual environment:

```bash
# System level
sudo apt install flac mpg123
# Python level
pip install SpeechRecognition gTTS gpiozero
```

## 🔭 Future Progress: Phase 8
The next phase will focus on moving the Voice Recognition from the Cloud (Google) to the local Hailo NPU using the **Whisper** model for 100% offline, high-speed interaction.
