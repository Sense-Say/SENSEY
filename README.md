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
##

## 📐 Methodology Architecture 

```mermaid
graph TD
    %% Define the single, large system container
    subgraph SYSTEM_CONTAINER ["**Block Diagram**"]
        direction TB
        %% 0. Start
        Z([Start]) -->

        %% 1. Input Flow
        A([User Action]) --> B{Input Type?}
        
        B -->|Toggle Switch| C{Mode Selection?}
        B -->|PushButton-to-Talk| D["Vosk Speech Recognition"]
        D -->|Command Text| RPICPU

        %% 2. Mode Activation & Data Flow
        C -->|Navigation Mode| E["OAK-D Lite Engine (Navigation Data)"]
        C -->|Monitoring Mode| F["Hailo AI HAT+ Engine (Behavior Data)"]
        C -->|Standby Mode| K([End/Idle])
        
        E --> RPICPU
        F --> RPICPU
        
        %% 3. Central Processing & Safety Check
        RPICPU[RPi5 Central Logic] --> H{Obstacle < 1 foot?}

        %% 4. Decision Branches & Output
        
        %% Critical Safety Path - Haptic Only
        H -->|YES| I["Trigger Haptic Feedback"]
        I --> J([Vibration Motors])
        
        %% Normal Operation Path
        H -->|NO| L{Active Mode?}
        
        L -->|Navigation| M["Calculate Path/Turn"]
        L -->|Monitoring| N["Summarize Student Behavior"]
        
        M --> O["eSpeak-NG Audio Engine"]
        N --> O
    end

    %% Connect Outputs to the Final End State
    J --> K
    O --> K

    %% --- Styling for Clarity ---
    style SYSTEM_CONTAINER fill:#fffacd,stroke:#333,stroke-width:4px;
    style H fill:#ffcdd2,stroke:#c62828,stroke-width:2px
    style I fill:#ef9a9a,stroke:#c62828,stroke-width:2px
    style J fill:#ef9a9a,stroke:#c62828,stroke-width:2px
    style L fill:#e3f2fd,stroke:#333,stroke-width:2px
    style M fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style N fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style E fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style F fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style O fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    style RPICPU fill:#bbf,stroke:#333,stroke-width:2px
```


