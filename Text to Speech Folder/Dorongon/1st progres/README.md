
***

# 🇵🇭 Multi-Mode AI Assistant (RPi 5 + Hailo-8)

A dual-purpose AI system running on **Raspberry Pi 5** with the **Hailo-8** AI accelerator. This system is designed for accessibility and monitoring with a localized Filipino touch.

### Key Features
1.  **Blind Navigation Mode:** Object detection with real-time Filipino voice feedback to assist visually impaired users.
2.  **Student Behavior Monitor:** High-performance pose estimation detecting actions such as "Raising Hand", "Walking", and "Standing".

---

## 🛠️ Hardware Requirements
- **Raspberry Pi 5** (8GB Recommended)
- **Official 27W USB-C Power Supply** (Critical for Hailo-8 performance)
- **Hailo-8 / Hailo-8L M.2 HAT**
- **USB Camera** or RPi Camera Module (CSI)
- **Speaker / Headphones** (Connected via 3.5mm Jack or USB)

---

## 💿 Phase 1: OS Installation (Critical)
**Warning:** Do not use the default "latest" OS. This project relies on specific driver compatibility found in the Legacy Bookworm release.

1.  Open **Raspberry Pi Imager**.
2.  **Device:** Raspberry Pi 5.
3.  **OS:** `Raspberry Pi OS (Legacy, 64-bit) Bookworm`.
    - *Note:* Do NOT select Trixie or "Testing" versions.
4.  Flash to SD Card and boot.

---

## ⚙️ Phase 2: System Setup

Run these commands in the terminal block by block.

### 1. Update & PCIe Configuration
```bash
sudo apt update && sudo apt full-upgrade -y
sudo raspi-config
```
*   Navigate to: **6 Advanced Options** -> **A8 PCIe Speed** -> Select **Yes** (Enable Gen 3).
*   **Finish and Reboot.**

### 2. Install Hailo Drivers
```bash
sudo apt install hailo-all -y
sudo reboot
```

### 3. Install Hailo Infrastructure
```bash
git clone https://github.com/hailo-ai/hailo-apps-infra.git
cd hailo-apps-infra
./install.sh
```

### 4. Install Project Dependencies
```bash
# System Audio Engines
sudo apt install espeak-ng mpg123 -y

# Python Libraries
pip3 install pyttsx3 gTTS opencv-python --break-system-packages
```

---

## 📂 Phase 3: File Placement Map
The system expects a specific directory structure. Ensure your files are moved to the locations below:

### Visual File Tree
```text
/home/raspberrypi/
├── keyboard_controller.py
├── generate_voice.py
├── audio_files/               # Generated automatically in Phase 4
└── Downloads/
    ├── STANDING.MOV           # Your test video
    └── pose estimation/       # Ensure the space is in the folder name
        └── action_logic.py
```

### Core Script Overwrites
Replace the default Hailo scripts with your modified versions:

1.  **Behavior Script:**
    - *Destination:* `/home/raspberrypi/hailo-apps-infra/hailo_apps/hailo_app_python/apps/pose_estimation/pose_estimation.py`
2.  **Blind Nav Script:**
    - *Destination:* `/home/raspberrypi/hailo-apps-infra/hailo_apps/hailo_app_python/apps/detection/detection.py`

---

## 🎙️ Phase 4: Voice Initialization
Before running the system, generate the Filipino voice assets. **Requires Internet Connection.**

```bash
cd ~
python3 generate_voice.py
```
*Verification:* A folder named `audio_files` should appear in your home directory containing several `.mp3` files.

---

## 🚀 Phase 5: Usage

1.  **Audio Setup:** Connect your Speaker/Headphones to the 3.5mm jack.
2.  **Run Master Controller:**
```bash
cd ~
python3 keyboard_controller.py
```

### 🎮 Controls
| Key | Action | Voice Feedback (Filipino) |
| :--- | :--- | :--- |
| **1** | Start Behavior Monitor | "Mode ng Pag-uugali ng Estudyante, Aktibo na." |
| **2** | Start Blind Navigation | "Mode ng Nabigasyon para sa Bulag, Aktibo na." |
| **s** | Stop / Standby | "Naka-standby ang sistema." |
| **q** | Quit Program | "Paalam. Nag-sha-shut down na." |

---

## 🔧 Troubleshooting

- **Error: `action_logic.py` missing**
  - Check the path: `/home/raspberrypi/Downloads/pose estimation/`. Linux is case-sensitive and the space in the folder name must exist.
- **No Audio / Silent:**
  - Right-click the **Volume icon** on the Taskbar -> Select Output Device -> **AV Jack**.
  - Ensure `mpg123` is installed: `sudo apt install mpg123`.
- **Window Not Opening (Display Issues):**
  - The scripts use `os.environ["QT_QPA_PLATFORM"] = "xcb"`. If issues persist, ensure you are not running the Pi via Wayland (Bookworm Legacy uses X11 by default, which is required for these CV windows).
- **Video Playback Speed:**
  - Use the `--sync` flag in the terminal commands if the video plays too fast. The `keyboard_controller.py` handles this by default.
