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
This error (**Error 6 / HAILO_DRIVER_OPERATION_FAILED**) is different from the previous "Busy" error (Error 74). 

**Error 6** (ENXIO) means: *"I see the file `/dev/hailo0`, but when I try to talk to the hardware, no one answers."* This usually points to a **Hardware/PCIe Link failure** or a **Permission issue**.

Follow these steps to diagnose and fix it:

### 1. Check Permissions (The Quickest Fix)
Sometimes the device file exists but your current user doesn't have permission to open it.
Run this command:
```bash
sudo chmod 666 /dev/hailo0
```
Then try to run your script again. If it works, you just need to add your user to the hailo group permanently (usually handled by `hailo-all` but sometimes skipped).

### 2. Check the PCIe Link (Is the Hat still there?)
Run this to see if the Raspberry Pi's internal bus can still see the Hailo chip:
```bash
lspci | grep -i hailo
```
*   **If it returns nothing:** The PCIe link has dropped. This is almost always a **loose ribbon cable**.
*   **If it returns a line (e.g., `0001:01:00.0 Co-processor: ...`):** The hardware is connected, but the driver is crashed.

### 3. Check the System Logs (The "Pro" Diagnostic)
This will tell you exactly why the driver failed. Run:
```bash
dmesg | grep -i hailo
```
**Look for these specific errors in the output:**
*   `hailo: probe of 0001:01:00.0 failed with error -5`: Hardware not responding.
*   `hailo: device is in D3 state`: Power management error.
*   `hailo: Failed to find pci bar`: Ribbon cable/Connection issue.

### 4. The Ribbon Cable (The Most Common Culprit)
The Raspberry Pi 5 PCIe connector is very sensitive. If you moved the Pi or bumped it, the cable might have shifted by a fraction of a millimeter.
1.  **Shut down and unplug power.**
2.  Open the little black/white tabs on the Pi 5 and the AI Hat.
3.  Pull the ribbon cable out and **re-insert it perfectly straight**.
4.  Make sure the cable is pushed in until the "ears" on the side of the cable touch the connector.
5.  Lock the tabs firmly.

### 5. Verify `config.txt`
Make sure your PCIe Gen settings haven't been lost. Open the config:
```bash
sudo nano /boot/firmware/config.txt
```
Ensure these lines are at the bottom:
```text
dtparam=pciex1
dtparam=pciex1_gen=3
```
*Note: If you have Gen 3 and it's unstable, try changing `gen=3` to `gen=2` to see if the error goes away. Gen 2 is slightly slower but much more stable if the cable is not perfect.*

### 6. Reset the Driver
If `lspci` sees the device but the script fails, try reloading the driver one more time:
```bash
sudo modprobe -r hailo_pci
sudo modprobe hailo_pci
```

**Summary of what to do right now:**
1. Run `lspci | grep -i hailo`.
2. If it shows nothing, **unplug power and re-seat the ribbon cable**.
3. If it shows the device, run `sudo chmod 666 /dev/hailo0` and try again..

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
