# Intelligent Reporting & Spatial Integration

**File Focus:** `pose_estimation_utils.py`

In this iteration, the core utility script was significantly refactored to support the **Spatial Matching** workflow and **Audio Feedback** system. The logic was moved away from attempting NPU operations directly (to avoid device conflicts) and focused instead on data preparation and user interaction.

## 📝 Key Modifications in `pose_estimation_utils.py`

### 1. Spatial Data Handoff (The 'S' Trigger)
Previously, the script only saved a screenshot when 'S' was pressed. Now, it captures the **spatial geometry** of the scene to ensure names are assigned correctly even if people swap positions.

*   **Change:** Added logic to extract the bounding box coordinates `[xmin, ymin, xmax, ymax]` and the ID for every detected person.
*   **Mechanism:** Saves this data to `temp_boxes.json` immediately before triggering the snapshot.
*   **Purpose:** This allows the external Face Recognition script to match a face to a specific **Body Box**, rather than relying on unstable array indices.

```python
# Code Snippet Logic
pose_boxes.append({
    "id": str(i),
    "box": [int(x) for x in det_box]
})
json.dump(pose_boxes, f)
```

### 2. Grouped Status Reporting
The reporting logic was overhauled to summarize information rather than printing individual lines for every detection.

*   **Old Output:**
    *   `Edward is Raising Hand`
    *   `Michael is Raising Hand`
*   **New Output (Aggregated):**
    *   `Edward, Michael is Raising Hand.`
*   **Implementation:** Used a dictionary `action_groups = {}` to collect names under specific actions before printing.

### 3. Integrated Voice Feedback (TTS)
Added **Text-to-Speech** capabilities directly into the visualization loop to provide auditory monitoring feedback.

*   **Library:** Integrated `gTTS` (Google Text-to-Speech) and `playsound`.
*   **Threading:** Crucially, the audio generation and playback were moved to a **Background Thread** (`threading.Thread`).
*   **Why:** This ensures the video feed **does not freeze** while the Raspberry Pi is generating the MP3 file or speaking the report.

### 4. Fail-Safe Initialization
Added robust error handling to the `__init__` logic to prevent the application from crashing if auxiliary files are missing.

*   **Audio Safety:** Checks if `gTTS` is installed; if not, it disables audio mode gracefully without crashing.
*   **Logic Safety:** If `action_logic.py` is missing, it loads a `DummyMonitor` class to keep the video running with default "Monitoring" labels.
*   **Data Safety:** Uses strict `try/except` blocks during Hailo data extraction to prevent `UnboundLocalError` if the NPU output format fluctuates.

### 5. Removal of NPU Context
*   **Change:** Completely removed all `hailo_platform` / `VDevice` initialization code from this file.
*   **Reason:** To permanently solve **Error 74**. This script now strictly handles **CPU-based drawing and logic**, leaving the NPU hardware management entirely to the wrapper script and the external snapshot processor.

---

## 📊 Logic Flow Summary

1.  **Frame Arrival:** Data arrives from the Pose NPU.
2.  **Action Analysis:** Keypoints are sent to `action_logic.py`.
3.  **Name Lookup:** Names are pulled from `name_map.json` using the spatial index.
4.  **Aggregation:** Students are grouped by their current action.
5.  **Trigger Check ('S'):**
    *   If pressed: Save Image + Save Box Coordinates -> Exit for external processing.
6.  **Reporting:**
    *   If restarting after a scan: Print grouped status -> Generate TTS Audio in background thread.
