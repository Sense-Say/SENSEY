import queue
import threading
import subprocess
import shlex
import os
import time
import math
import wave
import tempfile

PIPER_EXE = "/home/raspberrypi/TTS-STT-AUDIO/piper/piper" 
PIPER_MODEL = "/home/raspberrypi/TTS-STT-AUDIO/en_US-lessac-medium.onnx"
PIPER_READY = os.path.exists(PIPER_EXE) and os.path.exists(PIPER_MODEL)

# Global queue and preemption state trackers
audio_queue = queue.Queue()
scene_description_active = False # 🚀 Controls standard navigation suppression

def interrupt_and_clear_queue():
    """🚀 Instantly kills active audio playback processes and empties the queue."""
    player_exe = "pw-play" if os.path.exists("/usr/bin/pw-play") else "aplay"
    subprocess.run(f"pkill {player_exe}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
            audio_queue.task_done()
        except queue.Empty:
            break

def speak(text):
    audio_queue.put(text)

def speak_description(text):
    """🚀 Enqueues the final scene description with a tag to trigger state release."""
    audio_queue.put(("DESCRIPTION", text))

def tts_worker():
    global scene_description_active
    ram_file = "/dev/shm/report.wav"
    while True:
        item = audio_queue.get()
        if item is None: 
            break
        
        # Check if this item is the final scene description
        if isinstance(item, tuple) and item[0] == "DESCRIPTION":
            text = item[1]
            is_desc = True
        else:
            text = item
            is_desc = False
        
        # 🚀 Print exactly what the headset is saying to the terminal
        print(f"\n🎙️ [SPEAKING]: {text}\n")
        
        try:
            piper_cmd = f"echo {shlex.quote(text)} | {PIPER_EXE} --model {PIPER_MODEL} --length_scale 1.10 --output_file {ram_file}"
            result = subprocess.run(piper_cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"🔊 [Piper Error]: {result.stderr.strip()}")
            
            if os.path.exists(ram_file):
                play_cmd = f"pw-play {ram_file}" if os.path.exists("/usr/bin/pw-play") else f"aplay {ram_file}"
                play_result = subprocess.run(play_cmd, shell=True, capture_output=True, text=True)
                
                if play_result.returncode not in [0, 143, -15] and play_result.stderr.strip():
                    print(f"🔊 [Player Error]: {play_result.stderr.strip()}")
                
                try: os.remove(ram_file)
                except OSError: pass
            else:
                print(f"⚠️ [Audio Error]: {ram_file} not found.")
        except Exception as e:
            print(f"⚠️ [Audio Thread Error]: {e}")
        finally:
            audio_queue.task_done()
            # 🚀 Release the suppression lock once the description finishes playing
            if is_desc:
                scene_description_active = False

if PIPER_READY:
    threading.Thread(target=tts_worker, daemon=True).start()
else:
    print("⚠️ [Warning]: Local Piper TTS not configured.")


class ProximityTonePlayer:
    def __init__(self, volume=0.30):
        self.volume = volume
        self.sample_rate = 22050
        self._last_pulse = 0.0
        self._thread = None
        self._lock = threading.Lock()

    def update(self, tracks, alerts):
        # 🚀 Suppress spatial pulses while a scene description is active
        if scene_description_active:
            return

        now = time.time()
        closest_alert, closest_id = None, None
        for track_id, alert in alerts.items():
            if alert["current_distance"] < 2.0:
                if closest_alert is None or alert["current_distance"] < closest_alert["current_distance"]:
                    closest_alert, closest_id = alert, track_id
                    
        if closest_alert is None:
            return

        dist = closest_alert["current_distance"]
        closeness = (2.0 - max(0.35, dist)) / 1.65
        interval = 1.4 * ((0.18 / 1.4) ** closeness)

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return 
            if now - self._last_pulse < interval:
                return
            self._last_pulse = now

            track_data = tracks.get(closest_id)
            if track_data and len(track_data["x"]) > 0:
                rx = track_data["x"][-1]
                left_gain = max(0.15, min(1.0, 0.5 - rx))
                right_gain = max(0.15, min(1.0, 0.5 + rx))
            else:
                left_gain, right_gain = 0.7, 0.7

            freq = 1120 if dist <= 0.7 else 880 
            duration = 0.055

            self._thread = threading.Thread(
                target=self._play_worker,
                args=(left_gain, right_gain, freq, duration),
                daemon=True
            )
            self._thread.start()

    def _play_worker(self, left_gain, right_gain, freq, duration):
        wav_path = None
        try:
            frames = int(self.sample_rate * duration)
            amp = int(32767 * self.volume)
            fd, wav_path = tempfile.mkstemp(prefix="nav_tone_", suffix=".wav")
            os.close(fd)
            
            with wave.open(wav_path, "wb") as wav:
                wav.setnchannels(2)
                wav.setsampwidth(2)
                wav.setframerate(self.sample_rate)
                buf = bytearray()
                for i in range(frames):
                    phase = 2.0 * math.pi * freq * (i / self.sample_rate)
                    sample = int(math.sin(phase) * amp)
                    left = int(sample * left_gain)
                    right = int(sample * right_gain)
                    buf.extend(left.to_bytes(2, "little", signed=True))
                    buf.extend(right.to_bytes(2, "little", signed=True))
                wav.writeframes(bytes(buf))
            
            player_exe = "pw-play" if os.path.exists("/usr/bin/pw-play") else "aplay"
            subprocess.run([player_exe, wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        finally:
            if wav_path and os.path.exists(wav_path):
                try: os.unlink(wav_path)
                except Exception: pass


class SpatialAudioAnnouncer:
    def __init__(self):
        self.last_critical_time, self.last_census_time = 0.0, 0.0
        self.last_critical_label, self.last_critical_distance = "", 0.0
        self.spoken_objects = {}

    def speak_info(self, text):
        """🚀 Route informational alerts to description worker to manage state reset."""
        speak_description(text)

    def update(self, objects, paths, alerts=None, img_w=1920):
        # 🚀 Suppress all standard navigation updates during active scene descriptions
        if scene_description_active:
            return

        now = time.time()
        collision_threats = []
        if alerts:
            for track_id, alert in alerts.items():
                if alert["is_dangerous"] and (0.1 <= alert["tti"] <= 2.5):
                    collision_threats.append(alert)

        yolo_threats = []
        for obj in objects:
            if obj['zone'] == 'CENTER':
                dist = obj['distance']
                bx1, by1, bx2, by2 = obj['box']
                width_fraction = (bx2 - bx1) / float(img_w)
                is_danger = (0.1 <= dist <= 0.4) or (dist == 0.0 and width_fraction > 0.25)
                if is_danger:
                    obj['display_dist'] = f"{dist:.1f}" if dist > 0.0 else "under 0.4"
                    yolo_threats.append(obj)

        phrase, label, dist_val = None, "", 0.0

        if collision_threats:
            closest_collision = min(collision_threats, key=lambda x: x["tti"])
            raw_lbl = closest_collision["label"]
            clean_lbl = raw_lbl.split(":")[-1].strip() if ":" in raw_lbl else raw_lbl
            tti = closest_collision["tti"]
            dist_val = closest_collision["current_distance"]
            phrase = f"Stop. Collision with {clean_lbl} in {tti:.1f} seconds."
            label = f"Col_{raw_lbl}"
        elif yolo_threats:
            closest_threat = yolo_threats[0]
            label = closest_threat['label']
            display_dist = closest_threat['display_dist']
            dist_val = closest_threat.get('distance', 0.0)
            phrase = f"Stop. {label} ahead, {display_dist} meters."
        else:
            wall_dist = paths.get("WALL_DIST", 0.0)
            if 0.1 <= wall_dist <= 0.5:  
                phrase = "Stop. Facing the wall."
                label = "Wall"
                dist_val = wall_dist

        if phrase:
            should_warn = False
            if label != self.last_critical_label:
                should_warn = True
            elif dist_val > 0.0 and (self.last_critical_distance - dist_val) > 0.10:
                should_warn = True
            elif now - self.last_critical_time > 4.5:
                should_warn = True

            if should_warn:
                self.last_critical_time, self.last_critical_label, self.last_critical_distance = now, label, dist_val
                
                player_exe = "pw-play" if os.path.exists("/usr/bin/pw-play") else "aplay"
                subprocess.run(f"pkill {player_exe}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                while not audio_queue.empty():
                    try:
                        audio_queue.get_nowait()
                        audio_queue.task_done()
                    except queue.Empty:
                        break
                speak(phrase)
            return 

        if now - self.last_census_time > 5.0:
            census_phrases = []
            self.last_critical_label, self.last_critical_distance = "", 0.0

            if paths["CENTER"]:
                census_phrases.append("path open ahead")
            else:
                open_directions = [d.lower() for d, walkable in paths.items() if walkable and d != "CENTER" and d != "WALL_DIST"]
                if open_directions:
                    census_phrases.append(f"ahead blocked, path open to the {' and '.join(open_directions)}")
                else:
                    census_phrases.append("dead end, all paths blocked")

            for obj in objects:
                lbl, zone, dist = obj['label'], obj['zone'].lower(), obj['distance']
                if dist > 0.4:
                    key = (lbl, zone)
                    if now - self.spoken_objects.get(key, 0) > 8.0:
                        self.spoken_objects[key] = now
                        census_phrases.append(f"{lbl} on the {zone} at {dist:.1f} meters")

            if census_phrases:
                full_phrase = ". ".join(census_phrases) + "."
                speak(full_phrase[0].upper() + full_phrase[1:])
                self.last_census_time = now