import queue
import threading
import subprocess
import shlex
import os
import time

# --- PATHS ---
PIPER_EXE = "/home/raspberrypi/TTS-STT-AUDIO/piper/piper" 
PIPER_MODEL = "/home/raspberrypi/TTS-STT-AUDIO/en_US-lessac-medium.onnx"
PIPER_READY = os.path.exists(PIPER_EXE) and os.path.exists(PIPER_MODEL)

# Initialize the background queue inside the module
audio_queue = queue.Queue()

def tts_worker():
    """Background daemon thread to render speech to RAM and play via PipeWire."""
    ram_file = "/dev/shm/report.wav"
    while True:
        text = audio_queue.get()
        if text is None: 
            break
        
        try:
            piper_cmd = (
                f"echo {shlex.quote(text)} | "
                f"{PIPER_EXE} --model {PIPER_MODEL} --length_scale 0.85 --output_file {ram_file}"
            )
            # Run Piper
            result = subprocess.run(piper_cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"🔊 [Piper Error]: {result.stderr.strip()}")
            
            # Only play if the WAV file was successfully generated
            if os.path.exists(ram_file):
                play_cmd = f"pw-play {ram_file}"
                play_result = subprocess.run(play_cmd, shell=True, capture_output=True, text=True)
                
                # 🚀 FIX: Ignore exit codes 143 and -15.
                # These are standard Unix return codes when pw-play is intentionally terminated by pkill.
                if play_result.returncode not in [0, 143, -15] and play_result.stderr.strip():
                    print(f"🔊 [PipeWire Error]: {play_result.stderr.strip()}")
                
                os.remove(ram_file)
            else:
                print(f"⚠️ [Audio Error]: {ram_file} was not created. Check your Piper/Model paths!")
                
        except Exception as e:
            print(f"⚠️ [Audio Thread Error]: {e}")
        finally:
            audio_queue.task_done()

# Start the background audio thread automatically on import
if PIPER_READY:
    threading.Thread(target=tts_worker, daemon=True).start()
else:
    print(f"⚠️ [Warning]: Piper or Model not found at specified paths:\n   Exe: {PIPER_EXE}\n   Model: {PIPER_MODEL}")

def speak(text):
    """Adds a sentence to the background voice queue."""
    audio_queue.put(text)


class SpatialAudioAnnouncer:
    def __init__(self):
        # Timing state variables
        self.last_critical_time = 0.0
        self.last_census_time = 0.0
        
        # Track when we last announced specific objects to prevent spam
        self.spoken_objects = {}

    def update(self, objects, paths, img_w=1920):
        """
        Main decision loop called on every camera frame.
        Decides when to speak, what to say, and if it needs to execute a critical warning.
        """
        now = time.time()

        # --- 🚀 STEP 1: CHECK FOR IMMEDIATE CRITICAL OBSTACLES (<0.4m) ---
        # Trigger stop if:
        # - Object is in CENTER and distance is between 0.1 and 0.4m
        # - OR distance is 0.0 (Too Close for triangulation) but the bounding box 
        #   takes up > 25% of the screen width (meaning it is right in front of you).
        critical_threats = []
        for obj in objects:
            if obj['zone'] == 'CENTER':
                dist = obj['distance']
                bx1, by1, bx2, by2 = obj['box']
                width_fraction = (bx2 - bx1) / float(img_w)
                
                is_danger = False
                if 0.1 <= dist <= 0.4:
                    is_danger = True
                elif dist == 0.0 and width_fraction > 0.25:
                    is_danger = True
                    
                if is_danger:
                    obj['display_dist'] = f"{dist:.1f}" if dist > 0.0 else "under 0.4"
                    critical_threats.append(obj)

        if critical_threats:
            closest_threat = critical_threats[0]
            label = closest_threat['label']
            display_dist = closest_threat['display_dist']

            # Enforce a short 1.8s cooldown on critical loops so it doesn't stutter-overlap
            if now - self.last_critical_time > 1.8:
                self.last_critical_time = now
                
                # 🚀 INTERRUPT: Kill active pw-play and purge background queue instantly!
                subprocess.run("pkill pw-play", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                with audio_queue.mutex:
                    audio_queue.queue.clear()
                
                # Broadcast emergency stop
                speak(f"Stop. {label} ahead, {display_dist} meters.")
            
            return # Skip the normal room census entirely while in danger

        # --- 🚀 STEP 2: ROLLING SPATIAL CENSUS (Once every 5.0 seconds) ---
        if now - self.last_census_time > 5.0:
            census_phrases = []

            # 1. State the walkable path status
            if paths["CENTER"]:
                census_phrases.append("path open ahead")
            else:
                open_directions = [d.lower() for d, walkable in paths.items() if walkable and d != "CENTER"]
                if open_directions:
                    census_phrases.append(f"ahead blocked, path open to the {' and '.join(open_directions)}")
                else:
                    census_phrases.append("dead end, all paths blocked")

            # 2. State peripheral objects if they are not spamming
            for obj in objects:
                label = obj['label']
                zone = obj['zone'].lower()
                dist = obj['distance']

                # We only list peripheral objects if they are safely in range
                if dist > 0.4:
                    key = (label, zone)
                    # Enforce a strict 8-second cooldown on specific object/zone pairs
                    if now - self.spoken_objects.get(key, 0) > 8.0:
                        self.spoken_objects[key] = now
                        census_phrases.append(f"{label} on the {zone} at {dist:.1f} meters")

            if census_phrases:
                # Compile into standard spoken paragraph
                full_phrase = ". ".join(census_phrases) + "."
                full_phrase = full_phrase[0].upper() + full_phrase[1:]
                speak(full_phrase)
                self.last_census_time = now