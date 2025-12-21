# 🇵🇭 Multi-Mode AI Assistant (RPi 5 + Hailo-8)

A dual-purpose AI system running on Raspberry Pi 5 with the Hailo-8 accelerator.
1.  **Blind Navigation Mode:** Object detection with Filipino voice feedback.
2.  **Student Behavior Monitor:** Pose estimation detecting "Raising Hand", "Walking", and "Standing" with custom visuals.

---

## 🛠️ Hardware Requirements
*   **Raspberry Pi 5** (8GB Recommended)
*   **Official 27W USB-C Power Supply** (Critical for performance)
*   **Hailo-8 / Hailo-8L M.2 HAT**
*   **USB Camera** or RPi Camera Module
*   **Speaker / Headphones** (3.5mm Jack)

---

## 💿 Phase 1: OS Installation (Critical)
**Do not use the latest default OS.** This project requires specific drivers.

1.  Open **Raspberry Pi Imager**.
2.  Select Device: **Raspberry Pi 5**.
3.  Select OS: **Raspberry Pi OS (Legacy, 64-bit) Bookworm**.
    *   *Warning:* Do NOT select Trixie or "Testing".
4.  Flash to SD Card and boot up.

---

## ⚙️ Phase 2: System Setup

Open the Terminal on your Raspberry Pi and run these commands block by block.

### 1. Update & Config
```bash
sudo apt update && sudo apt full-upgrade -y
sudo raspi-config
# Navigate to: 6 Advanced Options -> A8 PCIe Speed -> Select "Yes" (Gen 3).
# Finish and Reboot.


### 2. Install Hailo Drivers
Open the terminal and install the official drivers (requires reboot).
sudo apt install hailo-all -y
sudo reboot

## 3. Install Hailo Infrastructure
Download the official GStreamer pipeline tools provided by Hailo.
git clone https://github.com/hailo-ai/hailo-apps-infra.git
cd hailo-apps-infra
./install.sh

## 4. Install Project Dependencies
We need specific audio engines and Python libraries for the Filipino voice and logic.
# System Audio Engines
sudo apt install espeak-ng mpg123 -y

# Python Libraries
pip3 install pyttsx3 gTTS opencv-python --break-system-packages


## 📂 Phase 3: File Placement Map
This project requires specific files to be in specific locations.

## 1. Home Directory (/home/raspberrypi/)
Place the following controller scripts here:
keyboard_controller.py
generate_voice.py

## 2. Logic & Media Folder
Create the specific folder structure required by the logic script:
mkdir -p "/home/raspberrypi/Downloads/pose estimation"
Move action_logic.py inside: /home/raspberrypi/Downloads/pose estimation/
Move the test video STANDING.MOV inside: /home/raspberrypi/Downloads/


## 3. Overwriting Hailo Apps
Replace the default Hailo scripts with your modified versions.
Behavior Script:
Source: Your modified pose_estimation.py
Destination: /home/raspberrypi/hailo-apps-infra/hailo_apps/hailo_app_python/apps/pose_estimation/pose_estimation.py
Blind Nav Script:
Source: Your modified detection.py
Destination: /home/raspberrypi/hailo-apps-infra/hailo_apps/hailo_app_python/apps/detection/detection.py


## 🎙️ Phase 4: Initialization (Voice Identity)
Run this command once (requires Internet connection) to generate the Filipino voice assets using Google TTS.

cd ~
python3 generate_voice.py
Verification: A folder named audio_files should appear in your home directory containing .mp3 files.

## 🚀 Phase 5: Usage
Audio: Connect your Speaker or Headphones to the Raspberry Pi 3.5mm jack.
Run: Execute the Master Controller.
cd ~
python3 keyboard_controller.py

## 🎮 Controls
Key	Action	Voice Feedback (Filipino)
1	Start Behavior Monitor	"Mode ng Pag-uugali ng Estudyante, Aktibo na."
2	Start Blind Navigation	"Mode ng Nabigasyon para sa Bulag, Aktibo na."
s	Stop / Standby	"Naka-standby ang sistema."
q	Quit Program	"Paalam. Nag-sha-shut down na."

## 🔧 Troubleshooting
Error: action_logic.py missing
Ensure the folder /home/raspberrypi/Downloads/pose estimation exists (note the space) and the file is inside it.
No Audio / Silent:
Right-click the Volume icon on the RPi desktop.
Select Output Device -> AV Jack (Headphones).
Ensure mpg123 is installed (sudo apt install mpg123).
Black Screen / Window Not Opening:
The scripts include os.environ["QT_QPA_PLATFORM"] = "xcb" to fix Raspberry Pi 5 display issues automatically.
Ensure you are using the --sync flag (default in the controller) when running video files.
