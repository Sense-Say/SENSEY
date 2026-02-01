graph TD

    %% USER INPUTS
    subgraph INPUTS [1. USER INTERFACE]
        T[Toggle Switch] -->|Selects Mode| LOGIC
        B[Push Button] -->|Trigger Summary/Path| LOGIC
        M[USB Mic] -->|Voice Command| VOSK[Vosk Speech Recog]
        VOSK --> LOGIC
    end

    %% HARDWARE SENSORS
    subgraph SENSORS [2. SENSORY HARDWARE]
        OAK[OAK-D Lite Camera]
    end

    %% AI PROCESSING
    subgraph AI [3. EDGE AI ENGINES]
        OAK -->|RGB + Depth + IMU| VPU[OAK-D VPU]
        OAK -->|RGB Stream| NPU[Hailo AI HAT+ NPU]
        
        VPU -->|Nav Mode: VIO + ArUco + Obstacles| LOGIC
        NPU -->|Monitor Mode: Pose + Hands + Sleep| LOGIC
    end

    %% RPi5 LOGIC
    subgraph RPI [4. RASPBERRY PI 5 CPU LOGIC]
        LOGIC{Central Controller}
        LOGIC --> SAFETY[Safety Override < 1m]
        LOGIC --> PATH[VIO Path Calculator]
        LOGIC --> SUMM[Behavior Summarizer]
    end

    %% AUDIO OUTPUT
    subgraph OUTPUT [5. FEEDBACK]
        SAFETY -->|Priority 1| AUDIO[eSpeak Audio Engine]
        PATH -->|Priority 2| AUDIO
        SUMM -->|Priority 3| AUDIO
        AUDIO --> EAR[Bone Conduction Headphones]
    end

    %% Styling
    style SAFETY fill:#ff9999,stroke:#cc0000,stroke-width:2px;
    style LOGIC fill:#bbf,stroke:#333,stroke-width:2px;
