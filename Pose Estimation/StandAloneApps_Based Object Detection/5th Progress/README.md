
#  True Spatial AI Fusion

**Focus:** OAK-D Lite Integration, 3D Coordinate Mapping (XYZ), Field of View Maximization, and Hardware Limitations.

In this 5th phase, the system evolves from a 2D "flat" object detector into a **3D Spatial Awareness System**. By upgrading the camera hardware to the Luxonis OAK-D Lite, we transitioned from simply knowing *what* an object is, to knowing exactly *where* it is in physical space (measured in meters). 

This progress establishes the "Host-Side Fusion" architecture that will be replicated across all future SENSEY monitoring projects.

---

## 🏗️ Hardware Architecture & Roles

To prevent the Raspberry Pi 5 from experiencing thermal throttling or undervoltage, processing tasks are strictly divided across three distinct processors:

1.  **Luxonis OAK-D Lite (Myriad X VPU): The "Eyes & Depth"**
    *   Captures high-resolution RGB video.
    *   Uses dual monochrome cameras to calculate a stereo depth map in real-time.
    *   *Zero CPU cost to the Raspberry Pi.*
2.  **Hailo-8 AI Hat (NPU): The "Brain"**
    *   Receives the RGB frame and processes the YOLOv8m Object Detection model.
    *   Outputs 2D bounding boxes and class IDs.
3.  **Raspberry Pi 5 (CPU): The "Coordinator"**
    *   Acts as the bridge. It matches the 2D bounding box from Hailo to the 3D Depth Map from the OAK-D to calculate the final X, Y, Z coordinates.

---

## 🧠 Core Spatial Concepts Resolved

### 1. Host-Side Spatial Fusion (The Math)
Because the AI (Hailo) and the Depth (OAK-D) run on separate chips, they must be aligned by the Pi. 
*   **Alignment:** The OAK-D is instructed to hardware-warp the depth map to perfectly match the RGB camera's perspective (`setDepthAlign`). 
*   **Extraction:** We calculate the center pixel of the Hailo bounding box. We then look up that exact pixel in the OAK-D depth map to get the **Z (Distance)** in millimeters.
*   **Horizontal Mapping:** Using the camera's focal length, we calculate the **X (Horizontal)** distance to determine exactly how far left or right the object is from the user.

### 2. Maximizing Field of View (Letterboxing)
Blind navigation requires the widest possible angle to detect obstacles.
*   **The Problem:** The OAK-D RGB sensor is rectangular (4:3 ratio). The Hailo YOLOv8 model requires a square (1:1 ratio, 640x640). Simply forcing the camera to 640x640 crops the left and right sides of the lens, creating a dangerous "tunnel vision" blind spot.
*   **The Solution:** We set the camera to capture its native `640x480` wide view. Before sending the frame to Hailo, we **Letterbox** it—placing the wide rectangle in the center of a black 640x640 square. The AI processes the full room without distortion, and our math automatically accounts for the padding.

### 3. The Auto-Focus Hazard
The OAK-D Lite's RGB camera (IMX214) features an active Auto-Focus lens. 
*   **The Issue:** As the blind user walks, the lens constantly "hunts" for focus. This physical movement of the lens slightly changes the focal length, which completely ruins the accuracy of the depth calculation and makes the video feed blurry.
*   **The Fix:** We locked the camera to a manual focus position (`setManualFocus(10)`), setting it to "Infinity." This ensures everything from 1 meter to the back of the room remains perfectly sharp and the spatial math remains perfectly stable.

### 4. Hardware Limitations: MinZ and Occlusion
Understanding the physical limits of the OAK-D Lite is critical for blind navigation:
*   **Minimum Distance (MinZ):** The stereo cameras are 7.5cm apart. Due to trigonometry, they cannot calculate depth for objects closer than **~30cm**. Objects closer than this return a distance of `0`. Our code actively filters out `0` values to prevent false readings. For a blind user, an object <30cm is considered an immediate collision hazard.
*   **Occlusion:** The cameras cannot see through solid objects. If a chair is in front of a table, only the chair is detected. This is *desired* behavior for navigation, as the user only needs to avoid the closest immediate obstacle.

---

## 📂 Software Architecture (Bypassing the Official Wrapper)

To achieve this level of hardware integration, we had to abandon the official Hailo `ObjectDetectionApp` Python class. The official class is designed strictly for USB webcams or GStreamer streams and does not natively accept OAK-D depth arrays.

**The New Two-File Structure:**

1.  **The Custom Runner (`oakd_blind_runner.py`)**
    *   Manually configures the DepthAI pipeline.
    *   Manually initializes the Hailo `VDevice` and `InferVStreams`.
    *   Explicitly provides the list of COCO labels (since we bypassed the official script that usually reads the JSON).
    *   Passes both the RGB frame and the Depth frame to the post-processor.

2.  **The Post-Processor (`object_detection_post_process.py`)**
    *   Safely extracts raw tensors from Hailo (using robust shape checking to prevent `UnboundLocalError`).
    *   Draws the Left/Center/Right partition UI.
    *   Performs the Depth median-filtering (scanning a small ROI around the object center to ignore noisy pixels).
    *   Renders the final label: `[Class] [Position] [Distance in Meters]`.

---

## 🔭 Future Implications for Student Monitoring

The architecture established in this 5th Progress is the exact blueprint required for the next phase of the **Classroom Monitoring System**. 

By applying this exact OAK-D data flow to the **Pose Estimation** project, we will be able to extract the Z-Distance of specific body keypoints (e.g., determining if a hand is raised high *and* is 3 meters away). This will grant the Action Logic 3D contextual awareness, drastically reducing false positives in behavior detection.
