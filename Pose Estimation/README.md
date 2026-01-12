---

# Raspberry Pi 5 & Hailo-8: Custom Pose Estimation & Action Logic

This project implements real-time pose estimation and action recognition (Standing, Walking, Raising Hand) on a Raspberry Pi 5 using the Hailo-8 AI HAT.

## 1. System Requirements & OS Setup

### OS Choice: Debian Bookworm (Legacy Full)
*   **Why Bookworm?** As of late 2025, Debian Trixie is still prone to errors. Most importantly, the official [hailo-rpi5-examples](https://github.com/hailo-ai/hailo-rpi5-examples) repository specifically supports **Bookworm**. 
*   **Note:** If you choose to use Trixie, you must use the [hailo-apps-infra](https://github.com/hailo-ai/hailo-apps-infra/tree/main) repository instead, which lacks some specific RPi5 optimizations found in the Bookworm examples.

## 2. Environment Installation

After flashing the OS, follow the official Hailo/Core-Electronics setup. 

### Environment Activation
Every time you open a new terminal, you **must** activate the environment:
```bash
cd hailo-rpi5-examples
source setup_env.sh
```

### Hardware Verification
To confirm the AI HAT is correctly installed and detected, run:
```bash
# Check if the Hailo-8 Firmware is identified
hailortcli fw-control identify

# Verify installed Hailo packages
dpkg -l | grep hailo
```

## 3. Development Setup (Thonny IDE)

To run and debug code within Thonny instead of just the terminal, you must point the IDE to the Hailo Virtual Environment.

1.  Open **Thonny**.
2.  Go to **Run** > **Configure Interpreter**.
3.  Select **Alternative Python 3 interpreter or virtual environment**.
4.  Browse to the following path:
    ` /home/raspberrypi/hailo-rpi5-examples/venv_hailo_rpi_examples/bin/python3 `
5.  Click OK. You can now run scripts directly from Thonny using the Hailo libraries.

## 4. Custom Action Logic

The primary goal of this implementation is to recognize specific actions from pose data:
*   **Standing**
*   **Walking**
*   **Raising Hand**

### Handling Inputs (Camera vs. Video File)
In the source code (specifically within your progress scripts), you can switch inputs by modifying the `sys.argv` extension:

**For USB Webcam:**
```python
# Set input to local USB camera
sys.argv.extend(["--input", "/dev/video0"]) 
# or use
sys.argv.extend(["--input", "usb"])
```

**For Local Video File:**
1.  Locate your video in the File Manager.
2.  Right-click and select **Copy Path**.
3.  Replace the input string:
```python
sys.argv.extend(["--input", "/path/to/your/video.mp4"])
```

## 5. Performance Optimization & Models

### Using YOLOv8m Pose
For better accuracy, the project utilizes the YOLOv8m pose model.
*   **HEF Path:** `/home/raspberrypi/hailo-rpi5-examples/resources/models/hailo8/yolov8m_pose.hef`

### Increasing FPS & Stability
To make the live feed faster and more manageable on the Pi 5, the following arguments are added to the system arguments:

```python
# Disable display sink sync to run as fast as the hardware allows
sys.argv.extend(["--disable-sync"])

# Set a desired frame rate (e.g., 30)
DESIRED_FPS = 30
sys.argv.extend(["--frame-rate", str(DESIRED_FPS)])
```

---

## Appendix: Hailo CLI Arguments Reference

When running or modifying scripts, use these flags to customize the pipeline behavior:

| Option | Command | Description |
| :--- | :--- | :--- |
| **Input** | `--input` / `-i` | Source: file, `usb`, `rpi` (CSI), or `/dev/video<X>`. |
| **Show FPS** | `--show-fps` / `-f` | Prints the current FPS on the video sink. |
| **Architecture** | `--arch` | Specify `hailo8`, `hailo8l`, or `hailo10h`. |
| **HEF Path** | `--hef-path` | Path to the `.hef` model file. |
| **Disable Sync** | `--disable-sync` | Runs pipeline as fast as possible (best for files). |
| **Frame Rate** | `--frame-rate` / `-r`| Manually set the source frame rate (Default: 30). |
| **Callback** | `--disable-callback`| Runs the pipeline without user custom logic. |
| **Debug** | `--dump-dot` | Dumps the pipeline graph to a `pipeline.dot` file. |

---
