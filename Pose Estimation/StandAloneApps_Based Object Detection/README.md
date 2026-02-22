# 🧮 SENSEY Blind Navigation: Core Mathematical Framework

The SENSEY system relies on several layers of geometric, spatial, and kinematic mathematics to convert raw pixel and sensor data into real-world navigation instructions. Below are the core formulas implemented across the project's progress phases.

---

## 1. Object Centroid Calculation (2D Spatial Zonal Logic)
*Implemented in: Progress 2 (Left/Center/Right Awareness)*

To determine whether an object is to the left, center, or right of the user, we calculate the geometric center (centroid) of the 2D bounding box provided by the YOLOv8 model.

**Formula:**
$$Center_{X} = \frac{X_{min} + X_{max}}{2}$$
$$Center_{Y} = \frac{Y_{min} + Y_{max}}{2}$$

**Zonal Thresholds:**
*   $Left = Center_{X} < (\frac{Width}{3})$
*   $Right = Center_{X} > (\frac{2 \times Width}{3})$
*   $Center = \text{Otherwise}$

---

## 2. Letterbox Scaling & Coordinate Mapping
*Implemented in: Progress 5 (FOV Maximization)*

To feed the wide 4:3 camera image (640x480) into the square 1:1 AI model (640x640) without distortion, we use a uniform scaling factor and add padding.

**Scaling Factor ($S$):**
$$S = \min\left(\frac{Target_{W}}{Image_{W}}, \frac{Target_{H}}{Image_{H}}\right)$$

**New Dimensions:**
$$New_{W} = Image_{W} \times S \quad | \quad New_{H} = Image_{H} \times S$$

**Padding Offsets:**
$$Pad_{X} = \frac{Target_{W} - New_{W}}{2} \quad | \quad Pad_{Y} = \frac{Target_{H} - New_{H}}{2}$$

*To map the AI's bounding box back to the original image, we reverse this process (Denormalization).*

---

## 3. Host-Side Spatial Calculation (3D Pinhole Camera Model)
*Implemented in: Progress 5 (XYZ Real-World Coordinates)*

To find the real-world position of an object, we map the 2D pixel coordinates $(u, v)$ to the OAK-D depth map (which provides $Z$), and then use the camera's intrinsic parameters (Focal Length $f_x, f_y$ and Optical Center $c_x, c_y$) to find $X$ and $Y$ in meters.

**Z (Depth in meters):**
$$Z = \frac{\text{Median}(Depth\_ROI)}{1000}$$

**X (Horizontal distance in meters):**
$$X = \frac{(u - c_x) \times Z}{f_x}$$

**Y (Vertical height in meters):**
$$Y = \frac{(v - c_y) \times Z}{f_y}$$

---

## 4. Euler Integration for Heading (Inertial Odometry)
*Implemented in: Progress 6 (VIO Engine)*

The BMI270 IMU provides raw angular velocity ($\omega_z$) in radians per second. To find the current heading (Yaw) in degrees, we integrate this velocity over the time difference ($dt$) between frames.

**Delta Time ($dt$):**
$$dt = Time_{Current} - Time_{Previous}$$

**Change in Yaw ($\Delta\theta$):**
$$\Delta\theta = \omega_z \times \left(\frac{180}{\pi}\right) \times dt$$

**Current Heading ($\theta_{current}$):**
$$\theta_{current} = (\theta_{previous} + \Delta\theta) \pmod{360}$$

---

## 5. Visual Pedometer (Optical Odometry)
*Implemented in: Progress 6 (VIO Engine)*

To measure physical distance walked without relying on error-prone accelerometers, we track the change in the Z-depth ($\Delta Z$) of static features in the room.

**Distance Delta for Feature $i$:**
$$\Delta Z_i = Z_{previous\_i} - Z_{current\_i}$$

**Total Distance Step ($D_{step}$):**
*Calculated by averaging all valid, realistic $\Delta Z$ values in a frame (ignoring noise).*
$$D_{step} = \frac{1}{N} \sum_{i=1}^{N} \Delta Z_i \quad \text{(where } 0.01 < |\Delta Z_i| < 0.30\text{)}$$

**Total Distance Accumulated ($D_{total}$):**
$$D_{total} = D_{total} + D_{step}$$

---

## 6. Global 2D Position Tracking (Cartesian Coordinates)
*Implemented in: Progress 7 (Waypoint Mapping)*

Using the accumulated distance ($D_{total}$) and current heading ($\theta_{current}$), we calculate the user's global position $(X_{global}, Z_{global})$ relative to their starting point (the Anchor).

**Position Update:**
$$X_{global} = D_{total} \times \sin(\theta_{current\_rad})$$
$$Z_{global} = D_{total} \times \cos(\theta_{current\_rad})$$

*(Note: In 3D space, Z is forward/backward, X is left/right, and Y is up/down).*

---

## 7. AR Perspective Projection (3D to 2D Screen Mapping)
*Implemented in: Progress 7 (AR Path Drawing)*

To draw digital waypoints on the real floor in the video feed, we reverse the Pinhole Camera Model. We translate the global point relative to the user, rotate it based on the user's heading, and project it onto the 2D screen.

**1. Translation (Relative to Camera):**
$$\Delta X = X_{target} - X_{camera}$$
$$\Delta Z = Z_{target} - Z_{camera}$$

**2. Rotation Matrix (Applying Yaw):**
$$X_{rotated} = \Delta X \cos(-\theta_{yaw}) - \Delta Z \sin(-\theta_{yaw})$$
$$Z_{rotated} = \Delta X \sin(-\theta_{yaw}) + \Delta Z \cos(-\theta_{yaw})$$

**3. Screen Projection:**
$$Screen_X = \left(\frac{X_{rotated} \times f_x}{Z_{rotated}}\right) + c_x$$
$$Screen_Y = \left(\frac{Camera\_Height \times f_y}{Z_{rotated}}\right) + c_y$$

---

## 8. Turn-by-Turn Routing Math
*Implemented in: Progress 10 (Navigation Engine)*

To give audio instructions ("Turn 45 degrees right, walk 2 meters"), the system calculates the distance and relative angle between the user's current position and the next waypoint.

**Distance to Target ($D_{target}$):**
$$D_{target} = \sqrt{(X_{target} - X_{current})^2 + (Z_{target} - Z_{current})^2}$$

**Absolute Angle to Target ($\theta_{target}$):**
$$\theta_{target} = \arctan2(X_{target} - X_{current}, Z_{target} - Z_{current}) \times \left(\frac{180}{\pi}\right)$$

**Relative Turn Angle ($\theta_{turn}$):**
$$\theta_{turn} = (\theta_{target} - \theta_{current}) \pmod{360}$$
*(If $\theta_{turn} > 180$, we subtract $360$ to get the shortest turn path, e.g., $-45^\circ$ instead of $315^\circ$)*.
