import os
import subprocess
import sys

def run_cmd(cmd):
    print(f"🚀 Executing: {cmd}")
    # We use list format here to avoid shell redirection errors with < or >
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e}")

def main():
    print("🌟 SENSEY COMPREHENSIVE SETUP ORCHESTRATOR 🌟")
    print("---------------------------------------------")

    # 1. SYSTEM UPDATES & APT PACKAGES
    # We ask the user to ensure no other update process is running
    print("\n📦 Installing System Dependencies (Apt)...")
    apt_cmd = (
        "sudo apt update && sudo apt install -y alsa-utils mpg123 flac build-essential "
        "cmake pkg-config libjpeg-dev libpng-dev libtiff-dev libavcodec-dev "
        "libavformat-dev libswscale-dev libv4l-dev libxvidcore-dev libx264-dev "
        "libgtk-3-dev python3-pip python3-pil python3-pil.imagetk"
    )
    run_cmd(apt_cmd)

    # 2. CREATE DIRECTORY STRUCTURE
    print("\n📂 Creating SENSEY folder structure...")
    base_dir = "/home/raspberrypi/Student Monitoring"
    audio_dir = "/home/raspberrypi/TTS-STT-AUDIO"
    piper_dir = f"{audio_dir}/piper"
    
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(piper_dir, exist_ok=True)

    # 3. INSTALL PYTHON LIBRARIES
    print("\n📦 Installing Python Libraries (Pip)...")
    # 🚀 FIX: Added quotes around libraries with < or = symbols
    pip_libs = [
        "'numpy<2.0'",
        "'opencv-python<=4.10.0.84'",
        "depthai==2.32.0.0",
        "face_recognition",
        "customtkinter",
        "Pillow",
        "imutils",
        "gpiozero",
        "rpi.gpio",
        "gTTS",
        "playsound==1.2.2",
        "python-dotenv",
        "PyYAML",
        "blobconverter"
    ]
    run_cmd(f"{sys.executable} -m pip install " + " ".join(pip_libs))

    # 4. DOWNLOAD PIPER TTS
    print("\n🔊 Downloading Piper TTS Binary to TTS-STT-AUDIO...")
    if not os.path.exists(f"{piper_dir}/piper"):
        os.chdir(piper_dir)
        run_cmd("wget https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_arm64.tar.gz")
        run_cmd("tar -xf piper_arm64.tar.gz --strip-components=1")
        run_cmd("chmod +x piper")
        run_cmd("rm piper_arm64.tar.gz")
    
    print("\n🗣️ Downloading Piper Voice Model...")
    if not os.path.exists(f"{audio_dir}/en_US-lessac-medium.onnx"):
        os.chdir(audio_dir)
        run_cmd("wget https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-en-us-lessac-medium.tar.gz")
        run_cmd("tar -xf voice-en-us-lessac-medium.tar.gz")
        run_cmd("rm voice-en-us-lessac-medium.tar.gz")

    # 5. DOWNLOAD OAK-D FACE DETECTION BLOB
    print("\n👁️ Downloading OAK-D Face Detector Blob...")
    if not os.path.exists(f"{audio_dir}/fast_face.blob"):
        run_cmd(f"{sys.executable} -m blobconverter --zoo-name face-detection-retail-0004 --shaves 3 --version 2021.4 --output_dir '{audio_dir}'")
        for f in os.listdir(audio_dir):
            if "face-detection-retail-0004" in f and f.endswith(".blob"):
                run_cmd(f"mv '{audio_dir}/{f}' '{audio_dir}/fast_face.blob'")

    print("\n" + "="*45)
    print("✅ SENSEY INITIALIZATION COMPLETE!")
    print(f"📁 Logic Path:  {base_dir}")
    print(f"📁 Audio Path:  {audio_dir}")
    print(f"🔊 Piper EXE:   {piper_dir}/piper")
    print("="*45)

if __name__ == "__main__":
    main()