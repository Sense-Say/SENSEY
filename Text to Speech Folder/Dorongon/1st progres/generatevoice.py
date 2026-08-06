from gtts import gTTS
import os

# 1. Create the directory if it doesn't exist
save_dir = "/home/raspberrypi/audio_files"
if not os.path.exists(save_dir):
    os.makedirs(save_dir)
    print(f"Created directory: {save_dir}")

# 2. Define the phrases to generate
phrases = {
    "startup": "Handa na ang sistema. Pumili ng mode.",
    "behavior_active": "Mode ng Pag-uugali ng Estudyante, Aktibo na.",
    "blind_active": "Mode ng Nabigasyon para sa Bulag, Aktibo na.",
    "standby": "Naka-standby ang sistema.",
    "shutdown": "Paalam. Nag-sha-shut down na.",
    "stopping": "Pinapahinto ang proseso."
}

print("⏳ Generating Filipino Audio Files (Requires Internet)...")

# 3. Generate and Save
for filename, text in phrases.items():
    file_path = os.path.join(save_dir, f"{filename}.mp3")
    print(f"   Generating: {filename}.mp3...")
    
    try:
        # 'tl' is the code for Tagalog
        tts = gTTS(text=text, lang='tl', slow=False) 
        tts.save(file_path)
        print(f"   ✅ Saved to: {file_path}")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        print("   (Check your internet connection!)")

print("\nDONE! You can now run the controller.")