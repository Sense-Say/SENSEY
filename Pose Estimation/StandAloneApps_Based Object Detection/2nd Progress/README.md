# 🧭 Blind Navigation System (2nd Progress)

**Focus:** Spatial Awareness & Zonal Logic Implementation

In this phase, we upgraded the standard object detection pipeline to provide **relative positional context**. For a blind navigation aid, knowing *what* is in front of you is not enough; you must know *where* it is (Left, Center, or Right) to navigate around it.

## 🧠 The Logic: How it Works

We modified the post-processing layer of the Hailo application to analyze the geometry of every detected bounding box before it is drawn on the screen.

### 1. Screen Partitioning (The Grid)
The video feed resolution (typically 640x480) is mathematically divided into three vertical zones:
*   **Left Zone:** 0% to 33% of the screen width.
*   **Center Zone:** 33% to 66% of the screen width.
*   **Right Zone:** 66% to 100% of the screen width.

*Visual Aid:* We added vertical white lines to the video output to visually represent these safety corridors during testing.

### 2. Object Centroid Calculation
Instead of using the top-left corner of a bounding box (which can be misleading), we calculate the **Center X-Coordinate** of every detected object:
$$Center\_X = \frac{x_{min} + x_{max}}{2}$$

### 3. Zonal Classification
The system compares the `Center_X` of the object against the zone boundaries:
*   If `Center_X` < 1/3 Width $\rightarrow$ **[LEFT]**
*   If `Center_X` > 2/3 Width $\rightarrow$ **[RIGHT]**
*   Otherwise $\rightarrow$ **[CENTER]**

### 4. Label Injection
We intercept the standard class label (e.g., "Person") and append the calculated position string.
*   *Before:* `Person: 85%`
*   *After:* `Person [CENTER]: 85%`

---

## 📂 Modified System Files

To implement this logic, we modified the internal post-processing script of the standalone application.

| File | Location | Modification |
| :--- | :--- | :--- |
| **`object_detection_post_process.py`** | `hailo_apps/.../object_detection/` | **1.** Added `get_position_text` helper function.<br>**2.** Updated `draw_detections` to render partition lines.<br>**3.** Updated label generation to include spatial tags. |
| **`run_object_detection.py`** | `~/Downloads/` | **Unchanged.** The wrapper simply launches the updated core logic. |

---

## 🧪 Testing the Spatial Logic

1.  Open **Thonny**.
2.  Run the wrapper script: `run_object_detection.py`.
3.  **Visual Verification:**
    *   You will see two vertical white lines splitting the screen.
    *   Move an object (or your hand) from the left side of the frame to the right.
    *   Observe the label change dynamically from **[LEFT]** to **[CENTER]** to **[RIGHT]**.

## 🎯 Value for Blind Navigation
This update lays the groundwork for the **Audio Feedback System**. In the next stage, the Text-to-Speech engine will not just say "Chair," but "Chair on your Right," allowing the user to steer left and avoid the obstacle safely.
