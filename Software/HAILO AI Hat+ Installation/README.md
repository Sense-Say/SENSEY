#  Hailo-8 AI HAT+ Installation Guide (26 TOPS)

**Target OS:** Raspberry Pi OS "Trixie" (Debian 13) 
**Hardware:** Raspberry Pi 5 + Hailo-8 AI HAT+ (M.2 Key M)  
**Repo:** `hailo-apps` (New Standard)

---

## 📦 Part 1: Install Libraries & Drivers
**Do this first.** This sets up the system-level drivers and firmware.

### 1. Update System & Install DKMS
Trixie uses DKMS for kernel driver management.
```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install dkms -y
```

### 2. Install Hailo-All Package
This installs Firmware, HailoRT, Tappas Core, and PCIe drivers.
```bash
sudo apt install hailo-all -y
sudo reboot
```

### 3. Enable PCIe Gen 3.0 (Required for 26 TOPS)
RPi5 defaults to Gen 2.0. Force Gen 3.0 for max AI performance.
1.  Run `sudo raspi-config`
2.  Navigate to: **6 Advanced Options** $\rightarrow$ **A8 PCIe Speed**
3.  Select **Yes** (Enable Gen 3)
4.  **Finish** & **Reboot**

---

## 🛠️ Part 2: Install Hailo Apps (Git)

### 1. Clone the Repository
```bash
git clone https://github.com/hailo-ai/hailo-apps.git
cd hailo-apps
```

### 2. Setup Python Environment
Install the required Python dependencies for the apps.
```bash
# Create and activate a virtual environment (Recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Download Resources
Download the required model networks (.hef files) and video resources.
```bash
./download_resources.sh
```

---

## 🏃 Part 3: Running AI Tasks

Ensure your virtual environment is active (`source venv/bin/activate`) and you are in the `hailo-apps` folder.

### Run Object Detection
```bash
python runtime/python/detection/detection.py --input resources/detection0.mp4
```

### Run Pose Estimation
```bash
python runtime/python/pose_estimation/pose_estimation.py --input resources/detection0.mp4
```

### Run on Live Camera (USB/RPi Cam)
```bash
python runtime/python/detection/detection.py --input /dev/video0
```

---

## ℹ️ Part 4: Info & Troubleshooting

### Verify Device
Check if the Hailo-8 (26 TOPS) is recognized.
```bash
hailortcli fw-control identify
```
*Expected:* `Board Name: Hailo-8`, `Device Architecture: HAILO8`.

### Monitor Temperature & Power
Check chip status during inference.
```bash
hailortcli measure-power
```

### Trixie vs Bookworm Note
*   **Trixie (Debian 13):** Uses `dkms` to manage the Hailo driver independent of the kernel. This prevents driver breakages during `apt upgrade`.
*   **"System Unstable":** If the Pi crashes under load, ensure you are using the **Official 27W Power Supply**. PCIe Gen 3 consumes significant power.

### Native Camera (No Python)
You can run inference directly on the RPi camera stack:
```bash
rpicam-hello -t 0 --post-process-file /usr/share/rpi-camera-assets/hailo_yolov8_inference.json --loopy
```
