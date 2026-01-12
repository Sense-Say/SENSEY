This is a comprehensive README.md guide for your GitHub repository. It covers the hardware, software, architecture, and the "Soft Pause" innovation we developed to handle the Raspberry Pi 5’s power constraints.

Vision-Assist: A Hybrid Real-Time & LLM Navigation System

This project is a revolutionary assistive technology for the blind and classroom monitors, built on the Raspberry Pi 5 with the Hailo-8 AI Accelerator.

It utilizes a Hybrid AI Architecture:

Fast Brain (Hailo-8): Handles real-time computer vision (Detection & Pose) at 15-30 FPS.

Smart Brain (Local LLM): Uses Ollama (Qwen2-0.5B) to interpret vision logs and provide natural language summaries on demand.

🚀 Key Features

Blind Navigation Mode: 3-column spatial detection (Left, Center, Right) with object majority-area logic.

Classroom Monitor Mode: Detects student actions (Standing, Walking, Raising Hand) using pose estimation.

"Ask AI" Integration: A physical button that triggers a local Large Language Model to summarize the last 10 lines of system logs into a natural sentence.

Intelligent Resource Management: Includes a "Soft Pause" mechanism that throttles vision CPU usage during AI inference to prevent PSU Low Voltage crashes on the RPi 5.

Tactile-First Interface: Designed for blind users using a 3-way industrial rotary switch and physical buttons.

🛠 Hardware Requirements

Raspberry Pi 5 (8GB recommended)

Raspberry Pi AI Kit (Hailo-8L)

USB Webcam or Raspberry Pi Camera Module 3

3-Way Selector Switch (SPDT Center-Off: MTS-103 or Industrial Rotary)

Momentary Push Button (The "Ask AI" trigger)

Waveshare UPS 3S (or a high-current 5V/5A power supply)

Audio Output: 3.5mm Jack or USB Speaker for Text-to-Speech (TTS).

📂 Project Structure
code
Text
download
content_copy
expand_less
.
├── askaicontroller.py      # Master controller (Handles GPIO, Process Switching, Ollama)
├── detection.py            # Blind Navigation script (Hailo-8 YOLOv8)
├── pose_estimation.py      # Classroom Monitoring script (Hailo-8 Pose)
├── action_logic.py         # Helper for pose action detection
├── audio_files/            # Folder for pre-recorded UI sounds (mp3)
└── README.md
⚙️ Installation
1. Prerequisite Software

Ensure your Raspberry Pi OS (Bookworm 64-bit) is up to date and Hailo software is installed:

code
Bash
download
content_copy
expand_less
sudo apt update && sudo apt install hailo-all espeak-ng mpg123
sudo reboot
2. Setup Hailo Examples

The scripts depend on the hailo-rpi5-examples library:

code
Bash
download
content_copy
expand_less
git clone https://github.com/hailo-ai/hailo-rpi5-examples.git
cd hailo-rpi5-examples
./install.sh
source setup_env.sh
./download_resources.sh
3. Setup Ollama (Local LLM)

Install Ollama and pull the lightweight Qwen model:

code
Bash
download
content_copy
expand_less
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2:0.5b
pip install ollama
🔌 Hardware Wiring
Component	RPi 5 Pin (GPIO)	Physical Pin	Connection
Switch: Mode A (Behavior)	GPIO 17	Pin 11	GND (Middle Pin)
Switch: Mode B (Navigation)	GPIO 22	Pin 15	GND (Middle Pin)
"Ask AI" Button	GPIO 27	Pin 13	GND
🧠 System Logic: "The Soft Pause"

Running a Vision model and a Large Language Model (LLM) simultaneously can exceed the 25W power limit of the RPi 5. This project solves this via the Soft Pause mechanism:

When the Ask AI button is pressed, the Master Controller creates a temporary flag file /tmp/hailo_pause.

The active vision script (detection.py or pose_estimation.py) detects this file and instantly skips CPU-heavy tasks like cv2.cvtColor and cv2.putText.

The CPU overhead is released to Ollama for fast inference (1-3 seconds).

Once the AI finishes speaking, the flag is removed, and high-FPS vision processing resumes automatically.

📖 Usage

Boot the System:

code
Bash
download
content_copy
expand_less
cd /home/raspberrypi/hailo-rpi5-examples
source setup_env.sh
python askaicontroller.py

Switch Mode: Turn the rotary switch Left for Classroom Monitoring or Right for Blind Navigation.

Analyze: At any time, press the Ask AI button. The system will chime "Thinking," pause the UI, and then describe the scene via TTS:

Example (Navigation): "A person is on your left and a chair is directly in front of you."

Example (Behavior): "Three students are present; two are standing and one has their hand raised."

Standby: Move the switch to the Center position to release the Hailo hardware and save power.

⚠️ Troubleshooting

Status 74 (Device Busy): The controller includes a "Nuclear Cleanup" logic. Ensure you wait the 5-second cooldown period between switching modes to allow the PCIe bus to reset.

Low Voltage Warning: If the warning persists, ensure you are using high-discharge 18650 batteries in your UPS. The "Soft Pause" logic is designed to minimize this.

ModuleNotFoundError: Ensure you are running the scripts inside the Hailo Virtual Environment (source setup_env.sh).

📜 Credits

Developed for the Raspberry Pi 5 AI Hat.

Uses Hailo-8L for hardware acceleration.

Local LLM powered by Ollama.
