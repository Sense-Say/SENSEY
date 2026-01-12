---

# Hailo RPi5 Triple-Column Detection

This project implements real-time object detection using the Raspberry Pi 5 AI Kit (Hailo-8L). It divides the camera feed into three equal vertical columns (**Left**, **Center**, **Right**) and identifies the majority position of detected objects.

## Features
- **Majority-Area Logic**: Uses the horizontal midpoint of bounding boxes to assign objects to exactly one column, preventing detection conflicts.
- **Throttled Output**: Terminal results refresh every 0.5s to maintain readability.
- **Visual Overlays**: Draws green grid lines and column labels directly on the video stream.
- **Pose-Estimation Format**: Terminal output follows the format: `FPS:XX | [Label] on [Column] || Status: [ID:Col]`.

## Prerequisites
- Raspberry Pi 5
- Raspberry Pi AI Kit (Hailo-8L)
- Raspberry Pi OS (64-bit Bookworm)

## Installation

1. **Install Hailo Suite**:
   ```bash
   sudo apt update && sudo apt install hailo-all
   sudo reboot
   ```

2. **Clone Official Examples**:
   The script relies on the `hailo-rpi5-examples` infrastructure.
   ```bash
   cd /home/raspberrypi
   git clone https://github.com/hailo-ai/hailo-rpi5-examples.git
   cd hailo-rpi5-examples
   ./install.sh
   ./download_resources.sh
   ```

## Configuration

Ensure your script contains the correct paths to the HEF model and the example repository:
- **Library Path**: `sys.path.append("/home/raspberrypi/hailo-rpi5-examples")`
- **Model Path**: `/home/raspberrypi/hailo-rpi5-examples/resources/yolov8m.hef`

## Execution

You **must** run the script within the Hailo virtual environment.

```bash
# 1. Navigate to the examples folder
cd /home/raspberrypi/hailo-rpi5-examples

# 2. Activate the environment
source setup_env.sh

# 3. Run the script
python "/path/to/your/detection.py"
```

## How it Works

### 1. Column Logic
The screen width (normalized 0.0 to 1.0) is split at **0.33** and **0.66**. 
- **Left**: Midpoint < 0.33
- **Center**: 0.33 ≤ Midpoint < 0.66
- **Right**: Midpoint ≥ 0.66

### 2. Critical Flags
The script uses `sys.argv` to inject two vital flags:
- `--use-frame`: Enables the Python buffer to allow OpenCV drawing (`cv2.line`, `cv2.putText`).
- `--disable-sync`: Prevents lag when processing frames through Python/OpenCV.

### 3. Terminal Output Example
```text
FPS:25 | person on left | laptop on center || Status: ['ID1:L', 'ID2:C']
```



This is your integrated **Master Reference Guide**. It combines the core Hailo-8L setup instructions with the specific Triple-Column logic and terminal formatting we developed.

---

# 📝 Hailo RPi5 Development: Master Reference Guide

### 1. The Development Environment
*   **Location matters:** Your scripts should live near or reference the `hailo-rpi5-examples` folder to access the `hailo_apps` library.
*   **The Virtual Env:** Always activate the environment before running:
    ```bash
    cd /home/raspberrypi/hailo-rpi5-examples
    source setup_env.sh
    ```
*   **External Scripts:** If your script is in a custom folder (like `SENSEY/...`), tell Python where the Hailo libraries are:
    ```python
    import sys
    sys.path.append("/home/raspberrypi/hailo-rpi5-examples")
    ```

### 2. GStreamer App Logic (The Pipeline)
*   **`user_app_callback_class`**: Use this to store persistent variables (e.g., `self.last_print_time`).
*   **`app_callback`**: This function runs for every frame. 
*   **Don't use `cv2.imshow`**: It will crash the GStreamer pipeline threads.
*   **Use `user_data.set_frame(frame)`**: This sends your modified OpenCV frame (with lines/text) back to the GStreamer display sink.
*   **Critical Flags in `sys.argv`**:
    *   `--use-frame`: **Required** to enable Python-side frame processing and drawing.
    *   `--disable-sync`: Prevents video lag when using USB cameras or performing heavy OpenCV drawing.

### 3. Triple Column Detection Logic
To detect objects in Left, Center, or Right columns without "double-counting":
*   **The Midpoint Rule**: Calculate the horizontal center of the bounding box (normalized 0.0 to 1.0):
    ```python
    mid_x = (bbox.xmin() + bbox.xmax()) / 2
    ```
*   **The 33% Threshold**:
    *   `mid_x < 0.33` → **Left**
    *   `mid_x < 0.66` → **Center**
    *   `else` → **Right**
*   **Benefit**: This ensures that even if an object overlaps two columns, it is only assigned to the one where the **majority (50%+)** of its body is located. No conflict possible.

### 4. Output Formatting (Pose-Estimation Style)
To keep the terminal clean and mimic the `pose_estimation.py` style, use a 0.5s timer:
*   **Throttling**: `if (current_time - self.last_print_time) >= 0.5:`
*   **Format**: `FPS:XX | [Label] on [Column] || Status: [ID:Code]`
*   **Status Codes**: Use short identifiers like `ID1:L`, `ID2:C`, `ID3:R` for quick visual scanning.

### 5. Hardware Troubleshooting (Error 74)
The error `HAILO_OUT_OF_PHYSICAL_DEVICES` means the chip is locked or crashed.
*   **The #1 Cause**: Closing the live video window by clicking the **'X'** button. This leaves the driver "in use."
*   **The Safe Way**: Always click the terminal window and press **`Ctrl + C`** to stop the script.
*   **The "Soft" Fix**: Kill ghost processes:
    ```bash
    sudo pkill -9 -f python
    ```
*   **The "Hard" Fix**: If the driver is stuck (`hailo_pci` in use):
    1.  `sudo shutdown -h now`
    2.  Physically unplug power for 10 seconds.
    3.  Plug back in and boot.

### 6. Useful Terminal Commands
| Command | Purpose |
| :--- | :--- |
| `hailortcli scan` | Checks if the Pi sees the AI Hat. |
| `hailortcli fw-control identify` | Checks if the AI Hat firmware is responding. |
| `ls /dev/hailo0` | Verifies the device node exists in Linux. |
| `sudo lsof /dev/hailo0` | Shows exactly which process is currently using the chip. |

### 7. Code Maintenance
*   **HEF Paths**: Ensure paths to the `.hef` model are absolute (starting from `/home/...`).
*   **Input**: Set `VIDEO_PATH = "usb"` for the official camera/webcam, or provide the full path to a file.
*   **Color Space**: Hailo buffers are **RGB**, but OpenCV uses **BGR**. Always convert before drawing and before sending back to the sink:
    ```python
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) # Convert to Draw
    # ... draw lines ...
    user_data.set_frame(frame) # Send back
    ```

---

### Final Script Configuration Template
```python
# Quick snippet for sys.argv setup in main():
sys.argv = [
    sys.argv[0],
    "--input", "usb",
    "--hef-path", "/home/raspberrypi/hailo-rpi5-examples/resources/yolov8m.hef",
    "--use-frame",   # MUST HAVE FOR DRAWING  (REMOVE IF LAG!)
    "--disable-sync" # MUST HAVE FOR SMOOTH USB
]
```
## Troubleshooting
- **No Lines on Screen**: Ensure `--use-frame` is included in `sys.argv`.
- **ModuleNotFoundError**: Ensure you ran `source setup_env.sh` before executing.
- **Laggy Video**: Ensure `--disable-sync` is enabled and that you are not running other heavy background processes.
