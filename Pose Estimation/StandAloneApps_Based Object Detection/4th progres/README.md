# Visual-Inertial Odometry (VIO) Foundation

## 📌 Overview
In the **4th Progress**, the SENSEY system transitions from high-level visual recognition to **Inertial Awareness**. For a blind teacher to navigate a classroom without ArUco tags or GPS, the device must track its own orientation and movement in 3D space. 

This progress milestone documents the successful implementation of a **Visual-Inertial Hardware Bridge** using the **DepthAI v3.x (SDK)** architecture. 

## 🚀 Key Improvements & API Changes (v2.x vs v3.x)
Because this project utilizes the modern **DepthAI v3.3.0**, several fundamental code structures were refactored from the "Gen2" standard to ensure stability on the Raspberry Pi 5.

### 1. Implicit Context Management
*   **Change:** Shifted from standard object declaration to the **Context Manager** (`with dai.Pipeline()`) approach.
*   **Impact:** This ensures a clean "handshake" between the RPi 5 and the OAK-D Lite. It handles the "Implicit Device" creation, automatically managing the connection and preventing "Stream already open" errors during crashes.

### 2. High-Level Output Queueing (Removal of XLinkOut)
*   **Change:** Removed manual `dai.node.XLinkOut` creation and explicit `node.link()` commands.
*   **Impact:** In v3, the system uses the high-level **`.out.createOutputQueue()`** function directly on the sensor node. This abstracts the complexity of XLink communication, reducing code overhead and improving data throughput for high-frequency (400Hz) IMU packets.

### 3. Automated Reconnection Logic
*   **Change:** Implemented v3’s improved internal recovery loop.
*   **Impact:** The Raspberry Pi 5 USB 3.0 controller often experiences synchronization drops. The v3 implementation handles the *"Attempting to reconnect"* warnings natively, allowing the IMU data stream to recover without restarting the entire script.

## 🛠 Sensor Integration: BMI270 (6-Axis)
The script in this progress verifies the raw data from the **BMI270 IMU** located inside the OAK-D Lite.

*   **Accelerometer (Z-Axis Calibration):** Used to detect the "Gravity Vector." This allows the system to know if the wearable is tilted, ensuring the **GTA Red Circle Waypoint** stays perfectly flat on the classroom floor.
*   **Gyroscope (Yaw Integration):** Used to track body rotation. This data is the "Inner Ear" of the system, providing the **Relative Compass** that triggers the **Navigation Ticking** when the teacher is facing the correct direction.
*   **Frequency Optimization:** The sensors are tuned to **400Hz**, providing the high-fidelity data needed for the custom **VIO (Visual Inertial Odometry)** math that replaces SpectacularAI.

## 🧠 Navigation Concept: The "Somatic Pedometer"
The 4th progress applies the IMU data to the **Step-Conversion Formula**:
1.  **Detection:** The Accelerometer detects the "thump" of a footstep.
2.  **Validation:** The system cross-references visual movement from the **Feature Tracker**.
3.  **Output:** Converts OAK-D distance into "Steps" ($Distance / 0.6m$) for the voice guidance system.

## 📈 Status Report
| Metric | Status |
| :--- | :--- |
| **API Architecture** | DepthAI v3.3.0 |
| **IMU Sampling Rate** | 400Hz |
| **RPi 5 CPU Load** | < 12% |
| **USB Communication** | USB 3.0 (SuperSpeed) |

## ⏩ Next Milestone
The **5th Progress** will focus on the **"Master Fusion"**: Injecting OAK-D frames into the **Hailo-8 Standalone API** to match individual **Instance Segmentation Masks** with their physical **IMU-tracked coordinates**.

---
*Developed as part of the SENSEY Accessibility Project.*

This is an essential addition. A professional README should always include a **"Getting Started"** section so that other researchers can replicate your work. 

Since you are running **Debian Trixie** on a **Raspberry Pi 5**, the installation process requires specific steps to ensure the USB drivers and the modern **DepthAI 3.0** libraries are correctly configured.

---

## 🛠 Installation & Setup Process
To replicate the IMU data stream on a Raspberry Pi 5 running Debian Trixie, follow these steps:

### 1. System Dependencies
The OAK-D Lite requires low-level USB communication libraries to transmit high-frequency IMU data (400Hz).
```bash
sudo apt update
sudo apt install -y libusb-1.0-0-dev
```

### 2. Hardware Permissions (Udev Rules)
By default, Linux restricts USB access for security. You must grant the Raspberry Pi permission to talk to the Movidius MyriadX chip inside the OAK-D Lite.
```bash
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="03e7", MODE="0666"' | sudo tee /etc/udev/rules.d/80-movidius.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```
*Note: Unplug and replug the OAK-D Lite after applying these rules.*

### 3. Python Environment & Library Installation
Because Debian Trixie uses Python 3.13, it is mandatory to use a Virtual Environment to prevent system conflicts.
```bash
# Enter your project directory
cd ~/hailo-apps

# Activate your existing Hailo environment
source venv_hailo_apps/bin/activate

# Install/Upgrade DepthAI to the modern v3.x branch
pip install depthai==3.3.0
```
---


