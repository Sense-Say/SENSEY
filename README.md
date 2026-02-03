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
    style SYSTEM_CONTAINER fill:#fffacd,stroke:#333,stroke-width:1px;
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

---
This is the complete, professional `README.md` guide incorporating all the finalized logic, hardware roles, and design decisions we made, specifically using Markdown tables for clean visualization.

***

# 🧠 Eye-Link Assistant: Fused AI Navigation & Monitoring

This project details the architecture for a real-time assistive device for blind teachers, integrating the specialized power of the **OAK-D Lite** (for 3D Vision) and the **Hailo AI HAT+** (for high-speed behavior monitoring) on a single **Raspberry Pi 5**.

## I. SYSTEM ARCHITECTURE & CONTROL

The system is managed via a physical **3-Mode Toggle Switch** for clear, tactile state management.

| Mode | Hardware Focus | Primary Function | Audio Control / Trigger |
| :--- | :--- | :--- | :--- |
| **1. NAVIGATION** | **OAK-D Lite** (VIO, Depth) | Guiding the teacher (walking) via an audio compass and obstacle avoidance. | **Auto-Pilot:** Speaks only when an obstacle is detected or a turn is needed. |
| **2. STANDBY (MODE 2)** | **ALL AI INACTIVE** | Power saving. Used during lecturing/sitting to ensure complete silence. | **SILENCE.** |
| **3. MONITORING**| **Hailo AI HAT+** (Pose) | Tracking student behavior (hands, sleeping, cheating). | **ON-DEMAND:** Speaks only when the **Push-to-Talk button** is clicked. |

---

## II. SENSOR FUSION: The 3D 'Kinect' Data Model

The core innovation is fusing the data from the two separate AI chips into a reliable 3D coordinate (`X, Y, Z`) model, which is essential for accurate behavior analysis.

| Data Source | Data Provided | RPi5 Logic | Final Output (Use Case) |
| :--- | :--- | :--- | :--- |
| **Hailo AI HAT+** | `X, Y` Pixel Coordinates (2D Pose) | Provides the **lookup address** for the depth value. | *e.g., Nose is at pixel* |
| **OAK-D Lite** | `Z` Depth Map (mm) | Provides the **distance value** at the specified pixel location. | *e.g., Z-Depth at is 2100mm.* |
| **Final Fusion** | **X, Y, Z (3D Point)** | **Kinect Logic:** Runs geometry on the full 3D coordinate system. | *e.g., **`Z_Nose`** is closer than **`Z_Shoulder`** (Student is aggressively leaning).* |

---

## III. NAVIGATION ENGINE LOGIC (Mode 1)

The system uses a rigid, redundant framework to ensure the teacher is always aware of their location and immediate threats.

| System Aspect | Implementation Details | Key Geometric Rule |
| :--- | :--- | :--- |
| **Pathing** | **VIO (Visual Inertial Odometry):** Tracks movement for "Clew-like" path recording and retracing. | Distance measured in millimeters via OAK-D Stereo. |
| **Compass** | **8-Point ArUco Tags** (N, NE, S, SE, etc.) | Provides stable, magnetic-immune anchors. Python calculates `Target_Angle - Current_Angle`. |
| **Obstacle Avoidance** | **3-Zone Logic (L/C/R) + Depth:** OAK-D classifies obstacles by distance and position. | **Center (1m-2m):** *"Obstacle Center. Drift Right."*<br>**Critical (<1ft):** **Haptic Vibration** + *"STOP."* |

---

## IV. MONITORING ENGINE LOGIC (Mode 3)

For a blind teacher, the most valuable behaviors are those that affect **classroom management, engagement, and safety.
##

### 1. The Collaborative/Peer-Cheating Pose (High Value)

**Goal:** Detect unauthorized communication or peer-to-peer visual cheating. This is distinct from simple leaning.

| Behavior | Logic / Rationale | Target (Action) |
| :--- | :--- | :--- |
| **Huddle/Head-Proximity** | **`Distance(Nose_Student_A, Nose_Student_B) < Shoulder_Width * 1.5`** | Two students' heads are abnormally close together (1.5 times the width of a single shoulder width). This is a strong signal for whispering or looking at the same paper. |
| **Writing Sharing** | **`Distance(Wrist_A, Wrist_B) < Hip_Width`** | Two students' wrists are close together and near the desk surface. This is a clear signal that they are touching or looking at the same writing surface. |
| **Teacher Feedback:** *"Heads huddled on the right."* |

### 2. The Boredom / Disinterest Pose (Engagement Management)

**Goal:** Detect a student who is bored and no longer interacting with the lesson. This is different from sleeping.

| Behavior | Logic / Rationale | Target (Action) |
| :--- | :--- | :--- |
| **Head-on-Shoulder** | **`Distance(Nose, Elbow) < Shoulder_Width * 0.5`** **AND** **`Y_Elbow > Y_Nose`** | The student is bracing their head with their elbow on the desk. The elbow is higher than the nose. This is a classic "I'm bored" pose, distinct from resting on the hands. |
| **Crossed Arms** | **`Distance(Wrist_L, Wrist_R)` is minimal AND `Y_Shoulder` is far from `Y_Hip`** | The wrists are close together, but the torso is upright. This is the posture of a student who has "checked out" but is not asleep. |
| **Teacher Feedback:** *"One student is bracing their head with their arm."* |

### 3. The "Searching/Looking Away" Pose (Focus Management)

**Goal:** Detect students who are looking at the clock, out the window, or at their phone in their lap.

| Behavior | Logic / Rationale | Target (Action) |
| :--- | :--- | :--- |
| **Head Down (Phone Use)** | **`Y_Nose` is far below `Y_Shoulder` AND `Y_Nose` is near `Y_Hip`** | The student's head is tilted straight down (as if looking at a phone in their lap). The vertical distance between the head and the shoulder is large. |
| **Sideways Twist** | **`Angle(Shoulder-Hip-Knee)` is far from 180 degrees** | The torso is twisted out of alignment with the hips, indicating the student is completely turned around in their seat. |
| **Teacher Feedback:** *"Student is looking down intensely."* |

### 4. The Safety/Physical Discomfort Pose (Crucial for Public Schools)

**Goal:** Detect students who may be in discomfort and need attention, especially valuable since the teacher cannot visually check.

| Behavior | Logic / Rationale | Target (Action) |
| :--- | :--- | :--- |
| **Stomach/Chest Clutch** | **`Distance(Wrist_L, Avg_Hip) < Hip_Width * 0.5`** **AND** **`Distance(Wrist_R, Avg_Hip) < Hip_Width * 0.5`** | Both wrists are pulled down and held tightly near the abdominal area. This is a very strong signal of pain or discomfort. |
| **Head-in-Hands/Exhaustion** | **`Y_Elbow` is low AND `Y_Wrist` covers `Y_Eye/Nose`** | The student's head is completely enveloped by their hands. This is a high-level distress/exhaustion signal. |
| **Teacher Feedback:** *"Student in the back is clutching their stomach area."* |

---

### Summary of Benefits

These four categories provide the teacher with **actionable intelligence** that requires a response:

*   **P1 Safety:** *Heads Huddled* or *Stomach Clutch*
*   **P2 Engagement:** *Hand Raise* or *Boredom Bracing*

By focusing on these geometrically distinct poses, you minimize false alarms from simple reading and writing.

### The Non-LLM Behavior Summarizer

| Trigger | Logic | Example Audio Output |
| :--- | :--- | :--- |
| **Teacher Clicks Button** | System counts events in the buffer and fills a pre-written **Template** (no AI generation). | *"Two students have questions, and one student is sleeping."* |
| **Safety Breach (Auto)** | **Cheating/Suspicious Activity** detected. | *"ALERT! Student looking sideways on the right."* (Interrupts immediately). |
