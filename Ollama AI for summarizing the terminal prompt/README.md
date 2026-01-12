# Vision-Assist: Hybrid AI for Raspberry Pi 5

A revolutionary assistive technology project that combines high-speed computer vision with a local Large Language Model (LLM). This system is specifically designed for the **Raspberry Pi 5** and the **Hailo-8 AI Accelerator** to help blind users navigate and teachers monitor classroom behavior.

## Project Concept
This project utilizes a "Fast-and-Slow" AI architecture. The **Hailo-8** chip handles survival-critical, real-time detection at 15-30 FPS, while a local **Ollama (Qwen2)** model provides high-level scene descriptions only when requested by the user.

## Key Features
- **Blind Navigation:** Spatial 3-column detection (Left, Center, Right) with majority-area logic.
- **Classroom Monitor:** Real-time pose estimation to detect *Standing, Walking, and Hand Raising*.
- **Ask AI Button:** Converts technical system logs into a natural human sentence using Qwen2-0.5B.
- **Soft Pause Logic:** An innovative resource-management system that prevents power crashes during heavy AI tasks.
- **Tactile Design:** Full hardware control using an industrial 3-way rotary switch and tactile buttons.

## Hardware Requirements

| Component | Specification |
| :--- | :--- |
| **SBC** | Raspberry Pi 5 (4GB/8GB) |
| **AI Accelerator** | Raspberry Pi AI Kit (Hailo-8L) |
| **Power Supply** | Waveshare UPS 3S or 5V/5A Adapter |
| **Switch** | 3-Position Rotary or Toggle Switch (ON-OFF-ON) |
| **Button** | Momentary Push Button (Tactile) |
| **Audio** | Speaker or Headphones (via 3.5mm or USB) |

## GPIO Wiring Map

| Connection | GPIO Pin | Physical Pin | Mode/Action |
| :--- | :--- | :--- | :--- |
| Switch (Left/Up) | GPIO 17 | Pin 11 | Student Behavior Mode |
| Switch (Center) | — | Pin 9 | Standby (GND) |
| Switch (Right/Down) | GPIO 22 | Pin 15 | Blind Navigation Mode |
| Push Button | GPIO 27 | Pin 13 | "Ask AI" Scene Description |

## Installation

### 1. Setup Hailo Environment

**Update system and install dependencies**
```
sudo apt update && sudo apt install hailo-all espeak-ng mpg123
```

**Clone the official RPi5 examples**
```
git clone https://github.com/hailo-ai/hailo-rpi5-examples.git
cd hailo-rpi5-examples
./install.sh
source setup_env.sh
./download_resources.sh
```

### 2. Setup Local LLM (Ollama)

 **Install Ollama service**
```
curl -fsSL https://ollama.com/install.sh | sh
```
 **Pull the ultra-lightweight Qwen model**
```
ollama pull qwen2:0.5b
pip install ollama
```

# The "Soft Pause" Innovation
**Running Vision pipelines and LLMs simultaneously on a Raspberry Pi 5 can trigger PSU Low Voltage warnings and system instability due to high current draw (4A-5A). To solve this, this project implements a Soft Pause:**

 **1.Trigger:** User presses the "Ask AI" button.
 
 **2.Signal:** The controller creates a temporary flag file at /tmp/hailo_pause.
 
 **3. Throttling:** The vision scripts detect this file and instantly skip heavy CPU tasks like OpenCV color conversion and text drawing.
 
 **4. Inference:** The CPU overhead is cleared, allowing Ollama to process the summary using the filtered logs.
 
 **5. Resume:** Once the AI finishes speaking, the flag is removed and the video feed resumes drawing and processing at full speed.


## How to Run
**1. Navigate to your workspace**
```
cd ~/hailo-rpi5-examples
source setup_env.sh
```
**2. Start the Master Controller**
```
python askaicontroller.py
```
**3. Operation**
**Turn the Rotary Switch** to select a mode (Behavior or Navigation).
**Press the Tactile Button** to hear a natural language scene description.
**Move the switch** to the Center to release the Hailo chip and enter standby.

# Troubleshooting
**Status 74 (Device Busy):** The script includes a 5-second "Nuclear Cleanup" logic. If you switch modes too fast, simply wait for the reset period to finish to allow the PCIe bus to clear.
**Low Voltage Warning:** This is common during the 2-3 seconds of AI inference. The "Soft Pause" logic minimizes this to prevent system reboots.
**Ollama Error:** Ensure the Ollama service is running in the background. If the connection fails, type ollama serve in a separate terminal.

