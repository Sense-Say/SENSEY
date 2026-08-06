# 20th Progress: Absolute Relocalization & AprilTag "Ground Truth" Integration

## 🚀 Overview
The 20th progress marks the transition of **SENSEY** from a "Dead Reckoning" system (which inherently drifts over time) to an **Absolute Positioning System**. By integrating `TAG_36H11` AprilTags and mapping them to an 8-point cardinal compass, the system now passively self-calibrates. The user simply walks; if the camera spots a known tag, the system instantly corrects any accumulated IMU or Pedometer drift.

---

## 🧠 The Problem: VIO and IMU Drift
Visual-Inertial Odometry (VIO) relies on integrating accelerometer, gyroscope, and optical flow data over time. 
*   **The Flaw:** Even with a 10-frame smoothing window and physical step-gating, micro-errors accumulate. After 5 minutes of walking, a 2° yaw error can result in the user being guided into a wall.
*   **The Solution:** We require a "Ground Truth" anchor. AprilTags provide high-contrast, mathematically verifiable fiducial markers that the OAK-D Lite can decode at high speeds.

---

## 🛠 Technical Architecture: The Unified AprilTag Logic

Because we are utilizing **DepthAI v2 (2.32.0.0)**, the native `AprilTag` node does not automatically output 3D spatial coordinates (`setTagSize` is unsupported in this specific binding). To bypass this, we engineered a **Unified 4-Gate Verification System** that manually fuses the 2D AprilTag centroid with the hardware Depth Map.

### The 4 Verification Gates (`handle_april_tags`)

1.  **The Center Gate (Lens Offset Compensation)**
    *   *Concept:* We only want to calibrate if the user is intentionally looking *at* the tag, not if they are just walking past it on the periphery.
    *   *Hardware Quirk:* The AprilTag node runs on the **Left Mono Camera** (`CAM_B`), which is physically offset from the center of the device by ~3.75cm. 
    *   *Math:* We shifted the "Center 1/3" acceptance zone 50 pixels to the right (`l_lim = (640 * 0.33) + 50`) to perfectly align the Mono camera's center with the user's physical center.
2.  **The Resolution Scaling Gate**
    *   *Concept:* The Mono camera runs at `640x480` (for high FPS), but the Stereo Depth map runs at `1344x1008` (for high precision).
    *   *Math:* We multiply the Tag's 2D centroid by `(1344/640)` for X and `(1008/480)` for Y to extract the exact depth pixel.
3.  **The Depth Gate (MinZ/MaxZ Protection)**
    *   *Concept:* We must ignore false positives (tiny reflections) and MinZ stereo errors (objects < 0.4m).
    *   *Math:* The system only accepts the tag if `0.5m < z_meters < 3.0m`.
4.  **The Hard Snap (Anti-Spam)**
    *   *Concept:* If the tag passes all gates, we instantly overwrite `current_yaw` with the absolute `World_Yaw` from our `TAG_MAP`.
    *   *Math:* We check `if abs(error) > 2.0°` before snapping. This prevents the terminal from spamming logs 20 times a second if the user is already perfectly aligned.

---

## 📂 Code Implementation Reference

### 1. The Cardinal Map
Defines the absolute "True North" of the classroom environment.
```python
# 🚀 8-Tag Cardinal Map (Tag ID : World Yaw)
TAG_MAP = {
    0: 0.0,    # North (Front Board)
    1: 45.0,   # North-East
    2: 90.0,   # East (Right Wall)
    3: 135.0,  # South-East
    4: 180.0,  # South (Back Door)
    5: 225.0,  # South-West
    6: 270.0,  # West (Left Wall)
    7: 315.0   # North-West
}
```

### 2. The Core Handler Function
```python
def handle_april_tags(april_data, current_yaw, current_x, current_z, depth_frame):
    # 1. Offset Center Gate (640x480 Mono)
    l_lim = (640 * 0.33) + 50
    r_lim = (640 * 0.66) + 50
    
    for det in april_data.aprilTags:
        if det.id in TAG_MAP:
            cx_mono = (det.topLeft.x + det.topRight.x + det.bottomRight.x + det.bottomLeft.x) / 4
            cy_mono = (det.topLeft.y + det.topRight.y + det.bottomRight.y + det.bottomLeft.y) / 4
            
            if l_lim < cx_mono < r_lim:
                # 2. Scale to Depth Map (1344x1008)
                dx, dy = int(cx_mono * 2.1), int(cy_mono * 2.1)
                
                if 0 <= dy < 1008 and 0 <= dx < 1344:
                    z_meters = depth_frame[dy, dx] / 1000.0
                    
                    # 3. Depth Gate
                    if 0.5 < z_meters < 3.0:
                        target_world_yaw = TAG_MAP[det.id]
                        
                        # 4. Hard Snap & Anti-Spam
                        if abs((target_world_yaw - current_yaw + 180) % 360 - 180) > 2.0:
                            current_yaw = target_world_yaw
                            print(f"⚓ ANCHOR SNAPPED! Tag {det.id} at {z_meters:.1f}m. Yaw locked to {current_yaw}°")
                            
    return current_yaw, current_x, current_z
```

### 3. Pipeline Integration (`get_pipeline`)
The AprilTag node is linked directly to the Left Mono camera, running entirely on the Myriad X VPU to ensure zero CPU overhead on the Raspberry Pi 5.
```python
april = p.create(dai.node.AprilTag)
april.initialConfig.setFamily(dai.AprilTagConfig.Family.TAG_36H11)
left.out.link(april.inputImage) # Native v2 API linking
```

---

## ✅ System Impact & UX Benefits
*   **Passive Calibration:** The user does not need to press a button, stand against a wall, or manually scan a tag. The system "heals" its own drift silently in the background.
*   **HUD Stability:** Because the Green Arrow on the HUD is mathematically pinned to the `target_yaw`, when an AprilTag snaps the `current_yaw` into place, the Green Arrow instantly aligns with the physical real-world target.
*   **Reverse Navigation Integrity:** Because the tags represent absolute compass directions (e.g., Tag 4 is always South), they work flawlessly regardless of whether the user is navigating a route forwards or backwards.

***

**Next Phase (Progress 21):**
With the spatial mathematics and audio threading completely stabilized, the final frontier is **Haptic Feedback**. We will integrate an ESP32 via BLE to translate the 3-Zone Safety Shield (Left/Center/Right obstacle detection) into variable-intensity PWM vibration motor pulses.
