# SENSEY: An Intelligent Wearable Aid with Real-Time Object Detection and Multimodal Feedback for Inclusive Education

Welcome to the repository for **SENSEY**! This project is dedicated to developing an intelligent wearable aid designed to empower visually impaired teachers in inclusive education settings. SENSEY leverages cutting-edge AI-driven computer vision, specifically YOLOv8, combined with multimodal haptic and audio feedback to enhance classroom mobility, object identification, student interaction, and overall spatial awareness.

Our goal is to create a robust and efficient system that bridges the existing gaps in assistive technology, providing real-time, adaptive support for educators.

---

## ✨ Features & Project Components

This repository is structured to provide clear access to the various modules and functionalities that comprise the SENSEY wearable aid and its underlying AI infrastructure.

*   **Blind Navigation:**
    *   This core module implements the navigation logic and processes sensory data to provide guidance for visually impaired users. It integrates outputs from perception models to offer intuitive feedback.

*   **Depth Estimation Model:**
    *   Dedicated to 3D scene understanding, this component includes models and code for estimating the depth of objects using a stereo camera. It's crucial for simulating "Human Binocular Vision" and understanding obstacle distances in the environment.

*   **Face Recognition Folder:**
    *   Focuses on the facial identification capabilities essential for SENSEY. This includes code and notes for recognizing students within the classroom environment, supporting enhanced teacher-student interaction.

*   **Hardware:**
    *   Contains detailed documentation, design files (e.g., 3D CAD for mounting cases), and setup instructions for the physical components of the SENSEY wearable device, including the Raspberry Pi 5 enclosure, stereo camera mount, and battery holder.

*   **Ollama AI for summarizing the terminal prompt:**
    *   *(Note: This component appears to be a general AI development tool for enhancing developer workflow, rather than a direct feature of the SENSEY wearable aid. It's included here as part of the broader repository's AI solutions.)* Explores integrating Ollama AI for terminal output summarization.

*   **Pose Estimation Model:**
    *   Documents the development and initial progress of the pose estimation module. This is vital for detecting and tracking student behaviors and actions in real-time within the classroom.

*   **Text to Speech Folder:**
    *   Implements the text-to-speech functionalities that drive SENSEY's audio feedback system, allowing the device to provide clear, audible information to the user.

*   **WaveShare UPS Module 3S:**
    *   Manages the integration and functionality of the WaveShare UPS Module 3S, ensuring reliable power supply and extended operational time for the portable SENSEY device.

*   **README.md:**
    *   (You are currently reading this file!) Provides a comprehensive overview of the SENSEY project, its features, and guidance for development and contribution.

*   **Raspberry Pi5 AI HAT + Hailo installation notes:**
    *   Contains essential notes and guides for setting up the Raspberry Pi 5 with an AI HAT, specifically optimized for Hailo AI accelerators to ensure efficient on-device inference for SENSEY's various AI models.

---

## 🚀 Getting Started

To get a local copy of SENSEY's development environment and explore its components, follow these steps:

1.  Clone the repository: `git clone https://github.com/Sense-Say/SENSEY.git`
2.  Navigate to the specific module you wish to explore (e.g., `cd Depth Estimation Model`).
3.  Refer to the `README.md` files within individual folders or the `Hardware` folder for detailed setup, installation, and usage instructions for each component.

---

## 🛠️ Technologies & Tools

The SENSEY project leverages a diverse stack of technologies and tools:

*   **Core AI:** YOLOv8 (for object detection, pose estimation, face recognition)
*   **AI Accelerators:** Hailo AI HAT (on Raspberry Pi 5)
*   **Embedded Computing:** Raspberry Pi 5
*   **Camera System:** Stereo Camera (e.g., RealSense D435)
*   **Haptic Feedback:** Custom ESD Arm Sleeve with Coin Vibration Motors
*   **Audio Feedback:** Shokz OPENMOVE Bone Conduction Headphones (Text-to-Speech)
*   **Power Management:** WaveShare UPS Module 3S
*   **Development & Training:**
    *   Python
    *   Ultralytics YOLO Framework
    *   Roboflow (Dataset management)
    *   Google Colab (GPU-accelerated training)
    *   OpenCV (Image and video processing)
*   **Other AI Tools (within repository):** Ollama AI (for development utilities)

---

## 🤝 Contributing

We welcome contributions to the SENSEY project! If you have suggestions for improvements, new features, or want to report issues, please feel free to:

1.  Fork the repository.
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

---

## 📞 Contact

**Project Team:** Buco, Dogillo, Dorongon, Padre, Villariña

**Adviser:** Engr. Dennis Jefferson A. Amora, PECE, LPT

Project Link: `https://github.com/Sense-Say/SENSEY`

---


# 💫 About Me:
An aspiring Electronics Engineer


## 🌐 Socials:
[![Facebook](https://img.shields.io/badge/Facebook-%231877F2.svg?logo=Facebook&logoColor=white)](https://facebook.com/1) [![Instagram](https://img.shields.io/badge/Instagram-%23E4405F.svg?logo=Instagram&logoColor=white)](https://instagram.com/2) [![LinkedIn](https://img.shields.io/badge/LinkedIn-%230077B5.svg?logo=linkedin&logoColor=white)](https://linkedin.com/in/3) [![Reddit](https://img.shields.io/badge/Reddit-%23FF4500.svg?logo=Reddit&logoColor=white)](https://reddit.com/user/4) [![email](https://img.shields.io/badge/Email-D14836?logo=gmail&logoColor=white)](mailto:5) 

# 💻 Tech Stack:
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54) ![Bash Script](https://img.shields.io/badge/bash_script-%23121011.svg?style=for-the-badge&logo=gnu-bash&logoColor=white) ![Adobe Acrobat Reader](https://img.shields.io/badge/Adobe%20Acrobat%20Reader-EC1C24.svg?style=for-the-badge&logo=Adobe%20Acrobat%20Reader&logoColor=white) ![Canva](https://img.shields.io/badge/Canva-%2300C4CC.svg?style=for-the-badge&logo=Canva&logoColor=white) ![PyTorch](https://img.shields.io/badge/PyTorch-%23EE4C2C.svg?style=for-the-badge&logo=PyTorch&logoColor=white) ![NumPy](https://img.shields.io/badge/numpy-%23013243.svg?style=for-the-badge&logo=numpy&logoColor=white) ![GitHub](https://img.shields.io/badge/github-%23121011.svg?style=for-the-badge&logo=github&logoColor=white) ![Cisco](https://img.shields.io/badge/cisco-%23049fd9.svg?style=for-the-badge&logo=cisco&logoColor=black) ![Portfolio](https://img.shields.io/badge/Portfolio-%23000000.svg?style=for-the-badge&logo=firefox&logoColor=#FF7139) ![Raspberry Pi](https://img.shields.io/badge/-Raspberry_Pi-C51A4A?style=for-the-badge&logo=Raspberry-Pi) ![OpenGL](https://img.shields.io/badge/OpenGL-white?logo=OpenGL&style=for-the-badge)
# 📊 GitHub Stats:
![](https://github-readme-stats.vercel.app/api?username=edi.ward&theme=calm&hide_border=true&include_all_commits=false&count_private=false)<br/>
![](https://nirzak-streak-stats.vercel.app/?user=edi.ward&theme=calm&hide_border=true)<br/>
![](https://github-readme-stats.vercel.app/api/top-langs/?username=edi.ward&theme=calm&hide_border=true&include_all_commits=false&count_private=false&layout=compact)

## 🏆 GitHub Trophies
![](https://github-profile-trophy.vercel.app/?username=edi.ward&theme=radical&no-frame=false&no-bg=true&margin-w=4)

### ✍️ Random Dev Quote
![](https://quotes-github-readme.vercel.app/api?type=horizontal&theme=radical)

### 🔝 Top Contributed Repo
![](https://github-contributor-stats.vercel.app/api?username=edi.ward&limit=5&theme=dark&combine_all_yearly_contributions=true)

---
[![](https://visitcount.itsvg.in/api?id=edi.ward&icon=0&color=0)](https://visitcount.itsvg.in)

<!-- Proudly created with GPRM ( https://gprm.itsvg.in ) -->
