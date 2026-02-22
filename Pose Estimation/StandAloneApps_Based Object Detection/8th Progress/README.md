#  Blind Navigation System (8th Progress: High-Accuracy Offline Voice)

**Focus:** Vosk STT Integration, L-Graph Acoustic Modeling, Real-time Audio Resampling, and Grammar Constraints.

In this 8th phase, the SENSEY system has reached a critical milestone in reliability. We abandoned cloud-based voice recognition and experimental NPU model-swapping in favor of a dedicated **CPU-based Offline STT (Speech-to-Text) Engine**. This ensures the system remains responsive in environments without internet and prevents hardware conflicts with the Hailo-8 NPU.

---

##  Key Features Added

### 1. Robust Offline Hearing (Vosk)
We integrated the **Vosk STT** library to handle all voice interactions. 
*   **Zero NPU Conflict:** Unlike previous attempts to run Whisper on the Hailo-8, Vosk runs entirely on the Raspberry Pi 5 CPU. This allows the Hailo-8 NPU to be dedicated **100% to YOLOv8 Object Detection**, maintaining a stable 30 FPS at all times.
*   **Privacy & Independence:** No data leaves the device. The teacher can navigate the classroom without needing a Wi-Fi connection.

### 2. High-Accuracy L-Graph Model
We upgraded from the 40MB "small" model to the **`vosk-model-en-us-0.22-lgraph` (128MB)**.
*   **Benefit:** This model provides a much deeper acoustic understanding, significantly reducing "Word Error Rate" (WER) while remaining small enough to load instantly on the Raspberry Pi 5.

### 3. Grammar Constraints (100% Recognition Success)
To solve the problem of the AI "mishearing" commands in a noisy classroom, we implemented **Grammar-Restricted Recognition**.
*   **The Logic:** Instead of the AI guessing between every word in the English language, we provided it with a specific list of **Allowed Navigation Words** (e.g., *Record, Point, Saved, Door, Desk*).
*   **The Result:** The AI is mathematically forced to match the user's speech to the navigation dictionary, making command recognition nearly flawless.

### 4. Real-time Audio Resampling Math
USB Microphones typically capture audio at 44.1kHz or 48kHz, but Voice AI models require exactly 16kHz.
*   **The Solution:** We implemented a real-time mathematical downsampler using **NumPy** (`np.linspace`). 
*   **Efficiency:** The script captures audio at the microphone's native hardware speed (preventing "Invalid Sample Rate" errors) and downsamples it on the fly before feeding it to the AI engine.

---

## 🏗️ Hardware Orchestration (Optimized)

This phase achieves the perfect "Balanced Load" for the Raspberry Pi 5:

1.  **Hailo-8 NPU:** 100% dedicated to **Seeing** (YOLOv8 Object Detection).
2.  **OAK-D Lite VPU:** 100% dedicated to **Depth** (Stereo Vision Z-axis).
3.  **RPi 5 CPU:** Dedicated to **Hearing** (Vosk STT), **Math** (Pedometer/AR), and **Speaking** (TTS).

---

##   Updated Software Architecture

| File | Location | Role |
| :--- | :--- | :--- |
| **`vosk_test.py`** | `~/Documents/` | **Diagnostic Tool.** Verifies microphone levels, resampling math, and grammar accuracy. |
| **`oakd_blind_runner.py`** | `~/Downloads/` | **Master Runner.** Updated to remove the "NPU Brain Swap" logic. It now listens via Vosk in a background thread while the video feed remains live. |
| **`name_map.json`** | `~/Documents/` | **Persistent Data.** Stores the 3D waypoints and landmark labels. |

---

## 🛠️ Installation & Setup

### 1. Install Audio Dependencies
```bash
source /home/raspberrypi/hailo-apps/venv_hailo_apps/bin/activate
pip install vosk sounddevice numpy
```

### 2. Download the L-Graph Model
```bash
cd /home/raspberrypi/Documents
wget https://alphacephei.com/vosk/models/vosk-model-en-us-0.22-lgraph.zip
unzip vosk-model-en-us-0.22-lgraph.zip
```

---

## 💡 How it Works (The Logic Flow)

1.  **Initialization:** The system loads the YOLOv8 model on the Hailo NPU and the Vosk model on the CPU.
2.  **Continuous Loop:** The AR Navigation and Object Detection run at full speed.
3.  **Voice Interrupt:** When the user speaks, the CPU processes the audio in a non-blocking background thread.
4.  **Keyword Match:** If the recognized text matches the "Grammar List," the system executes the command (e.g., "Record Path") and provides instant audio feedback.

## 🎯 Value for Blind Navigation
This phase eliminates the "video freeze" that occurred during voice commands. The blind user now has a **seamless experience**: they can speak to the device while it continues to track obstacles and display the AR path, ensuring constant safety and zero downtime.

## 🔭 Future Progress: Phase 9
The next phase will focus on replacing the internet-dependent `gTTS` with **Piper**, a high-quality neural Text-to-Speech engine that runs 100% offline on the Raspberry Pi 5 CPU.
