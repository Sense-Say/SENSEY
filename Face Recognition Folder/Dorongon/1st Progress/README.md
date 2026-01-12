# Raspberry Pi Face Recognition System - Setup & Usage Guide

This guide details the steps to set up a real-time face recognition system on a Raspberry Pi using a custom GUI for enrollment/training and a separate script for real-time recognition.

---

## 1. Hardware Requirements

*   **Raspberry Pi:** Pi 3B+, 4, or 5 (recommended for better performance).
*   **Camera:** Raspberry Pi Camera Module (V2 or V3 recommended) or a compatible CSI camera.
*   **Storage:** MicroSD card with Raspberry Pi OS (Bookworm) installed.
*   **Peripherals:** Power supply, monitor, keyboard, mouse (or SSH access).

---

## 2. Prepare Your Raspberry Pi

Ensure your Raspberry Pi OS is up to date and that you have the necessary development tools installed.

### A. Update System
Open a terminal and run:
```bash
sudo apt update
sudo apt full-upgrade -y

### B. Install System Dependencies
Install the required system-level libraries for `dlib` (face recognition engine) and Pillow (image processing):
```bash
sudo apt install -y build-essential cmake pkg-config libjpeg-dev libpng-dev libtiff-dev libavcodec-dev libavformat-dev libswscale-dev libv4l-dev libxvidcore-dev libx264-dev libgtk-3-dev python3-pip python3-pil python3-pil.imagetk
```
*   **build-essential, cmake, pkg-config:** For compiling C++ libraries like `dlib`.
*   **libjpeg-dev, etc.:** Image/video processing libraries.
*   **libgtk-3-dev:** For OpenCV GUI support.
*   **python3-pil.imagetk:** Critical for Pillow to work with the CustomTkinter GUI.

### C. Enable Camera Interface
1.  Go to **Menu > Preferences > Raspberry Pi Configuration**.
2.  Navigate to the **Interfaces** tab.
3.  Ensure **Camera** is set to **Enabled**.
4.  Click **OK** and **Reboot** if prompted.

---

## 3. Create Project Folder

Organize your files in a dedicated directory.

```bash
cd ~/Desktop/
mkdir FaceRecognitionApp
cd FaceRecognitionApp
```

---

## 4. Virtual Environment (Recommended)

To avoid installation errors, create a virtual environment before installing Python libraries.

1.  **Create the environment:**
    ```bash
    python3 -m venv .venv
    ```
2.  **Activate the environment:**
    ```bash
    source .venv/bin/activate
    ```
    *(Note: You must run this activation command every time you open a new terminal to work on this project).*

---

## 5. Install Python Libraries

Install the required Python packages inside your virtual environment.

```bash
pip install opencv-python numpy face_recognition imutils picamera2 customtkinter
```

> **Note:** The `face_recognition` library installation involves compiling `dlib`. This process can take **15–45 minutes** depending on your Raspberry Pi model. It may look stuck—**be patient and let it finish.**

---

## 6. Project Scripts

Ensure the following scripts are inside your `FaceRecognitionApp` folder:

### 6.1 `Finale_Face_Recognition_training.py`
*   **Purpose:** Provides a GUI for entering names and capturing face images.
*   **Function:** Captures photos, saves them to a `dataset` folder, and trains the model (generates the `.pickle` file).

### 6.2 `facial_recognition.py`
*   **Purpose:** Performs the actual real-time detection.
*   **Function:** Loads the trained model, opens the camera, detects faces, and draws bounding boxes/names on the video feed.

---

## 7. How to Run the System

### Step 1: Enrollment & Training
1.  Navigate to your folder and activate the environment (if not already active):
    ```bash
    cd ~/Desktop/FaceRecognitionApp
    source .venv/bin/activate
    ```
2.  Run the GUI App:
    ```bash
    python Finale_Face_Recognition_training.py
    ```
3.  **Usage:**
    *   Enter a Name.
    *   Click **Enrollment** to capture photos.
    *   Click **Train Model** to generate encodings.
    *   Click **Exit**.

### Step 2: Real-Time Recognition
Run the main recognition script:
```bash
python facial_recognition.py
```
*   Press **'q'** to quit the video feed.

---

## 8. Important Notes & Troubleshooting

*   **Virtual Environment:** If you get `ModuleNotFoundError`, make sure you typed `source .venv/bin/activate` before running python.
*   **Lighting:** Ensure good lighting when capturing training photos for better accuracy.
*   **Performance:** If the video is laggy, ensure `facial_recognition.py` has frame skipping enabled or uses the `model='small'` setting for encodings.
```
