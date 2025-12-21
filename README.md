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
