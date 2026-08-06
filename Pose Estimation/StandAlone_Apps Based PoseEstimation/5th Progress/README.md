# Physical Integration & Intelligent Feedback

**Focus:** Hardware Triggering, Spatial Linking, and Human-Like Reporting.

This update transitions the system from a development prototype to a usable classroom device by adding physical controls (GPIO Button) and refining how the system communicates results to the teacher (Smart TTS Grouping).

## 🚀 Key Features Added

### 1. Physical Trigger (GPIO 26)
We moved away from keyboard-only interaction. The system now supports a momentary push button connected to the Raspberry Pi GPIO pins.
*   **Hardware:** Push Button connected between **GPIO 26** and **GND**.
*   **Logic:** The `pose_estimation_utils.py` uses `gpiozero` to detect the press. This triggers the exact same snapshot workflow as the 'S' key, allowing for a wearable or desk-mounted "Scan Button."

### 2. Spatial Box Matching (Solving the "Identity Swap")
We solved the critical issue where student names would swap if their position in the array changed (e.g., if "Student 1" left the frame, "Student 2" became "Student 1").
*   **The Fix:** Instead of linking names to the array index, we now link names to the **Physical Location** of the person.
*   **Mechanism:**
    1.  Pose AI saves the bounding box of every person to `temp_boxes.json`.
    2.  Face AI finds a face and calculates its center point.
    3.  The logic checks: *"Is this face center inside Pose Box A or Pose Box B?"*
    4.  This creates an unbreakable link between the Name and the specific Body Box.

### 3. Intelligent Grouped Reporting
The terminal and audio output were refactored to sound natural. Instead of listing every student individually, the system now aggregates data.
*   **Old:** *"Student 1 is Attentive. Student 2 is Attentive. Edward is Attentive."*
*   **New:** *"Edward and 2 Students are Attentive."*
*   **Logic:** The script separates known names from generic "Student X" labels, counts the generics, and constructs a grammatically correct sentence using `is` or `are`.

### 4. Audio Feedback Integration
The system now speaks the generated Smart Report using Google Text-to-Speech (`gTTS`).
*   **Non-Blocking:** The audio generation and playback run in a background thread, so the video feed **never freezes** while the device is speaking.

---

## 📂 Updated File Roles

| File | Location | Role Update |
| :--- | :--- | :--- |
| **`pose_estimation_utils.py`** | `hailo-apps/...` | **Now supports GPIO 26.** Handles the Smart Reporting logic and Spatial Data export. |
| **`cpu_process_screenshot.py`** | `~/Documents/` | **Now performs Spatial Matching.** Reads `temp_boxes.json` to link faces to bodies accurately. |
| **`standalone_poseversion2.py`** | `~/Documents/` | **Unchanged.** Still acts as the stable wrapper/manager loop. |
| **`action_logic.py`** | `~/Documents/` | **Unchanged.** Provides the 5 behavior rules. |

---

## 🔧 Hardware Wiring Guide (GPIO Button)

To use the physical button feature:

1.  **Pin Selection:** We use **GPIO 26** (Physical Pin 37).
2.  **Connection:**
    *   Connect one leg of the button to **GPIO 26**.
    *   Connect the other leg to a **Ground (GND)** pin (Physical Pin 39 is adjacent).
3.  **No Resistor Needed:** The code enables the internal `pull_up` resistor on the Pi.

---

## 📊 Sample Reporting Output

**Scenario:** Edward (Known) and two unknown students are sitting. Michael (Known) is raising his hand.

**Terminal Output:**
```text
📊 CLASSROOM STATUS REPORT:
   👉 Edward and 2 Students are Attentive.
   👉 Michael is Raising Hand.
------------------------------------------------
🔊 Speaking Report...
```

**Audio Output:** *"Edward and 2 Students are Attentive. Michael is Raising Hand."*

---

## 🛠️ Installation of New Libraries

To support the GPIO and Audio features, ensure these libraries are installed in your virtual environment:

```bash
source /home/raspberrypi/hailo-apps/venv_hailo_apps/bin/activate
pip install gpiozero rpi.gpio gTTS playsound==1.2.2
```
