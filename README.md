Here is the Field Deployment Guide.

This guide is written so that anyone can take your files, install the necessary software on a fresh Raspberry Pi 5, and get your project running exactly as you have it, without guessing.

📋 Project Installation & Deployment Guide

System: Raspberry Pi 5 + Hailo-8/8L AI HAT
Function: Multi-mode AI Assistant (Blind Navigation & Student Behavior Monitor) with Filipino Voice Identity.

🟢 Part 1: OS & Driver Setup (Crucial)

If this part is wrong, the AI will not load.

Flash the SD Card:

Use Raspberry Pi Imager.

Device: Raspberry Pi 5.

OS: Select Raspberry Pi OS (Legacy, 64-bit) Bookworm.

⚠️ WARNING: Do NOT use "Trixie", "Testing", or the latest default if it has moved past Bookworm. The Hailo drivers are specific to the Kernel.

Initial Terminal Setup:
Open terminal and run:

code
Bash
download
content_copy
expand_less
sudo apt update && sudo apt full-upgrade -y
sudo raspi-config
# Go to: 6 Advanced Options -> A8 PCIe Speed -> Choose "Yes" (Gen 3).
# Finish and Reboot.

Install Hailo Drivers:

code
Bash
download
content_copy
expand_less
sudo apt install hailo-all -y
# Reboot again after this finishes.

Install Hailo Infrastructure:
This downloads the GStreamer pipeline tools.

code
Bash
download
content_copy
expand_less
git clone https://github.com/hailo-ai/hailo-apps-infra.git
cd hailo-apps-infra
./install.sh
🟡 Part 2: Install Project Dependencies

These are required for your Audio, Logic, and Keyboard Control.

System Audio Engines:

code
Bash
download
content_copy
expand_less
sudo apt install espeak-ng mpg123 -y

Python Libraries:
Install these globally (using break-system-packages is acceptable for this dedicated device).

code
Bash
download
content_copy
expand_less
pip3 install pyttsx3 gTTS opencv-python --break-system-packages
🟠 Part 3: File Placement (The Map)

You must place your custom files in these EXACT locations, or the code will crash.

1. Create the Logic Directory

Your code specifically looks in the Downloads folder for the logic.

code
Bash
download
content_copy
expand_less
mkdir -p "/home/raspberrypi/Downloads/pose estimation"

Action: Copy your action_logic.py file into this folder.

2. Overwrite the Hailo Apps

You are replacing the default Hailo demo scripts with your custom ones.

Source: Your pose_estimation.py

Destination: /home/raspberrypi/hailo-apps-infra/hailo_apps/hailo_app_python/apps/pose_estimation/pose_estimation.py
(Overwrite the existing file)

Source: Your detection.py

Destination: /home/raspberrypi/hailo-apps-infra/hailo_apps/hailo_app_python/apps/detection/detection.py
(Overwrite the existing file)

3. Place the Controllers

Source: keyboard_controller.py and generate_voice.py

Destination: Place these directly in /home/raspberrypi/ (The Home folder).

🔵 Part 4: Model & Media Setup

Download/Verify AI Models:
Ensure the .hef files exist. Usually, running the infra script downloads them, but verify:

/home/raspberrypi/hailo-apps-infra/resources/models/hailo8/yolov8m.hef

/home/raspberrypi/hailo-apps-infra/resources/models/hailo8/yolov8m_pose.hef

Place the Video File:
Your behavior mode uses a specific video test file.

File: STANDING.MOV

Location: /home/raspberrypi/Downloads/STANDING.MOV

🟣 Part 5: Initialization (The Identity)

Run this once to generate the Filipino voice assets. You must be connected to the internet for this step.

code
Bash
download
content_copy
expand_less
cd ~
python3 generate_voice.py

Check: Ensure a folder named audio_files appeared in your home directory containing .mp3 files.

🚀 Part 6: How to Run

This is the only step the user needs to do daily.

Connect Audio: Plug in headphones/speaker.

Run Controller:

code
Bash
download
content_copy
expand_less
cd ~
python3 keyboard_controller.py

Controls:

Press 1 + Enter: Starts Behavior Monitor (Filipino Voice: "Mode ng Pag-uugali...").

Press 2 + Enter: Starts Blind Navigation (Filipino Voice: "Mode ng Nabigasyon...").

Press s + Enter: Stops AI (Standby).

Press q + Enter: Quits the controller.

🔧 Troubleshooting Tips for New Users

Error: action_logic.py missing

Fix: You did not create the folder in Part 3, Step 1 correctly. Check the spelling of "pose estimation" (space included).

Error: qt.qpa.plugin: Could not find the Qt platform plugin "xcb"

Fix: This usually means you are on RPi 5 Wayland. The code includes os.environ["QT_QPA_PLATFORM"] = "xcb" to fix this automatically. If it persists, run sudo apt install libxcb-cursor0.

No Audio?

Fix: Right-click the Volume icon on the RPi desktop and ensure the Output Device is set to AV Jack (Headphones) and not HDMI.
