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
    ram_file = "/dev/shm/report.wav"
    while True:
        text = audio_queue.get()
        if text is None: 
            break
        
        try:
            piper_cmd = (
                f"echo {shlex.quote(text)} | "
                f"{PIPER_EXE} --model {PIPER_MODEL} --length_scale 1.10 --output_file {ram_file}"
            )
            result = subprocess.run(piper_cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"🔊 [Piper Error]: {result.stderr.strip()}")
            
            if os.path.exists(ram_file):
                play_cmd = f"pw-play {ram_file}"
                play_result = subprocess.run(play_cmd, shell=True, capture_output=True, text=True)
                
                if play_result.returncode not in [0, 143, -15] and play_result.stderr.strip():
                    print(f"🔊 [PipeWire Error]: {play_result.stderr.strip()}")
                
                try:
                    os.remove(ram_file)
                except OSError:
                    pass
            else:
                print(f"⚠️ [Audio Error]: {ram_file} was not created.")
                
        except Exception as e:
            print(f"⚠️ [Audio Thread Error]: {e}")
        finally:
            audio_queue.task_done()

if PIPER_READY:
    threading.Thread(target=tts_worker, daemon=True).start()
else:
    print(f"⚠️ [Warning]: Piper or Model not found.")

def speak(text):
    audio_queue.put(text)


class SpatialAudioAnnouncer:
    def __init__(self):
        # Timing state variables
        self.last_critical_time = 0.0
        self.last_census_time = 0.0
        
        # Smart memory to prevent repetitive "Stop Stop" spam
        self.last_critical_label = ""
        self.last_critical_distance = 0.0
        
        self.spoken_objects = {}

    def update(self, objects, paths, alerts=None, img_w=1920):
        """
        Main decision loop called on every camera frame.
        Decides when to speak, what to say, and if it needs to execute a critical warning.
        """
        now = time.time()

        # --- 🚀 STEP 1: PARSE IMMEDIATE 3D COLLISION THREATS (Priority 1) ---
        collision_threats = []
        if alerts:
            for track_id, alert in alerts.items():
                # Detect critical predictive collision path if TTI is under 2.5 seconds
                if alert["is_dangerous"] and (0.1 <= alert["tti"] <= 2.5):
                    collision_threats.append(alert)

        # --- STEP 2: PARSE STANDARD YOLO OBJECT THREATS (Priority 2 Fallback) ---
        yolo_threats = []
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
                    yolo_threats.append(obj)

        # --- STEP 3: PRIORITIZE ALERTS AND TRIGGERS ---
        phrase = None
        label = ""
        dist_val = 0.0

        if collision_threats:
            # 🚀 Case A: Critical collision trajectory found
            # Grab tracklet showing closest time-to-impact
            closest_collision = min(collision_threats, key=lambda x: x["tti"])
            raw_lbl = closest_collision["label"]
            # Extract simple label (removes ID text)
            clean_lbl = raw_lbl.split(":")[-1].strip() if ":" in raw_lbl else raw_lbl
            tti = closest_collision["tti"]
            dist_val = closest_collision["current_distance"]
            phrase = f"Stop. Collision with {clean_lbl} in {tti:.1f} seconds."
            label = f"Col_{raw_lbl}"
        elif yolo_threats:
            # 🚀 Case B: Falling back to direct center-zone proximity
            closest_threat = yolo_threats[0]
            label = closest_threat['label']
            display_dist = closest_threat['display_dist']
            dist_val = closest_threat.get('distance', 0.0)
            phrase = f"Stop. {label} ahead, {display_dist} meters."
        else:
            # 🚀 Case C: Checking slope wall boundaries
            wall_dist = paths.get("WALL_DIST", 0.0)
            if 0.1 <= wall_dist <= 0.5:  
                phrase = "Stop. Facing the wall."
                label = "Wall"
                dist_val = wall_dist

        # If a critical warning is active, determine if it should be spoken
        if phrase:
            should_warn = False
            
            # Smart Repeat Limiter:
            if label != self.last_critical_label:
                # 1. New obstacle track found -> speak instantly
                should_warn = True
            elif dist_val > 0.0 and (self.last_critical_distance - dist_val) > 0.10:
                # 2. Obstacle rapidly closing in -> speak instantly
                should_warn = True
            elif now - self.last_critical_time > 4.5:
                # 3. Static blocking obstacle -> speak reminder every 4.5s
                should_warn = True

            if should_warn:
                self.last_critical_time = now
                self.last_critical_label = label
                self.last_critical_distance = dist_val
                
                # INTERRUPT: Clear old buffer outputs and stop current speech instantly
                subprocess.run("pkill pw-play", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Standardized thread-safe queue flushing
                while not audio_queue.empty():
                    try:
                        audio_queue.get_nowait()
                        audio_queue.task_done()
                    except queue.Empty:
                        break
                
                speak(phrase)
            
            return # Block room census checks while navigating active danger

        # --- STEP 4: ROLLING SPATIAL CENSUS (Once every 5.0 seconds) ---
        if now - self.last_census_time > 5.0:
            census_phrases = []

            # Reset critical track memory
            self.last_critical_label = ""
            self.last_critical_distance = 0.0

            # 1. State walkable paths
            if paths["CENTER"]:
                census_phrases.append("path open ahead")
            else:
                open_directions = [d.lower() for d, walkable in paths.items() if walkable and d != "CENTER" and d != "WALL_DIST"]
                if open_directions:
                    census_phrases.append(f"ahead blocked, path open to the {' and '.join(open_directions)}")
                else:
                    census_phrases.append("dead end, all paths blocked")

            # 2. State non-urgent peripheral objects
            for obj in objects:
                lbl = obj['label']
                zone = obj['zone'].lower()
                dist = obj['distance']

                if dist > 0.4:
                    key = (lbl, zone)
                    if now - self.spoken_objects.get(key, 0) > 8.0:
                        self.spoken_objects[key] = now
                        census_phrases.append(f"{lbl} on the {zone} at {dist:.1f} meters")

            if census_phrases:
                full_phrase = ". ".join(census_phrases) + "."
                full_phrase = full_phrase[0].upper() + full_phrase[1:]
                speak(full_phrase)
                self.last_census_time = now