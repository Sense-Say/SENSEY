import vosk
from vosk import Model, KaldiRecognizer
import sounddevice as sd
import json
import sys
import os
import numpy as np

# --- CONFIGURATION ---
# Use the L-GRAPH model for better accuracy
MODEL_PATH = "/home/raspberrypi/Downloads/vosk-model-en-us-0.22-lgraph"
VOSK_RATE = 16000

# --- GRAMMAR DEFINITION ---
# Only these words will be recognized. This makes accuracy nearly perfect.
# List all words you might say for your navigation project.
ALLOWED_WORDS = [
    "record", "finish", "go", "to", "point", "saved", 
    "front", "back", "door", "desk", "window", "stop",
    "left", "right", "center", "navigate", "start", "[unk]"
]

def get_usb_mic_info():
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if "USB" in dev['name'] and dev['max_input_channels'] > 0:
            return i, int(dev['default_samplerate'])
    return None, None

def run_test():
    if not os.path.exists(MODEL_PATH):
        print(f"❌ Error: Model not found at {MODEL_PATH}")
        return

    print("⏳ Loading High-Accuracy Model...")
    model = Model(MODEL_PATH)
    
    # Initialize recognizer with GRAMMAR
    # This tells the AI to ONLY look for our specific navigation words
    grammar = json.dumps(ALLOWED_WORDS)
    rec = KaldiRecognizer(model, VOSK_RATE, grammar)

    mic_idx, native_rate = get_usb_mic_info()
    if mic_idx is None:
        print("❌ Error: USB Microphone not found.")
        return
    
    print(f"✅ Mic Found: {sd.query_devices(mic_idx)['name']}")
    print(f"✅ Grammar Active: Only listening for navigation commands.")

    def callback(indata, frames, time, status):
        audio_data = (indata * 32768).astype('int16').flatten()
        num_samples = int(len(audio_data) * VOSK_RATE / native_rate)
        indices = np.linspace(0, len(audio_data) - 1, num_samples).astype(int)
        resampled_data = audio_data[indices]
        
        if rec.AcceptWaveform(resampled_data.tobytes()):
            result = json.loads(rec.Result())
            if result['text']:
                print(f"\n✅ Command: {result['text']}")
        else:
            partial = json.loads(rec.PartialResult())
            if partial['partial']:
                sys.stdout.write(f"\r🎤 Hearing: {partial['partial']}...")
                sys.stdout.flush()

    try:
        print(f"\n🎧 System Online. Speak your navigation commands...")
        with sd.InputStream(samplerate=native_rate, device=mic_idx, 
                            channels=1, dtype='float32', blocksize=4000, 
                            callback=callback):
            while True:
                sd.sleep(1000)
    except KeyboardInterrupt:
        print("\n\n👋 Stopped.")

if __name__ == "__main__":
    run_test()