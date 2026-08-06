
***

# 🧠 Hailo-8 RPi5 AI Kit: Setup & Deployment Guide

This guide outlines the complete setup to get a custom Hailo-8 detection script running on a **Raspberry Pi 5** using the `hailo-rpi5-examples` framework.

## 1. Prerequisites
- **Hardware:** Raspberry Pi 5 + Raspberry Pi AI Kit (Hailo-8L).
- **OS:** Raspberry Pi OS 64-bit (Bookworm).
- **PCIe Configuration:** Ensure the AI Kit is enabled.
  - Run `sudo raspi-config` > **Advanced Options** > **PCIe Speed** > **Gen 3**.
  - Or verify `dtparam=pciex1` is in `/boot/firmware/config.txt`.

---

## 2. Install Hailo Software Suite
Install the core dependencies required to interface with the Hailo-8L hardware:

```bash
sudo apt update
sudo apt install hailo-all
sudo reboot
```

---

## 3. Setup the Working Directory
Clone the official examples repository. This repository contains the underlying logic (`hailo_apps`) that your custom script depends on.

```bash
cd /home/raspberrypi
git clone https://github.com/hailo-ai/hailo-rpi5-examples.git
cd hailo-rpi5-examples
```

---

## 4. Install Dependencies & Virtual Environment
The RPi5 examples require a specific Python environment to handle the GStreamer pipelines.

```bash
# Run the installation script provided by Hailo
./install.sh

# Download the pre-compiled models (HEF files)
./download_resources.sh
```

---

## 5. Create Your Custom Script
Create the directory for your specific project and initialize your detection script:

```bash
mkdir -p "/home/raspberrypi/SENSEY/Text to Speech Folder/Dorongon/1st progres/"
nano "/home/raspberrypi/SENSEY/Text to Speech Folder/Dorongon/1st progres/detection.py"
```
*Paste your working code into the editor, save (**Ctrl+O**), and exit (**Ctrl+X**).*

---

## 6. Critical Code Requirements
To ensure the script runs successfully outside the main `hailo-rpi5-examples` folder, verify these three sections are in your `detection.py`:

### A. Path Inclusion
Tells Python where to find the Hailo library modules:
```python
import sys
sys.path.append("/home/raspberrypi/hailo-rpi5-examples")
```

### B. Display Environment
Forces the GStreamer window to open correctly on the RPi Desktop:
```python
import os
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"
```

### C. Frame Handling
Do **not** use `cv2.imshow` inside the loop. GStreamer handles the high-speed display window via the user data object:
```python
user_data.set_frame(frame)
```

---

## 7. How to Run the Script
**Important:** You must source the Hailo environment every time you open a new terminal, or the imports will fail.

```bash
# 1. Navigate to the core examples folder
cd /home/raspberrypi/hailo-rpi5-examples

# 2. Activate the Hailo virtual environment
source setup_env.sh

# 3. Run your custom script from its specific location
python "/home/raspberrypi/SENSEY/Text to Speech Folder/Dorongon/1st progres/detection.py"
```

---

## 8. Troubleshooting Guide

| Issue | Solution |
| :--- | :--- |
| **ModuleNotFoundError** | Ensure you ran `source setup_env.sh` and that `sys.path.append` points correctly to the `hailo-rpi5-examples` folder. |
| **HEF file not found** | Ensure you ran `./download_resources.sh`. Check if the path in your code matches the actual `.hef` file location in the resources folder. |
| **Video not playing** | Verify the video path in `hardcoded_args`. If using `.MOV`, try converting to `.mp4` to avoid codec issues. |
| **Could not open display** | Run the script from the Pi Terminal on the desktop, not a basic SSH. If using SSH, use `ssh -X` for X11 forwarding. |
| **Slow Performance** | Ensure you aren't using `cv2.imshow` inside the callback; let the GStreamer pipeline handle the display. |

---

## 9. Summary of Folder Structure
For this setup to work seamlessly, maintain this structure:
- `/home/raspberrypi/hailo-rpi5-examples/` — **The Core Engine**
- `/home/raspberrypi/hailo-rpi5-examples/resources/` — **Pre-trained .hef models**
- `/home/raspberrypi/SENSEY/.../detection.py` — **Your Custom Logic**
