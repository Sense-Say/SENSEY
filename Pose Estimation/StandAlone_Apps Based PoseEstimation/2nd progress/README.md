#  Hailo-8 Classroom Monitoring System (Pose & Dynamic Identity)

This project demonstrates a highly stable, high-performance application for student monitoring using the Raspberry Pi AI Kit (Hailo-8/8L). It runs Pose Estimation on the NPU and uses a pre-scanned map for dynamic student identification, completely eliminating the risk of CPU overload and undervoltage.

##  Key Features

*   **NPU-Powered Performance**: Both Pose Estimation (YOLOv8) and Face Recognition (ArcFace) are offloaded to the Hailo-8 chip.
*   **Zero CPU Overload**: CPU usage remains low, preventing undervoltage issues common to multi-AI systems on the Raspberry Pi 5.
*   **Dynamic Labeling**: Student names are loaded from a JSON map created by a one-time "Snapshot" scan, ensuring the system runs smoothly without continuous face checks.
*   **Fail-Safe Design**: The system is designed to run flawlessly even if the face database or map files are missing.

---

## 🛠️ Deployment Guide

### 1. Prerequisites and Setup

| Component | Requirement | Note |
| :--- | :--- | :--- |
| **Hardware** | Raspberry Pi 5 + Hailo AI Hat+ (Hailo-8L) | Ensure the device is powered by a high-quality 5V, 5A supply. |
| **Software** | Hailo Software Suite | Run `sudo apt install hailo-all` |
| **Repositories** | `hailo-apps` | Clone the repository to `/home/raspberrypi/hailo-apps`. |
| **Camera** | USB Webcam | Will be accessed as `/dev/video0`. |

### 2. Environment and Library Installation

The system requires a specific virtual environment to manage library versions.

1.  **Clone the Repo and Create VENV**:
    ```bash
    cd /home/raspberrypi
    git clone https://github.com/hailo-ai/hailo-apps.git
    cd hailo-apps
    python3 -m venv venv_hailo_apps
    source venv_hailo_apps/bin/activate
    ```

2.  **Install Dependencies**: (Hailo is sensitive to the NumPy version)
    ```bash
    pip install "opencv-python<=4.10.0.84" "numpy<2.0" pillow customtkinter 
    ```

3.  **Download NPU Models**:
    ```bash
    ./download_resources.sh
    # You will need both yolov8m_pose.hef and arcface_mobilefacenet.hef
    ```

### 3. File Structure and Paths

This project relies on three scripts being placed in a stable, easily accessible location, like `/home/raspberrypi/Downloads`.

| File | Location | Purpose |
| :--- | :--- | :--- |
| `npu_face_enrollment.py` | `/home/raspberrypi/Downloads/` | GUI for creating the face database (`npu_encodings.pickle`). |
| `npu_face_snap.py` | `/home/raspberrypi/Downloads/` | The one-time script that executes the NPU scan and creates the `name_map.json`. |
| `pose_estimation_utils.py & pose_estimation.py` | `hailo-apps/.../pose_estimation/` | **The Core Patch.** Reads the JSON and draws the final labels. |
| **Output Files** | `/home/raspberrypi/Downloads/` | `npu_encodings.pickle` & `name_map.json`. |

---

## 💻 Operational Workflow (The Monitoring Process)

The system works in three distinct, sequential phases. You must run each phase manually.

### Phase 1: Enrollment (Creating the Brain)
This phase creates the mathematical representation of each student's face on the NPU.

1.  **Open Terminal and Activate VENV**:
    ```bash
    source /home/raspberrypi/hailo-apps/venv_hailo_apps/bin/activate
    ```
2.  **Run Enrollment GUI**:
    ```bash
    python3 /home/raspberrypi/Downloads/npu_face_enrollment.py
    ```
3.  **Action**: Use the GUI to enroll faces (take multiple photos).
4.  **Finish**: Click "Generate NPU Encodings." This creates **`npu_encodings.pickle`**.

### Phase 2: Snapshot (Naming the Students)
This phase is the only time the Face Recognition NPU runs. It scans the room and saves the names to a map.

1.  **Run Snapshot Script**:
    ```bash
    python3 /home/raspberrypi/Downloads/npu_face_snap.py
    ```
2.  **Action**: The terminal will show the NPU processing, and the script will create the **`name_map.json`** file.

### Phase 3: Monitoring (The Final Run)
This is the final, stable monitoring run. The system reads the name map and runs Pose Estimation at full speed.

1.  **Run Monitoring Script**:
    ```bash
    # Ensure you set the HAILO_SCHEDULER flag in your wrapper script!
    python3 standalone_poseversion2.py
    ```
2.  **Result**: The video feed opens, the FPS is high, and the labels are correctly mapped to **"[Student Name] | [Action] | [Score]"**.

---

##  4. The Role of Action Logic and Data Flow

The system is a true multi-stage processing pipeline. The **`action_logic.py`** script is not just used—it is the **primary intelligence layer** that processes the raw data from the Hailo chip.

### A. Action Logic (`action_logic.py`)

This script is responsible for translating **raw keypoints** (X, Y coordinates of joints) into **human behavior**.

| Function | Data Input | Output | Usage |
| :--- | :--- | :--- | :--- |
| **`action_logic.py`** | Raw Pose Keypoints (X, Y) | **Behavior** (e.g., "Raising Hand," "Standing") and **Color** (e.g., Red for Alert, Green for Normal). | This logic runs *every single frame*. It dictates the final label and the color of the bounding box. |

**Integration Point:** In the final `pose_estimation_utils.py` you are running, the script makes two crucial calls to the action logic:

1.  **`act_txt, act_col = self.action_monitor.get_action(...)`**: This line determines the student's behavior.
2.  **`cv2.rectangle(..., act_col, 2)`**: This uses the color returned by the action logic to provide instant visual feedback on the screen.

### B. The Full Data Flow Path

This shows how all the pieces of your project work together in the final system:

| Stage | Component | Output | Purpose |
| :--- | :--- | :--- | :--- |
| **1. Sensing** | USB Camera | BGR Frame | Continuous video input. |
| **2. Core Inference** | Hailo-8 NPU | **Keypoints (X, Y)** + Bounding Boxes | Finds bodies (Pose Estimation). |
| **3. Behavior Analysis** | `action_logic.py` (CPU) | **Action Text** & **Color** | Calculates behavior (Running every frame). |
| **4. Identity Lookup** | `name_map.json` (File) | **Student Name** | Provides the name (Pre-scanned). |
| **5. Final Display** | `pose_estimation_utils.py` (CPU) | **"[Name] | [Action] | [Score]"** | Draws the composite label on the screen. |

**Conclusion:** The Action Logic is fully integrated and running continuously. The system defaults to this logic (showing "Monitoring" or "Raising Hand") and only updates the **Name** when the JSON file tells it to.

---

## 💡 Troubleshooting & Trivia

| Issue | Root Cause & Solution |
| :--- | :--- |
| **`HAILO_OUT_OF_PHYSICAL_DEVICES` (Error 74)** | The Hailo chip is locked by a previous process. This is solved by setting the system flag: `env["HAILO_SCHEDULER"] = "1"`. |
| **Video Window Freezes/No Bar** | Wayland/X11 conflict. Solved by setting environment variables: `QT_QPA_PLATFORM=xcb` and `DISPLAY=:0`. |
| **"Unknown" Name on Screen** | The **`name_map.json`** is missing or the face was not clearly visible during **Phase 2**. |
| **Trivia Fact** | We use the **Pose AI's Nose Keypoint** to help the Face AI find your head. This technique is called **Cascaded Vision**. |
| **Final Exit** | Use the **`Q`** key when the video window is active. It is programmed to perform a clean exit (`os._exit(0)`). |
| **Thonny not Configured** | Click Run --> Configure Interpreter --> Cick the three dots [...] button --> find this path in venv_apps and click**python3**(/home/raspberrypi/hailo-apps/venv_hailo_apps/bin/python3) |
