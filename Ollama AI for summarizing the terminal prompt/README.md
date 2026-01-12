

***

# Vision-Assist: Hybrid AI for Raspberry Pi 5

An advanced assistive technology project that combines real-time computer vision with a local Large Language Model (LLM). This system is designed to help blind users navigate and teachers monitor classroom behavior using the **Raspberry Pi 5** and **Hailo-8 AI Accelerator**.

## Hardware Overview

| Component | Specification | Purpose |
| :--- | :--- | :--- |
| **SBC** | Raspberry Pi 5 | Main processing unit |
| **AI Kit** | Hailo-8L (13 TOPS) | Real-time object and pose detection |
| **Camera** | USB Webcam | Visual input for the AI models |
| **UPS** | Waveshare 3S | Portable power management |
| **Audio** | Speaker/Headphones | Voice feedback for the user |

## Pin Configuration

Use the following GPIO mapping for the 3-way rotary switch and the "Ask AI" push button.

| Device | GPIO Pin | Physical Pin | Mode/Action |
| :--- | :--- | :--- | :--- |
| Switch Pos 1 | GPIO 17 | Pin 11 | Classroom Monitor Mode |
| Switch Pos 2 | — | Pin 9 | Standby (GND) |
| Switch Pos 3 | GPIO 22 | Pin 15 | Blind Navigation Mode |
| Push Button | GPIO 27 | Pin 13 | Trigger AI Scene Description |

## Installation

Follow these steps to set up the environment on your Raspberry Pi 5.

### 1. Hailo Environment Setup
```bash
# Install core Hailo software
sudo apt update && sudo apt install hailo-all espeak-ng mpg123
# Clone and setup the environment
git clone https://github.com/hailo-ai/hailo-rpi5-examples.git
cd hailo-rpi5-examples
./install.sh
source setup_env.sh
```

### 2. Local LLM Setup (Ollama)
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
# Pull the lightweight Qwen model
ollama pull qwen2:0.5b
pip install ollama
```

## Logic Overview: The "Soft Pause"

One of the revolutionary features of this project is the **Soft Pause** mechanism. Running a 30 FPS vision pipeline alongside a Large Language Model can draw over 5 Amps of current, causing power failure.

- **The Trigger:** When the "Ask AI" button is pressed, the controller creates a flag file at `/tmp/hailo_pause`.
- **The Throttling:** The vision script detects this file and immediately skips high-CPU tasks (OpenCV drawing and color conversion).
- **The Result:** CPU overhead is cleared for **Ollama** to generate a summary in 1-3 seconds without crashing the power supply.

## Usage

1. **Start the Master Controller:**
   ```bash
   source setup_env.sh
   python askaicontroller.py
   ```
2. **Select Mode:** Turn the rotary switch to enter a specific AI mode.
3. **Hardware Reset:** When switching, the system enforces a 5-second "Nuclear Cleanup" to release the Hailo PCIe bus safely.
4. **Ask AI:** Press the tactile button at any time to hear a natural language description of the current scene.

## Troubleshooting

- **Status 74 Error:** If you see `HAILO_OUT_OF_PHYSICAL_DEVICES`, wait for the 5-second reset period. Do not flick the switch too quickly.
- **Low Voltage Warning:** This is expected during AI inference. The "Soft Pause" logic minimizes this, but ensure your batteries are high-discharge rated.
- **Audio Issues:** Ensure `espeak-ng` is installed correctly for the text-to-speech feedback.

---
*Developed for the Raspberry Pi 5 AI Maker Community.*
