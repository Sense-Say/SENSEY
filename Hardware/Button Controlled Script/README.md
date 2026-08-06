# Hailo RPi5 Mode-Switching Mechanism

This project implements a robust hardware-controlled switching mechanism for the **Raspberry Pi 5 with Hailo-8 AI Hat**. It allows a user (specifically designed for accessibility) to interchange between **Blind Navigation Mode** and **Student Monitoring Mode** using a physical 3-position toggle or rotary switch.

## 🚀 Features
- **Hardware-Enforced Standby:** Uses a 3-position switch (Center-OFF) to ensure a clean hardware break between mode changes.
- **PCIe Resource Management:** Prevents `HAILO_OUT_OF_PHYSICAL_DEVICES (Status 74)` by enforcing a 5-second cooldown and process-group termination.
- **Software Debouncing:** Ignores electrical noise and accidental "flicks" via a 1.0s stability check.
- **Audio Feedback:** Integrated `mpg123` support for voice/audio status updates (Startup, Mode Active, Standby, Shutdown).
- **Process Isolation:** Each AI module runs in its own Process Group (`os.setsid`) to ensure background GStreamer threads are fully terminated on exit.

---

## 🛠 Hardware Setup

### Components
1. **Raspberry Pi 5** + **Raspberry Pi AI Kit (Hailo-8L)**.
2. **3-Position Switch** (MTS-103 Toggle ON-OFF-ON or 3-Position Industrial Rotary Switch).
3. **Audio Output** (Speaker or Headphones via USB/3.5mm).

### Wiring Diagram (6-Pin DPDT or 3-Pin SPDT)
We use a **Pull-Up** configuration. When the switch is moved, it connects the GPIO to Ground (**GND**).

| Switch Pin | Connection | Function |
| :--- | :--- | :--- |
| **Middle Pin** | Raspberry Pi **GND** (Pin 9) | Common Ground |
| **Top Pin** | **GPIO 17** (Pin 11) | Student Behavior Mode |
| **Bottom Pin** | **GPIO 27** (Pin 13) | Blind Navigation Mode |

*Note: For 6-pin switches, simply use one vertical row of 3 pins and ignore the other row.*

---

## 📂 Project Structure
```text
/home/raspberrypi/SENSEY/
└── Text to Speech Folder/
    └── Dorongon/
        └── 1st progres/
            ├── buttonscontroller.py  # The "Master Controller"
            ├── detection.py          # Blind Navigation Logic
            └── pose_estimation.py    # Student Monitoring Logic
```

---

## ⚙️ Software Configuration

### 1. Requirements
- **OS:** Raspberry Pi OS 64-bit (Bookworm).
- **Hailo Suite:** `hailo-all` and `hailo-rpi5-examples` repository installed.
- **Audio:** `mpg123` installed (`sudo apt install mpg123`).

### 2. The Controller Logic
The `buttonscontroller.py` acts as a state machine. It prevents the Hailo chip from "locking up" by enforcing a sequence:
1. **Detect Change:** Monitor GPIO 17 and 27.
2. **Stabilize:** Wait 1s to confirm the user's intent.
3. **Kill & Clear:** Terminate existing AI scripts and force a `pkill` on all GStreamer/Hailo threads.
4. **Cooldown:** Wait 5s for the PCIe bus to release the Hailo-8 hardware handle.
5. **Initialize:** Launch the new `.hef` model using `subprocess.Popen`.

---

## 🏃 How to Run

1. **Activate the Environment:**
   ```bash
   cd /home/raspberrypi/hailo-rpi5-examples
   source setup_env.sh
   ```

2. **Launch the Master Controller:**
   ```bash
   python3 "/home/raspberrypi/SENSEY/Text to Speech Folder/Dorongon/1st progres/buttonscontroller.py"
   ```

3. **Switch Usage:**
   - **Switch UP:** Starts Student Behavior Mode.
   - **Switch CENTER:** Enters Standby (Hardware Released).
   - **Switch DOWN:** Starts Blind Navigation Mode.

---

## ⚠️ Troubleshooting

### `Status 74: HAILO_OUT_OF_PHYSICAL_DEVICES`
This occurs if a new script starts before the old one has finished cleaning up its memory.
- **Fix:** Ensure the `RESET_TIME` in `buttonscontroller.py` is set to at least `5.0`.
- **Fix:** Check that `os.killpg` is being used to kill the entire process group, not just the parent PID.

### Audio is too quiet
The controller uses `mpg123`. Adjust system volume:
```bash
amixer set Master 100%
```

### Switch feels unresponsive
The `DEBOUNCE_TIME` is set to `1.0s` to prevent accidental triggers for blind users. If you want faster switching, reduce this to `0.5s` in the script.

---

## 📜 License
This project is intended for research and accessibility development. Use in accordance with Hailo Technologies Ltd. software licensing.
