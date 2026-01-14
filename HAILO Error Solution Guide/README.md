# 🛠 Hailo-8 RPi5 Troubleshooting & Hardware Guide

This guide covers the specific hardware and software errors encountered when running Hailo-8 AI accelerators on a Raspberry Pi 5 via the PCIe interface.

---

## 🚨 Section 1: Critical Runtime Errors

### 1. Error 74: `HAILO_OUT_OF_PHYSICAL_DEVICES`
**Symptoms:**  
`[HailoRT] [error] CHECK failed - Failed to create vdevice. there are not enough free devices. requested: 1, found: 0`

**The Cause:**  
The Hailo chip is "locked" by a previous process. This occurs when a script is stopped improperly (e.g., closing the video window with the **'X'** button or using **`Ctrl+Z`**), leaving the GStreamer pipeline hanging in the background.

**The Fix:**  
1. **Kill all ghost processes:**
   ```bash
   sudo pkill -9 -f python
   ```
2. **The "Soft" Driver Reset:**
   ```bash
   sudo modprobe -r hailo_pci && sudo modprobe hailo_pci
   ```
   *Note: If it says `Module hailo_pci is in use`, a process is still active. Run the kill command again.*

3. **The "Hard" Reset (If Driver Reset fails):**
   * Perform a full `sudo shutdown -h now`.
   * **Physically unplug the power cord** for 10 seconds. This is the only way to clear the PCIe bus "D3" power state lock.

---

### 2. Error 6 / 36: `HAILO_DRIVER_OPERATION_FAILED`
**Symptoms:**  
`[HailoRT] [error] CHECK failed - Failed to open device file /dev/hailo0 with error 6`  
`dmesg` output shows: `Device disconnected while opening device`

**The Cause:**  
The PCIe link dropped. This is usually due to signal interference at Gen 3 speeds, a loose ribbon cable, or insufficient power.

**The Fix:**  
1. **Downgrade to PCIe Gen 2:** Gen 2 is significantly more stable than Gen 3 for the RPi5 ribbon cables.
   - Edit config: `sudo nano /boot/firmware/config.txt`
   - Change/Add: `dtparam=pciex1_gen=2`
   - Reboot the Pi.
2. **Re-seat the Ribbon Cable:** Power down and ensure the FPC cable is perfectly straight and firmly locked into both the Pi and the HAT.
3. **Check Power Supply:** Ensure you are using the **Official RPi 27W USB-C supply**. Standard chargers often cause PCIe brownouts during high-load inference (like YOLOv8m).

---

## 📂 Section 2: Environment & Pathing Issues

### 3. `ModuleNotFoundError`
**Symptoms:**  
`No module named 'hailo_apps'` or `hailo_apps_infra`

**The Cause:**  
Running a script from a custom directory (e.g., `/home/raspberrypi/SENSEY/...`) without adding the Hailo examples repository to the Python path.

**The Fix:**  
Include the repository path at the top of your Python script **BEFORE** the other Hailo imports:
```python
import sys
# Manually point Python to the library folder
sys.path.append("/home/raspberrypi/hailo-rpi5-examples")
```
*Always ensure the virtual environment is active:* `source setup_env.sh`

---

## 📊 Section 3: Diagnostic Commands Toolkit

Use these commands to determine if the issue is **Hardware (PCIe)** or **Software (Driver/Process)**.

| Command | Purpose | Expected Result |
| :--- | :--- | :--- |
| `hailortcli scan` | OS Connectivity | `[-] Device: 0001:01:00.0` |
| `hailortcli fw-control identify` | Firmware Health | Shows "Firmware Version: 4.20.0" |
| `lspci \| grep -i hailo` | PCIe Bus Check | Shows "Co-processor: Hailo Technologies" |
| `sudo lsof /dev/hailo0` | Lock Check | Shows the PID of the process using the chip |
| `dmesg \| grep -i hailo` | System Logs | Should NOT show "Device disconnected" |

---

## 🛡 Section 4: Prevention & Best Practices (Developer Survival Rules)

### 1. The "Golden Rule" of Stopping Scripts
**NEVER click the 'X' button on the video window.**
*   **Safe Way:** Click the terminal window and press **`Ctrl + C`**. This triggers the Python `finally` block and tells GStreamer to release the Hailo-8 hardware properly.
*   **The Result of Clicking 'X':** The display closes but the Hailo process remains a "zombie" in the background, leading to Error 74.

### 2. Environment Activation
Never run the script without sourcing the environment first. This links the specific compiled C-libraries needed for post-processing.
```bash
cd /home/raspberrypi/hailo-rpi5-examples
source setup_env.sh
```

### 3. Handling Segmentation Faults
If your script crashes with `Segmentation fault`, it usually means:
1.  The HEF path is wrong.
2.  The Post-Processing `.so` file path is wrong.
3.  The chip was just disconnected due to power loss.
**Action:** Verify all file paths and check `hailortcli scan`.

### 4. Hardware Cooling
The Hailo-8 can get very hot. If performance drops or the Pi freezes after 10-20 minutes of use, ensure your AI Hat has a heatsink and proper airflow. Thermal throttling can cause the PCIe driver to reset.

---
