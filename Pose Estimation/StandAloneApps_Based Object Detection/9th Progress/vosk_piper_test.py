import vosk
from vosk import Model, KaldiRecognizer
import sounddevice as sd
import json
import sys
import os
import numpy as np
import subprocess
import threading
import time

# --- CONFIGURATION ---
MODEL_PATH = "/home/raspberrypi/Downloads/vosk-model-en-us-0.22-lgraph"
PIPER_EXE = "/home/raspberrypi/Documents/piper/piper"
PIPER_MODEL = "/home/raspberrypi/Documents/piper/en_US-lessac-medium.onnx"
VOSK_RATE = 16000

# --- STATE CONTROL ---
is_speaking = False  # 🚀 LOCK: Stops the mic from hearing the speaker

ALLOWED_WORDS = [
    "record", "finish", "go", "to", "point", "saved", 
    "front", "back", "door", "desk", "window", "stop",
    "left", "right", "center", "navigate", "start", "[unk]"
]

def speak_offline(text):
    """Uses Piper to speak and mutes the ear while talking."""
    global is_speaking
    if not text.strip(): return

    is_speaking = True # 🔒 Lock the 'Ear'
    print(f"\n🔊 Speaking: {text}")
    
    # We pipe Piper directly to aplay
    command = f'echo "{text}" | {PIPER_EXE} --model {PIPER_MODEL} --output_raw | aplay -r 22050 -f S16_LE -t raw'
    
    try:
        subprocess.run(command, shell=True, check=True)
    except Exception as e:
        print(f"❌ Piper Error: {e}")
    
    # Small pause to allow room echoes to die down
    time.sleep(0.2) 
    is_speaking = False # 🔓 Unlock the 'Ear'

def get_usb_mic_info():
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if "USB" in dev['name'] and dev['max_input_channels'] > 0:
            return i, int(dev['default_samplerate'])
    return None, None

def run_system():
    global is_speaking
    if not os.path.exists(MODEL_PATH): return
    
    print("⏳ Loading Models...")
    model = Model(MODEL_PATH)
    rec = KaldiRecognizer(model, VOSK_RATE, json.dumps(ALLOWED_WORDS))

    mic_idx, native_rate = get_usb_mic_info()
    if mic_idx is None: return
    
    speak_offline("Voice systems online.")

    def callback(indata, frames, time_info, status):
        global is_speaking
        
        # 🚀 THE FIX: If the system is currently speaking, ignore all mic input
        if is_speaking:
            return

        # Resample
        audio_data = (indata * 32768).astype('int16').flatten()
        num_samples = int(len(audio_data) * VOSK_RATE / native_rate)
        indices = np.linspace(0, len(audio_data) - 1, num_samples).astype(int)
        resampled_data = audio_data[indices]
        
        if rec.AcceptWaveform(resampled_data.tobytes()):
            result = json.loads(rec.Result())
            command = result.get('text', '')
            
            if command:
                print(f"\n✅ Recognized: {command}")
                
                # Determine Response
                if "record" in command: response = f"Starting {command}"
                elif "finish" in command: response = "Recording saved"
                elif "point" in command: response = "Waypoint saved"
                else: response = f"Confirmed {command}"

                # Speak in thread so we don't crash the audio stream
                threading.Thread(target=speak_offline, args=(response,), daemon=True).start()
                
                # 🚀 THE FIX: Reset the recognizer immediately so it doesn't 
                # hold the 'Record' word in its buffer for the next loop.
                rec.Reset() 
        else:
            # Partial results for feedback
            partial = json.loads(rec.PartialResult())
            if partial['partial'] and not is_speaking:
                sys.stdout.write(f"\r🎤 Hearing: {partial['partial']}...")
                sys.stdout.flush()

    try:
        print(f"\n🎧 System Ready. Using Mic Index {mic_idx}")
        with sd.InputStream(samplerate=native_rate, device=mic_idx, channels=1, 
                            dtype='float32', blocksize=4000, callback=callback):
            while True:
                sd.sleep(1000)
    except KeyboardInterrupt:
        print("\n👋 Stopped.")

if __name__ == "__main__":
    run_system()