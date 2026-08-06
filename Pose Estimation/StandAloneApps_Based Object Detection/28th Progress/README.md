This revised methodology focuses on the real-world application of the SENSEY system, using the graphical user interface (GUI) as the primary point of reference for understanding the underlying math.

### **III. B. Visual-Inertial Odometry and Pedometer Logic**

Indoor navigation for a visually impaired teacher requires a system capable of tracking movement through 3D space with high reliability. Since traditional Global Positioning System (GPS) signals do not penetrate classroom walls, the SENSEY system utilizes Visual-Inertial Odometry (VIO). This technical framework operates by fusing visual data from the OAK-D Lite’s dual monochrome cameras with high-frequency motion data from the BMI270 Inertial Measurement Unit (IMU). The system effectively "sees" movement by tracking specific high-contrast points in the environment and measuring how their distance from the wearer changes in real-time.

The visual component of this logic is represented by the **Feature Tracking** system. The system identifies up to 320 distinct points on static surfaces, such as walls, door frames, or classroom furniture. As the teacher walks forward, these points appear to "expand" outward from the center of the screen, and their depth ($Z$) value decreases. By calculating the median change in depth across all active points, the system can determine exactly how many centimeters the teacher has moved forward. To ensure this data is accurate, the system utilizes a 10-frame sliding window to average out sensor noise and "shimmer," ensuring that the distance only increases during intentional movement.

The inertial component provides a **6-Degree of Freedom (6-DOF)** orientation system. While the cameras track distance, the IMU tracks the teacher's physical posture and heading. The system monitors **Yaw** (turning left or right), **Pitch** (tilting up or down), and **Roll** (leaning side to side). This 6-DOF data is critical because it allows the system to project the forward distance walked onto a 2D map of the classroom. For example, if the teacher walks one meter while facing West ($90^\circ$), the system mathematically understands that the teacher’s position has shifted one meter on the map’s X-axis rather than the Z-axis.

#### **1. Displacement and Positioning Equations**

The following mathematical models are used to calculate the metric distance and spatial coordinates:

*   **Raw Frame Displacement ($\Delta d_{f}$):** This determines the median change in depth for all tracked features between the previous and current frames.
    *   $\Delta d_{f} = \text{Median}(Z_{t-1} - Z_{t})$
    *   $\Delta d_{f}$: The unscaled displacement for a single frame update (meters).
    *   $Z_{t-1}$: The distance to a feature point in the previous frame.
    *   $Z_{t}$: The distance to the same feature point in the current frame.

*   **Total Scaled Distance ($D_{total}$):** This calibrates the unscaled camera data into real-world metric units using an empirical scale factor.
    *   $D_{total} = \sum (\Delta d_{f} \times S)$
    *   $D_{total}$: The cumulative distance reported on the GUI (meters).
    *   $S$: The Calibration Scale Factor ($1.66$), used to align virtual movement with a physical tape measure.

*   **Incremental Position Mapping ($X, Z$):** These project the walked distance onto the classroom’s Cartesian plane based on the user's heading.
    *   $X_{new} = X_{old} + (\text{Step} \times \sin(\theta))$
    *   $Z_{new} = Z_{old} + (\text{Step} \times \cos(\theta))$
    *   $X, Z$: The teacher's current coordinates relative to the route’s start.
    *   $\theta$: The current smoothed Yaw (Heading) value.

**Example Parameter Substitution:**
Suppose a teacher takes a step and the camera measures a raw median depth change ($\Delta d_{f}$) of $0.050\text{m}$ (5 cm). Applying the Scale Factor ($S$) of $1.66$, the system calculates an actual physical step of $0.083\text{m}$. If the teacher is currently facing a Yaw ($\theta$) of $90^\circ$ (pointing directly East), the system calculates $\sin(90) = 1$ and $\cos(90) = 0$. Using the position equations, the teacher’s $X$ coordinate increases by $0.083\text{m}$, while the $Z$ coordinate remains unchanged, accurately mapping the sideways movement across the classroom.

---

#### **2. VIO Logic Gating and Constraints**

To prevent the accumulation of "ghost distance" caused by stationary vibrations or head rotations, the system enforces the following logical gates.

**Table II: Motion Validation Gates**
| Condition | Parameter Logic | Operational Purpose |
| :--- | :--- | :--- |
| **Rotation Shield** | $|\omega| < 0.15\text{ rad/s}$ | Suspends the pedometer if the user is turning their head too quickly to maintain a stable depth map. |
| **Physical Step Gate** | $|Acc| - 9.81 > 0.25G$ | Validates that a physical "jolt" has occurred, ensuring distance is only added during actual walking. |
| **Depth Window** | $0.8\text{m} < Z < 8.0\text{m}$ | Filters out noise from objects that are too close (causing lens interference) or too far to track. |
| **Stabilization Buffer** | $Cooldown = 5\text{ frames}$ | Provides a 0.25s pause after a turn to allow the stereo algorithm to reconstruct the 3D environment. |

---

#### **3. Graphical Representation and HUD Description**

**Figure 2: SENSEY 6-DOF Navigation Interface.**
*Context:* This figure illustrates the live Augmented Reality (AR) HUD used by the system. The yellow dots overlaid on the environment represent the **Feature Trackers** used for VIO distance calculation. The bottom dashboard displays the real-time sensor fusion results: 
1.  **DIST:** The cumulative scaled distance walked ($D_{total}$).
2.  **YAW:** The current cardinal heading used for the $X, Z$ coordinate projection.
3.  **P (Pitch) & R (Roll):** Indicators used to verify the device is mounted level on the teacher’s body.
4.  **Green Arrow:** The target waypoint marker, which is mathematically pinned to a specific World Yaw degree to guide the teacher along the recorded path.
