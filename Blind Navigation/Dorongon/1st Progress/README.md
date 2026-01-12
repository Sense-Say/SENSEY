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

## Troubleshooting
- **No Lines on Screen**: Ensure `--use-frame` is included in `sys.argv`.
- **ModuleNotFoundError**: Ensure you ran `source setup_env.sh` before executing.
- **Laggy Video**: Ensure `--disable-sync` is enabled and that you are not running other heavy background processes.
