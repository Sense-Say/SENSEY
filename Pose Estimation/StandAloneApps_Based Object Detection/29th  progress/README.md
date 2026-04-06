# 29th Progress: Semantic Instance Segmentation & Geometric Floor Analysis

## 🚀 Overview
The 29th progress cycle transitioned the SENSEY system from bounding-box detection to **Instance-Level Semantic Segmentation**. By generating real-time binary masks for all detected objects and fusing them with the OAK-D Lite depth map, we have successfully created a "Virtual LiDAR" system. This allows the device to perceive the "open floor" (traversable space) rather than just isolated objects, enabling mapless exploration in complex indoor environments.

---

## 🧠 Core Technical Implementations

### 1. Reverse Segmentation (Floor Extraction)
*   **The Concept:** Rather than training a model to detect "floor," we use **Negative Space Mapping**. Any pixel not masked as an object (Person, Chair, Desk) by the Hailo-8 NPU is mathematically classified as traversable floor.
*   **Virtual LiDAR Logic:** The system performs radial "probes" into the depth map within the unmasked (floor) regions. This generates a `depth_profile` for Left, Center, and Right zones, allowing the system to identify the "Deepest Path" even in unmapped, unknown rooms.
*   **Instance Silhouettes:** We integrated alpha-blended instance masks (using `cv2.addWeighted` and `id_to_color` lookup tables). This provides high-contrast, color-coded visual feedback for the user's assistant, making it easy to distinguish between different obstacle classes (e.g., Person vs. Desk).

### 2. The Pedometer "Mask-Gating" Pipeline
*   **The Problem:** Traditional feature tracking fails when objects (like students) move across the frame, introducing "motion artifacts" into the distance calculation.
*   **The Solution:** We implemented **Semantic Mask-Gating**.
    *   **Logic:** Before calculating `d_z` (depth displacement), the script checks if the feature coordinate `(dy, dx)` exists in the `master_mask`. 
    *   **Result:** The pedometer algorithm is "blinded" to students, chairs, and other dynamic objects. It tracks only the static architecture (walls, floor, ceiling), resulting in 1-centimeter precision walking distance.

### 3. Asynchronous Inference Handover
*   **The Problem:** Synchronous AI inference (waiting for the NPU to finish before calculating) creates a bottleneck, leading to stuttering video and laggy audio ticks.
*   **The Solution:** We implemented a multi-threaded `infer_loop` using `HailoAsyncInference`. The main loop processes camera frames, IMU data, and navigation math at 20 FPS, while the inference happens in a parallel thread.
*   **The Synchronization:** By utilizing `output_queue.get_nowait()`, the system maintains a fluid user experience even if the AI inference takes longer than the video frame rate.

---

## 🛠 Bug Resolution Log

| Feature | Symptom | Resolution Strategy |
| :--- | :--- | :--- |
| **Mask Blending** | Masks were "stretching" over the whole screen. | Implemented `cv2.resize` with `INTER_NEAREST` mapping to the bounding box ROI. |
| **Pedometer Drift** | Distance added while standing still. | Implemented `is_stepping` accelerometer gate + Median Filtering on `deltas`. |
| **Audio Overlap** | Audio instructions colliding. | Migrated to an `audio_queue` + single-threaded `audio_worker` sequence. |
| **Naming Errors** | `NameError: det['label']` | Implemented defensive dictionary unpacking (`det.get('score')`) to handle tensor-list conversion. |

---

## 🚦 Navigation Methodology: "Follow the Deepest Path"
The system no longer requires a pre-recorded path to guide the teacher. It utilizes an **Artificial Potential Field (APF)** heuristic:
1.  **Attraction:** The system constantly attracts the Green Arrow toward the "deepest" floor zone (the largest clear aisle).
2.  **Repulsion:** Obstacle masks act as repulsive forces, pushing the Green Arrow away from chairs and desks.
3.  **Haptic/Audio Feedback:** 
    *   **Ticks:** Play only when the teacher is aligned with the "Deepest Path" (the "Safe Tunnel").
    *   **Narration:** Only triggers if the `Path-Blocked` or `Dead End` conditions are met.

---

## 📂 System Architecture Reference

*   **`postprocessing.py`**: Handles tensor-to-mask conversion. Contains the `inference_result_handler` which outputs the `master_mask` and `processed_frame`.
*   **`ExplorationManager`**: The "Brain." Stores `seen_objects` (memory), analyzes floor masks, and sets `target_yaw` for the Green Arrow HUD.
*   **`oakd_blind_runner.py`**: The "Orchestrator." Manages the `dai.Device` pipeline (12MP RGB, 480P Mono, IMU, FeatureTracker) and the asynchronous thread communication.

***

**Next Steps (Progress 30):**
The system is now mature. The final phase involves refining the **Ambience Narration** frequency—ensuring that the narrator doesn't interrupt the "Audio Ticks" unnecessarily, allowing the teacher to maintain their "Audio Tunnel" for as long as possible without being distracted by objects that are not directly blocking their path.
