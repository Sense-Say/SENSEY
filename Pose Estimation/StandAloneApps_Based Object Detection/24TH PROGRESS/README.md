# 24th Progress: Master Orchestration & Hands-Free Auto-Boot Deployment

## 🚀 Overview
The 24th progress represents the final "packaging" of the SENSEY system. We have moved beyond running individual scripts in Thonny to a fully automated **Master Controller** architecture. The system now features a physical mode-switch handler, high-speed SSD data management, and a "Zero-Interaction" boot sequence that allows a blind teacher to initialize the entire AI stack simply by powering on the device.

---

## 🧠 Core Technical Pillars

### 1. The Master Orchestrator (`sensey_mode_controller.py`)
*   **Concept:** A background "Watchdog" script that monitors physical GPIO toggle switches to swap between different AI modes (Blind Navigation vs. Student Monitoring).
*   **The "No Mercy" Kill Logic:** To prevent hardware lockouts on the OAK-D Lite and Hailo-8, the controller uses an aggressive cleanup routine. When a mode is switched, it issues an OS-level `SIGKILL (-9)` to all child processes, ensuring the PCIe bus and USB stack are instantly freed for the next mode.
*   **Threaded Speech:** The controller uses a dedicated background thread for Piper TTS, allowing it to announce "Standby Mode" while simultaneously killing heavy AI processes in the background.

### 2. SSD Migration & Path Optimization
*   **The Problem:** SD cards are too slow for loading large Vosk models and Hailo HEF files, often causing system-wide freezes during initialization.
*   **The Solution:** Migrated the entire OS and SENSEY stack to a high-speed SSD. 
*   **Technical Fix:** We resolved the `Device Unavailable [-9985]` and `Model file doesn't exist` errors by standardizing absolute paths and ensuring the `hailort_service` was disabled to prevent hardware resource contention between the OS and our Python scripts.

### 3. Hands-Free Auto-Boot (The "Launcher")
*   **Concept:** A blind user cannot use a mouse, keyboard, or Thonny to start the system.
*   **Implementation:** Created a Linux `.desktop` autostart entry that triggers a specialized Bash launcher (`start_sensey.sh`).
*   **The Developer Dashboard:** The launcher opens a visible `lxterminal` window on boot. This provides a "Live Dashboard" where all `print()` statements from the AI engines are streamed in real-time using the `PYTHONUNBUFFERED=1` environment variable.

---

## 🛠 Technical Implementation: The Auto-Start Chain

### Step 1: The Bash Launcher (`start_sensey.sh`)
Located in `/home/raspberrypi/MASTER CONTROL/`, this script prepares the environment:
```bash
#!/bin/bash
# 1. Force kill any zombie processes from previous sessions
pkill -9 -f sensey_mode_controller.py
pkill -9 -f oakd_blind_runner.py

# 2. Set environment for OpenCV GUI
export QT_QPA_PLATFORM=xcb
export DISPLAY=:0

# 3. Launch the Master Controller
/home/raspberrypi/hailo-apps/venv_hailo_apps/bin/python3 "/home/raspberrypi/MASTER CONTROL/sensey_mode_controller.py"
exec bash
```

### Step 2: The Autostart Entry (`sensey.desktop`)
Located in `~/.config/autostart/`, this tells the Pi to open the terminal on login:
```ini
[Desktop Entry]
Type=Application
Name=SENSEY Master
Exec=lxterminal -e "/home/raspberrypi/MASTER CONTROL/start_sensey.sh"
Terminal=false
```

---

## 🚦 Operational Workflow (Production Mode)

1.  **Power On:** The teacher connects the battery to the Raspberry Pi 5.
2.  **Auto-Init:** The Pi boots, loads the SSD, and automatically opens a terminal window.
3.  **Voice Confirmation:** After 10 seconds, the system announces: **"System Ready."**
4.  **Mode Selection:** The teacher flips the physical toggle switch:
    *   **Switch UP:** "Blind Navigation Mode Activated." (Launches `oakd_blind_runner.py`).
    *   **Switch DOWN:** "Student Monitoring Mode Activated." (Launches `standalone_poseversion2.py`).
    *   **Switch CENTER:** "Standby Mode." (Kills all AI processes to save battery).
5.  **Shutdown:** To stop the system, the user can simply close the terminal window or power down.

---

## 🔧 Developer Notes: Troubleshooting the SSD Stack

*   **Zombie Processes:** If the camera is "Busy," it is because a previous session wasn't killed. The new `pkill -9` logic in the launcher solves this.
*   **Terminal Visibility:** By using `lxterminal -e`, we ensure that developers can still see the debug logs (AprilTag snaps, Pedometer steps, etc.) without needing to open Thonny.
*   **Pathing with Spaces:** We successfully implemented quoted path handling (`"/home/raspberrypi/MASTER CONTROL/"`) to ensure Linux handles folder names with spaces correctly.

***
# 24th Progress: Installation & Deployment Guide

## 🛠 System Installation (Terminal Commands)

To set up the SENSEY Master Controller on a new SSD, follow these commands in order.

### 1. Update System & Install Core Dependencies
First, ensure the Raspberry Pi OS is up to date and install the necessary audio and windowing utilities.
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y pulseaudio pulseaudio-utils alsa-utils x11-xserver-utils lxterminal
```

### 2. Configure Audio Permissions
Grant the user permission to access the audio hardware and PulseAudio streams to prevent "Device Busy" errors.
```bash
sudo usermod -a -G audio $USER
sudo usermod -a -G pulse-access $USER
```

### 3. Disable Hailo Background Service
The default `hailort` service can lock the NPU. We disable it so our Python scripts have exclusive access to the 26 TOPS.
```bash
sudo systemctl stop hailort
sudo systemctl disable hailort
```

### 4. Set Up Directory Structure
Create the folders exactly as defined in the Master Controller paths.
```bash
mkdir -p "/home/raspberrypi/MASTER CONTROL"
mkdir -p "/home/raspberrypi/BlindNavigation"
mkdir -p "/home/raspberrypi/TTS-STT-AUDIO"
```

### 5. Configure Executable Permissions
Ensure the Piper TTS engine and your custom launcher have permission to run.
```bash
chmod +x "/home/raspberrypi/TTS-STT-AUDIO/piper/piper"
chmod +x "/home/raspberrypi/MASTER CONTROL/start_sensey.sh"
```

---

## 🚀 Deployment: Setting Up Auto-Boot

Follow these steps to enable the "Zero-Interaction" startup.

### Step 1: Create the Launcher Script
```bash
nano "/home/raspberrypi/MASTER CONTROL/start_sensey.sh"
```
**Paste the following:**
```bash
#!/bin/bash
# Force kill any zombie processes
pkill -9 -f sensey_mode_controller.py
pkill -9 -f oakd_blind_runner.py
pkill -9 -f arecord

sleep 10
export QT_QPA_PLATFORM=xcb
export DISPLAY=:0

/home/raspberrypi/hailo-apps/venv_hailo_apps/bin/python3 "/home/raspberrypi/MASTER CONTROL/sensey_mode_controller.py"
exec bash
```

### Step 2: Create the Autostart Entry
```bash
mkdir -p /home/raspberrypi/.config/autostart
nano /home/raspberrypi/.config/autostart/sensey.desktop
```
**Paste the following:**
```ini
[Desktop Entry]
Type=Application
Name=SENSEY Master
Comment=Auto-starts the system and shows the terminal
Exec=lxterminal -e "/home/raspberrypi/MASTER CONTROL/start_sensey.sh"
Terminal=false
StartupNotify=true
```

---

## 🔧 Developer "Maintenance" Commands

If you need to stop the auto-boot to perform coding in Thonny, use these "Toggle" commands:

**To Disable Auto-Boot:**
```bash
mv /home/raspberrypi/.config/autostart/sensey.desktop /home/raspberrypi/.config/autostart/sensey.desktop.bak
```

**To Enable Auto-Boot:**
```bash
mv /home/raspberrypi/.config/autostart/sensey.desktop.bak /home/raspberrypi/.config/autostart/sensey.desktop
```

**To Manually Kill All SENSEY Processes:**
```bash
sudo pkill -9 -f python
```

---

## 📊 Final Hardware Mapping Reference

| Component | GPIO Pin | Logic |
| :--- | :--- | :--- |
| **Blind Navigation Switch** | GPIO 5 | Pull-Up (Active Low) |
| **Student Monitor Switch** | GPIO 6 | Pull-Up (Active Low) |
| **Voice Trigger Button** | GPIO 26 | Pull-Up (Active Low) |

***

**Conclusion of 24th Progress:**
The system is now a **hardened appliance**. By moving the logic into a Master Controller and automating the boot sequence via `lxterminal`, we have created a reliable, self-healing environment that provides the teacher with a consistent, hands-free experience every time the device is powered on.
