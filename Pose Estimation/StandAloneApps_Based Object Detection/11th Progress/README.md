# 🗺️ Blind Navigation System (11th Progress: The AR Environment)

**Focus:** True 3D Checkpoint Rendering, Advanced Perspective Geometry, High-Resolution (1080p) Scaling, and Data Structure Sanitization.

In this 11th phase, the SENSEY system transitions from a functional prototype to a visually immersive Augmented Reality (AR) navigation tool. We completely overhauled the visual post-processing engine to project mathematically accurate 3D structures (checkpoints and guided paths) onto the real-world 1080p camera feed, while ensuring the Hailo YOLOv8 detections map perfectly to this new high-resolution space.

---

## 🚀 Key Technical Implementations

### 1. The 3D Checkpoint Cylinder (GTA-Style Markers)
To make manual landmarks highly visible to a sighted guide or teacher testing the system, we implemented a 3D translucent cylinder projection. 

**The Challenge:** Drawing a flat circle on the screen does not look like it exists in the real world. We had to simulate 3D perspective geometry.

**The Solution:** We draw two ellipses (one on the floor, one hovering at $Y = -0.5m$) and connect them with a transparent polygon. The width of the cylinder dynamically scales based on its real-world distance ($Z$) from the camera.

```python
# Perspective Scaling Math
ellipse_width = int((CYLINDER_RADIUS * FOCAL_LENGTH) / rz)
ellipse_height = int(ellipse_width * 0.3) # Squash factor to simulate depth

# Drawing the Translucent Body
pts = np.array([
    [cx - ellipse_width, ty],
    [cx + ellipse_width, ty],
    [cx + ellipse_width, by],
    [cx - ellipse_width, by]
], np.int32)
cv2.fillPoly(overlay, [pts], color=(0, 0, 255))
cv2.addWeighted(overlay, 0.4, image, 0.6, 0, image) # 40% Opacity
```

### 2. The Transparent Blue Carpet (Segmented Pathing)
Instead of a simple connecting line, the navigation path is now rendered as a 0.6-meter wide continuous "carpet" on the floor. 

**The Challenge:** We wanted to show the path *progressively*. If the user is navigating to Point 2, they shouldn't see the path to Point 5 yet.

**The Solution:** We slice the `waypoints` array up to the next manual landmark. We then calculate perpendicular vectors to create a Left Edge and Right Edge for the path in 3D space, before projecting it to the 2D screen.

```python
# Perpendicular Vector Calculation for Carpet Width
length = math.sqrt(dx*dx + dz*dz) + 0.001
perp_x, perp_z = -dz/length, dx/length

# Left Edge World Coordinates
left_x = wp[0] + (perp_x * PATH_WIDTH / 2)
left_z = wp[1] + (perp_z * PATH_WIDTH / 2)

# Drawing the Carpet
poly = left_points + right_points[::-1] # Reverse right side to close loop
pts = np.array(poly, np.int32).reshape((-1, 1, 2))
cv2.fillPoly(overlay, [pts], color=(255, 150, 0)) # Blue Fill
```

### 3. High-Resolution "Stretch-Fit" AI Scaling
In previous phases, we used "Letterboxing" (black bars) to feed the 4:3 camera into the 1:1 AI model. This wasted screen space. We switched the OAK-D to output a full **1080p (1920x1080) ISP stream** for the display, while stretching a compressed **640x640 Preview stream** for the AI.

**The Challenge:** The Hailo AI outputs bounding boxes based on the warped 640x640 image. We must map these coordinates precisely back to the 1080p image.

**The Solution:** The Hailo output gives normalized coordinates (0.0 to 1.0). By simply multiplying these floats by the target resolution (1920x1080), the boxes map perfectly, eliminating the need for complex padding removal.

```python
# Mapping normalized coordinates to 1080p display
# img_w = 1920, img_h = 1080
ymin, xmin, ymax, xmax = det[:4]
box = [
    int(xmin * img_w), 
    int(ymin * img_h), 
    int(xmax * img_w), 
    int(ymax * img_h)
]
```

### 4. Robust Tensor Extraction (Preventing `ValueError`)
The raw tensor data coming from the `InferVStreams` pipeline can vary in shape depending on the specific YOLO compilation. It frequently crashed with `TypeError: only length-1 arrays can be converted to Python scalars` because the confidence score was wrapped in an extra array dimension.

**The Solution:** We implemented a rigorous extraction loop that flattens the detection arrays and uses enumeration to guarantee the Class ID is captured correctly, preventing the "Everything is a Person" bug.

```python
for class_id, class_list in enumerate(detections):
    if len(class_list) == 0: continue
    for det in class_list:
        # Squeeze brackets out of the data row to ensure clean floats
        det_arr = np.array(det).flatten() 
        if len(det_arr) < 5: continue
        
        # Safely extract the score
        score = float(det_arr[4])
        
        # We now have the correct 'class_id' from the enumeration
        if score >= score_threshold:
             all_detections.append((score, class_id, box))
```

---

## 📂 Updated Software Roles

| File | Modification Focus |
| :--- | :--- |
| **`object_detection_post_process.py`** | Contains the `draw_ar_path`, `draw_3d_checkpoint`, and robust `extract_detections` logic. Acts as the primary rendering engine. |
| **`oakd_blind_runner.py`** | Configures the OAK-D pipeline to split out a high-res `isp` stream for UI and a `preview` stream for AI. Passes the BGR frames directly to the post-processor to fix "Blue Skin" color issues. |

## 🔭 Future Progress: Phase 12
With the AR environment perfectly calibrated, the next logical step is to combine the AR Path with the Object Detection. Phase 12 will focus on **Collision Warning**—calculating if a YOLO bounding box intersects with the AR Blue Carpet to alert the user of an obstacle specifically blocking their route.
