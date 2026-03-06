# 15th Progress: Graph-Based Semantic Navigation & Clew 2.0 Integration

## 🚀 Overview
The 15th progress represents the most significant architectural leap in the **SENSEY** project. We have moved away from simple "breadcrumb following" to a **Graph-Based Navigation Model**. This update implements automatic turn detection, human-centric directional zones, and a self-healing transformation matrix to ensure professional-grade stability for visually impaired teachers.

---

## 🧠 Core Concepts Applied

### 1. Path Node vs. Anchor Node Logic
*   **Concept:** Not all recorded points are equal. "Path Nodes" are silent breadcrumbs used for the "Invisible Tunnel" (audio ticks), while "Anchor Nodes" are landmarks (Turns, Saved Points, or AprilTags) that trigger voice instructions.
*   **Implementation:** The `NavigationManager` now classifies nodes upon loading. It automatically compresses raw breadcrumb data by filtering out segments shorter than 0.6m unless a significant heading change (>30°) is detected.

### 2. 8-Zone Human Directional Logic
*   **Concept:** Blind users cannot easily interpret "Turn 47 degrees." They need relative spatial zones.
*   **Implementation:** We divided the 360° circle around the user into 8 distinct zones:
    *   *Straight Ahead, Front Left/Right, Left/Right Side, Back Left/Right, and Directly Behind.*
*   **Code Location:** `NavigationManager.get_human_direction()`

### 3. Transformation Matrix (The "Clew Snap")
*   **Concept:** If a user starts a route 50cm away from the original starting point, the entire route is traditionally "broken."
*   **Implementation:** We added `offset_x`, `offset_z`, and `offset_yaw` variables. When an AprilTag or Anchor is detected, the system calculates the delta between the "Real World" and the "JSON Map" and **shifts the entire route in memory** to match the user's current position.

---

## 🛠 Problems Identified & Solutions Applied

### 1. The "Instant Arrival" Bug
*   **Problem:** Upon starting navigation, the system would immediately say "Arrived at destination" because the user was standing on the `[0,0]` start point.
*   **Fix:** Modified `load_path` to initialize `current_wp_index = 1`. The system now automatically skips the starting coordinate and aims for the first logical movement.

### 2. The "Christmas Light" Stutter
*   **Problem:** The system would announce every single breadcrumb ("Reached path... Reached path"), creating a chaotic audio experience.
*   **Fix:** Implemented **Instruction Gating**. The system now checks an `is_speaking` flag. It will not calculate or announce a new instruction until the previous sentence has finished playing.

### 3. The "Time Bomb" Audio Distortion
*   **Problem:** Using `aplay` or `paplay` in rapid succession caused "Device Busy" errors and distorted the audio.
*   **Fix:** Migrated to `pygame.mixer` for the navigation "Ticks" and a threaded `subprocess` for Piper TTS. This allows the rhythmic ticking to continue in the background while the AI voice speaks over it.

### 4. Reverse Navigation Logic
*   **Problem:** Simply reversing a list of coordinates doesn't work because the user is facing the wrong way (180° offset).
*   **Fix:** When a reverse route is detected (e.g., "Navigate Desk to Door" when the file is `door_to_desk.json`), the system calls `.reverse()` and immediately issues a **"Please turn around"** instruction to align the user with the new heading.

---

## 📂 Code Function Reference

### `oakd_blind_runner.py`
| Function | Role |
| :--- | :--- |
| `NavigationManager.load_path()` | Converts raw JSON into a compressed Graph; detects turns. |
| `NavigationManager.get_instruction()` | Builds natural sentences: *"Turn front right, walk 4 steps."* |
| `play_navigation_tick()` | Gated audio logic; only plays if the Green Arrow is in the center 1/3. |
| `execute_action()` | Handles the "to" keyword for automatic route reversing. |
| `speak_offline()` | Non-blocking threaded voice synthesis using Piper. |

### `object_detection_post_process.py`
| Function | Role |
| :--- | :--- |
| `draw_detections()` | Renders the 360° Compass HUD and pins the Green Arrow to the **Recorded Yaw**. |
| `calculate_spatial_coords()` | Provides 1cm precision (`.2f`) distance for detected obstacles. |

---

## ✅ Pros and ❌ Cons of the New Architecture

### Pros
*   **Reduced Cognitive Load:** The teacher only hears instructions at corners, not every meter.
*   **Intuitive Guidance:** "Steps" are easier to count than "Meters."
*   **High Stability:** Low-pass filters on Yaw and Distance prevent HUD jitter.
*   **Self-Correcting:** The transformation matrix allows for "Passive Re-alignment" via AprilTags.

### Cons
*   **Stride Dependency:** The "Steps" calculation assumes a 0.75m stride; users with very short or long strides may need calibration.
*   **Initial Orientation:** The system requires the user to be facing roughly the right way at the start (solved by the "Turn Around" prompt).

---

## 🎯 Developer Notes for Testing
1.  **Route Naming:** Always record routes as `LocationA_to_LocationB`. This enables the automatic reverse logic.
2.  **Voice Notes:** Use the "Add voice note" prompt to mark specific hazards like "Low hanging shelf" or "Step down here."
3.  **HUD Alignment:** If the Green Arrow is not centered when you are facing the target, check the `offset_yaw` in the `NavigationManager`.

***

**Next Steps:**
*   Finalizing the **8-Tag AprilTag Map** for absolute classroom relocalization.
*   Implementing **Dynamic Obstacle Safety Overrides** (Muting ticks if a person is in the way).
