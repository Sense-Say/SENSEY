# 🎛️ Master Controller Integration 

**Focus:** Hardware Switching, Process Management, and Audio Feedback.

In this phase, we moved from running individual scripts manually to a fully integrated **Hardware-Controlled System**. Using a physical **ON-OFF-ON Rocker Switch**, the user can instantly toggle between "Blind Navigation Mode," "Student Monitoring Mode," or "Standby," with the system handling the complex task of killing and launching AI processes automatically.

##  Key Features

### 1. Hardware-Driven Mode Switching
Instead of using a keyboard or SSH terminal, the device is now controlled by a physical switch connected to the Raspberry Pi 5 GPIO pins.
*   **Switch UP:** Activates **Blind Navigation** (Object Detection + Spatial Logic).
*   **Switch DOWN:** Activates **Student Monitoring** (Pose Estimation + Face Recognition).
*   **Switch CENTER:** Activates **Standby Mode** (Kills all AI/Camera processes to save power).

### 2. Raspberry Pi 5 GPIO Compatibility
We migrated from the older `RPi.GPIO` library to **`gpiozero`**.
*   **Reason:** The Raspberry Pi 5 uses a new RP1 I/O chip that is incompatible with legacy GPIO libraries. `gpiozero` provides a stable interface for the new hardware.

### 3. Voice Feedback System
The system now speaks its status changes using **Text-to-Speech (TTS)**.
*   *Event:* User flips switch.
*   *Audio:* "Blind Navigation Mode Activated."
*   *Event:* User sets switch to center.
*   *Audio:* "System is now in Standby."

### 4. Automated Process Management
The Master Controller acts as a supervisor. Before starting a new mode, it performs a **Hard Cleanup**:
*   It sends `SIGTERM` to running scripts.
*   It runs `pkill` on Python processes to ensure the **Hailo-8 NPU** and **USB Camera** are fully released before the next model tries to load. This prevents **Error 74 (Resource Busy)**.

---

##  Hardware Setup

**Component:** SPDT (Single Pole Double Throw) Center-OFF Rocker Switch.

| Switch Pin | Raspberry Pi Pin | Function |
| :--- | :--- | :--- |
| **Middle (Common)** | **GND** (Physical Pin 30 or 34) | Ground reference. |
| **Side A** | **GPIO 5** (Physical Pin 29) | Triggers Blind Navigation. |
| **Side B** | **GPIO 6** (Physical Pin 31) | Triggers Student Monitoring. |

*Note: The code enables internal Pull-Up resistors, so no external resistors are required.*

---

##  File Architecture

The `master_controller.py` sits at the top level and manages the wrapper scripts created in previous progress steps.

| File | Location | Role |
| :--- | :--- | :--- |
| **`master_controller.py`** | `~/Downloads/` | **The Brain.** Monitors GPIO 5 & 6, manages processes, and generates audio feedback. |
| **`run_object_detection.py`** | `~/Downloads/` | **Mode A.** Wrapper for the Spatial Object Detection system. |
| **`standalone_poseversion2.py`** | `~/Documents/` | **Mode B.** Wrapper for the Pose + Face Monitoring system. |

---

## 🛠️ Software Requirements

To run the Master Controller on Raspberry Pi 5, install these specific libraries in your virtual environment:

```bash
source /home/raspberrypi/hailo-apps/venv_hailo_apps/bin/activate

# gpiozero: Required for RPi 5 GPIO control
# gTTS/playsound: Required for voice feedback
pip install gpiozero gTTS playsound==1.2.2
```

---

## 💻 Code Logic (How it works)

The script uses a **State Machine** loop:

1.  **State Check:** Every 0.5 seconds, it checks the state of **GPIO 5** and **GPIO 6**.
2.  **Change Detection:**
    *   If **GPIO 5 is Low** (Active) AND current mode is not BLIND $\rightarrow$ Kill current process $\rightarrow$ Launch Object Detection.
    *   If **GPIO 6 is Low** (Active) AND current mode is not STUDENT $\rightarrow$ Kill current process $\rightarrow$ Launch Pose Monitor.
    *   If **BOTH are High** (Inactive) AND current mode is not STANDBY $\rightarrow$ Kill everything $\rightarrow$ Sleep.
3.  **Resource Safety:** It passes `env["HAILO_SCHEDULER"] = "1"` to all child processes to ensure the NPU initializes correctly every time.

---

##  Operational Test

1.  **Boot** the Raspberry Pi.
2.  Run `python3 master_controller.py`.
3.  **Flip Switch UP:**
    *   *Audio:* "Blind Navigation Mode Activated."
    *   *Screen:* Object detection window opens with Left/Center/Right partitions.
4.  **Flip Switch CENTER:**
    *   *Audio:* "System is now in Standby."
    *   *Screen:* Window closes immediately.
5.  **Flip Switch DOWN:**
    *   *Audio:* "Student Monitoring Mode Activated."
    *   *Screen:* Pose Estimation window opens with "Student X" labels.
