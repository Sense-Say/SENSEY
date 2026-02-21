# 6th Progress: Spatial 3D Integration (OAK-D Lite + Hailo NPU)

**Focus:** Z-Depth Coordinates, Stereo-Depth Alignment, and NPU Pipeline Optimization.

In this update, the SENSEY system evolves into a **Spatial AI** solution. We have replaced standard USB camera input with the **OAK-D Lite**, allowing the system to fuse human pose keypoints (X, Y) with real-world depth data (Z).

## 🚀 Key Features Added

### 1. 3D Distance Tracking (The "Z" Coordinate)
The system no longer just "sees" students; it knows exactly how far away they are. 
*   **Mechanism:** The OAK-D Lite's onboard stereo-depth processor calculates a depth map in real-time. 
*   **Fusion:** The script identifies the center of a student's body via the Hailo NPU and performs a "depth-lookup" at that specific pixel.
*   **Output:** Labels now display as `Name | Action | Distance (meters)` (e.g., "Edward | Attentive | 2.4m").

### 2. Stereo-to-RGB Alignment
To ensure the Hailo Pose AI and the OAK-D Depth sensor are looking at the same thing, we implemented **Hardware Alignment**.
*   **Logic:** `stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)` forces the depth map to match the RGB camera's perspective perfectly. This prevents "ghost" distances or misaligned labels.

### 3. NPU Post-Processing Synchronization
Because we are no longer using the "black box" official Hailo scripts, we implemented manual **Tensor Decoding**.
*   **The Problem:** The Hailo NPU returns raw mathematical tensors, not coordinates.
*   **The Fix:** Integrated `post_proc.post_process()` with the 5 required parameters (`max_detections`, `score_threshold`, `nms_iou_thresh`, `regression_length`, and `strides`) to turn raw NPU math into the 17 skeleton keypoints.

### 4. High-Performance Buffer Management
Running OAK-D (30 FPS) and Hailo NPU simultaneously can cause "clogged" data lines (`HAILO_TIMEOUT`).
*   **Optimization 1:** Changed queue `maxSize` to **1 or 2** to force the system to drop old frames and only process the **freshest** data.
*   **Optimization 2:** Implemented `np.ascontiguousarray` for NPU inputs, ensuring the fastest possible data transfer over the PCIe bus.

---

## 📂 New File Roles

| File Name | Location | Role Update |
| :--- | :--- | :--- |
| **`oakd_pose_monitor.py`** | `~/Documents/` | **New Master Script.** Orchestrates the OAK-D DepthAI pipeline and the Hailo NPU inference loop. |
| **`pose_estimation_utils.py`** | `hailo-apps/...` | **Signature Update.** Now accepts `depth_map` as a parameter and handles Z-axis visualization. |
| **`cpu_process_screenshot.py`** | `~/Documents/` | **Unchanged.** Still handles the high-accuracy spatial name matching. |

---

## 🔧 Technical Implementation: 3D Data Fusion

The logic inside `pose_estimation_utils.py` was updated to handle the spatial lookup:
```python
# Extract Z-coordinate from the OAK-D depth map
z_mm = depth_map[cy_depth, cx_depth]
distance_m = z_mm / 1000.0 # Convert millimeter to meters
```
This data is then passed to the **Grouped Reporting Logic**, enabling the device to say: *"Edward at 2.5 meters is Attentive."*

---

## 📊 Updated Workflow

### Step 1: 3D Monitoring
Run the new Spatial Monitor script:
```bash
python3 /home/raspberrypi/Documents/oakd_pose_monitor.py
```
*   The OAK-D Lite will initialize, followed by the Hailo NPU.
*   The window will display the live 3D feed.

### Step 2: Identification Snapshot
1.  Press the physical **GPIO 26 Button**.
2.  The system captures the 3D scene, runs the Face ID logic on the CPU, and reloads.
3.  The 3D Monitor resumes with the student's **Name** and **Distance** locked together.

---

## 🛠️ Requirements Update

Ensure you have the DepthAI library installed:
```bash
source /home/raspberrypi/hailo-apps/venv_hailo_apps/bin/activate
pip install depthai==2.32.0.0
```

---
*Next Progress: Moving Face Recognition to the NPU for zero-lag identification.*
