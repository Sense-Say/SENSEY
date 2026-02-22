#  Blind Navigation System (9th Progress: The 100% Offline Loop)

**Focus:** Piper Neural TTS Integration, Synchronized Ear-Mouth Logic, Software Muting, and System Autonomy.

In this 9th phase, the SENSEY system achieves **Total Autonomy**. We have replaced the internet-dependent Google TTS with **Piper**, a high-speed neural Text-to-Speech engine. By combining **Vosk (Hearing)** and **Piper (Speaking)** on the Raspberry Pi 5 CPU, the device now functions completely offline, ensuring safety and privacy for the blind user in any environment.

---

## 🚀 Key Features Added

### 1. Neural Offline Speech (Piper TTS)
We integrated the **Piper TTS** engine, which utilizes ONNX runtime to generate human-like speech locally.
*   **Quality:** Unlike traditional robotic offline voices (like eSpeak), Piper uses neural networks to produce natural, clear audio.
*   **Performance:** Optimized for the RPi 5, Piper generates audio in milliseconds, providing the "Instant Feedback" required for real-time navigation.
*   **Zero Internet:** The system no longer needs a Wi-Fi connection to provide status updates or landmark confirmations.

### 2. The "Software Muting" Logic (Feedback Fix)
A major challenge in voice-controlled robotics is the "Self-Hearing" loop—where the microphone hears the system's own speakers and misinterprets it as a new command.
*   **The Logic:** We implemented a global `is_speaking` flag (Software Lock).
*   **The Result:** The system **automatically "closes its ears"** the moment it starts talking. It ignores all microphone input while the speakers are active, preventing infinite repeating loops.

### 3. Short-Term Memory Reset
To ensure the system doesn't act on old information, we implemented a **Recognizer Reset** protocol.
*   **Mechanism:** Every time a command (e.g., "Record Path") is successfully parsed and confirmed, the script calls `rec.Reset()`.
*   **Purpose:** This wipes the AI’s temporary audio buffer clean, ensuring that the next command is fresh and not confused by leftover words from the previous interaction.

### 4. Background Audio Threading
To maintain a high-speed video feed for navigation, the "Mouth" (Piper) and "Ear" (Vosk) run on separate threads.
*   **Parallelism:** Speech generation happens in a background thread, allowing the **Hailo-8 NPU** to continue its YOLOv8 object detection without a single frame of lag.

---

## 📂 System Architecture Update

The system now runs three major AI components simultaneously:

| Component | Logic Type | Hardware | Role |
| :--- | :--- | :--- | :--- |
| **YOLOv8** | Vision | **Hailo-8 NPU** | Obstacle Detection & AR. |
| **Vosk** | Hearing | **RPi 5 CPU** | Offline Command Recognition. |
| **Piper** | Speaking | **RPi 5 CPU** | Offline Neural Feedback. |

---

## 🔧 File Roles & Integration

| File | Location | Modification |
| :--- | :--- | :--- |
| **`piper`** (Binary) | `~/Documents/piper/` | The core neural speech engine executable. |
| **`vosk_piper_stable.py`**| `~/Documents/` | **Diagnostic Tool.** Tests the synchronized Ear-Mouth loop with muting logic. |
| **`oakd_blind_runner.py`** | `~/Downloads/` | **Master Runner.** Now uses `speak_offline` (Piper) instead of `gTTS`, creating a 100% offline experience. |

---

## 🛠️ Installation & Setup

### 1. Install Audio Utilities
Piper and Vosk require low-level Linux audio tools for stable operation.
```bash
sudo apt update
sudo apt install alsa-utils mpg123 flac
```

### 2. Download the Neural Voice Brain
The system uses the "Lessac" voice model for professional, clear instructions.
```bash
cd ~/Documents/piper
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

---

## 💡 The "Voice Handshake" (How it works)

1.  **User Trigger:** User holds Button 26 and speaks: *"Record door to desk."*
2.  **Recognition:** Vosk (The Ear) identifies the command locally on the CPU.
3.  **Locking:** The system sets `is_speaking = True` and locks the microphone.
4.  **Feedback:** Piper (The Mouth) says: *"Starting record door to desk."*
5.  **Reset:** Once speech ends, the system clears its audio buffer and sets `is_speaking = False`.
6.  **Ready:** The system waits for the next command while the Hailo NPU continues to draw the AR path.

## 🎯 Value for Blind Navigation
This phase makes the device **truly portable**. It can be used in classrooms, hallways, or outdoor areas where Wi-Fi is unavailable. By removing all cloud dependencies and implementing the muting fix, the system provides a reliable, responsive, and professional user experience.

## 🔭 Future Progress: Phase 10
The next phase will focus on **Environmental Voice Narrator**—integrating the YOLOv8 object detections with Piper so the system automatically narrates the room (e.g., *"Chair ahead, 2 meters"*).
