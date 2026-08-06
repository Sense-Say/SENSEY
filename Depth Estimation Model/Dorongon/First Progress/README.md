# Depth Estimation with Depth Anything V2 for Raspberry Pi 5

This guide details the installation and setup process for running the Depth Anything V2 model on a Raspberry Pi 5. Depth Anything V2 provides robust monocular depth estimation, which is a crucial component for our SENSEY project's 3D scene understanding capabilities.

---

## 🛠️ Installation Guide

Follow these steps to get Depth Anything V2 up and running on your Raspberry Pi 5.

### Prerequisites

*   A working Raspberry Pi 5 (8GB RAM recommended).
*   Internet connection for downloading models and packages.
*   Python 3 installed (typically default on RPi OS).
*   Thonny IDE or direct terminal access.

### Step-by-Step Setup

1.  **Download Pre-trained Models:**
    *   Navigate to the official Depth Anything V2 GitHub repository: [https://github.com/DepthAnything/Depth-Anything-V2?tab=readme-ov-file#pre-trained-models](https://github.com/DepthAnything/Depth-Anything-V2?tab=readme-ov-file#pre-trained-models)
    *   Download your preferred pre-trained model (e.g., `depth_anything_v2_vits.pth`).

2.  **Clone the Depth Anything V2 Repository:**
    *   Open your Raspberry Pi terminal.
    *   Execute the following commands to clone the repository and navigate into its directory:
        ```bash
        git clone https://github.com/DepthAnything/Depth-Anything-V2
        cd Depth-Anything-V2
        ```

3.  **Install Python Dependencies:**
    *   While in the `Depth-Anything-V2` directory, install the required Python packages:
        ```bash
        pip install -r requirements.txt
        ```

4.  **Place Downloaded Files:**
    *   Move the pre-trained model file (e.g., `depth_anything_v2_vits.pth`) you downloaded in Step 1 into the newly created `Depth-Anything-V2` folder.
    *   From the original Depth Anything V2 GitHub repository (same link as Step 1), download `convert.py` and `live_depth.py`. Place these two script files directly into your `Depth-Anything-V2` folder as well.

5.  **Install Additional Python Packages (if needed):**
    *   You can install these directly via `pip` in your terminal, or use Thonny's "Manage Packages" feature (`Tools > Manage packages...`).
        ```bash
        pip install onnxscript onnx onnxruntime opencv-python
        ```
    *   *Note:* Ensure `onnx` and `onnxruntime` are installed correctly for your RPi's architecture.

### Converting Model to ONNX Format

To optimize performance for the Raspberry Pi environment, we convert the PyTorch model (`.pth`) to the ONNX format (`.onnx`).

1.  **Run the Conversion Script:**
    *   Open Thonny.
    *   Navigate to the `Depth-Anything-V2` folder and open `convert.py`.
    *   Run `convert.py` in Thonny. This script will transform your `depth_anything_v2_vits.pth` file into `depth_anything_v2_vits.onnx`. This ONNX file is more suitable for the RPi's system.

### Running Live Depth Estimation

Once the model is converted, you can run live depth estimation using your RPi's camera.

1.  **Execute Live Depth Script:**
    *   In Thonny, open `live_depth.py`.
    *   Run `live_depth.py`. This script will open a video feed from your camera and display the real-time depth estimation.

---

## ⚠️ Performance Considerations

During our testing, running Depth Anything V2 directly on a Raspberry Pi 5 (8GB RAM model) resulted in a noticeable lag, achieving only **2-3 frames per second (fps)**.

For smoother and faster performance, we anticipate significant improvement by integrating an **RPI AI HAT** (e.g., with 26 TOPS capability). This hardware acceleration is expected to boost the inference speed, making the depth estimation more practical for real-time applications within the SENSEY project.

---
