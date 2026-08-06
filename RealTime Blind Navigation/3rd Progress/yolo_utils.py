import numpy as np
import cv2
import math
import time
import os
import base64
import threading

def draw_birds_eye_view(tracks, width=250, height=250, max_range_m=4.0):
    bev = np.zeros((height, width, 3), dtype=np.uint8)
    cx, cy = width // 2, height - 15
    cv2.circle(bev, (cx, cy), 6, (0, 0, 255), -1) 
    cv2.putText(bev, "YOU", (cx - 13, cy + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1, cv2.LINE_AA)
    
    for dist_m in range(1, int(max_range_m) + 1):
        py_grid = int(cy - (dist_m / max_range_m) * (height - 30))
        cv2.line(bev, (10, py_grid), (width - 10, py_grid), (40, 40, 40), 1, cv2.LINE_AA)
        cv2.putText(bev, f"{dist_m}m", (12, py_grid - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (100, 100, 100), 1, cv2.LINE_AA)

    fov_rad = math.radians(68.3 / 2)
    dx = int((height - 30) * math.tan(fov_rad))
    cv2.line(bev, (cx, cy), (cx - dx, 15), (80, 80, 80), 1, cv2.LINE_AA)
    cv2.line(bev, (cx, cy), (cx + dx, 15), (80, 80, 80), 1, cv2.LINE_AA)
    
    for track_id, track in tracks.items():
        if len(track["x"]) == 0:
            continue
        rx, rz = track["x"][-1], track["z"][-1]
        
        px = int(cx + (rx / max_range_m) * (width / 2))
        py = int(cy - (rz / max_range_m) * (height - 30))
        
        if 0 <= px < width and 0 <= py < height:
            if len(track["x"]) > 1:
                pts = []
                for hx, hz in zip(track["x"], track["z"]):
                    h_px = int(cx + (hx / max_range_m) * (width / 2))
                    h_py = int(cy - (hz / max_range_m) * (height - 30))
                    pts.append((h_px, h_py))
                for i in range(len(pts) - 1):
                    cv2.line(bev, pts[i], pts[i+1], (0, 140, 255), 1, cv2.LINE_AA)
                    
            cv2.circle(bev, (px, py), 5, (0, 255, 0), -1)
            clean_lbl = track["label"].split(":")[-1].strip() if ":" in track["label"] else track["label"]
            cv2.putText(bev, f"{clean_lbl} (ID {track_id})", (px + 7, py + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            
    return bev


class HostCollisionTracker:
    def __init__(self, fx, fy, cx, cy, max_history=10):
        self.fx, self.fy, self.cx, self.cy = fx, fy, cx, cy
        self.max_history = max_history
        self.object_tracks = {}
        self.next_track_id = 0

    def project_to_3d(self, bbox, depth_m):
        bx1, by1, bx2, by2 = bbox
        center_x = (bx1 + bx2) / 2.0
        center_y = (by1 + by2) / 2.0
        real_z = depth_m
        real_x = ((center_x - self.cx) * real_z) / self.fx
        real_y = ((center_y - self.cy) * real_z) / self.fy
        return real_x, real_y, real_z

    def update_tracks(self, detected_objects):
        current_time = time.time()
        updated_tracks = {}

        for obj in detected_objects:
            bbox, depth_m, label = obj["box"], obj["distance"], obj["label"]
            if depth_m <= 0.0:
                continue 

            x, y, z = self.project_to_3d(bbox, depth_m)
            matched_id, min_dist = None, 0.8 

            for track_id, track_data in self.object_tracks.items():
                last_x, last_z = track_data["x"][-1], track_data["z"][-1]
                dist_3d = math.sqrt((x - last_x)**2 + (z - last_z)**2)
                if dist_3d < min_dist:
                    min_dist, matched_id = dist_3d, track_id

            if matched_id is None:
                matched_id = self.next_track_id
                self.next_track_id += 1
                self.object_tracks[matched_id] = {"x": [], "z": [], "timestamp": [], "label": label}

            track = self.object_tracks[matched_id]
            track["x"].append(x)
            track["z"].append(z)
            track["timestamp"].append(current_time)
            track["label"] = label 

            if len(track["x"]) > self.max_history:
                track["x"].pop(0)
                track["z"].pop(0)
                track["timestamp"].pop(0)

            updated_tracks[matched_id] = track

        for track_id, track_data in self.object_tracks.items():
            if track_id not in updated_tracks:
                if len(track_data["timestamp"]) > 0 and (current_time - track_data["timestamp"][-1] < 0.5):
                    updated_tracks[track_id] = track_data

        self.object_tracks = updated_tracks
        return self.object_tracks

    def analyze_collisions(self, path_clearance_threshold=0.25, moving_threshold=0.08):
        alerts = {}
        for track_id, track in self.object_tracks.items():
            if len(track["x"]) < 4:
                continue
            x_hist, z_hist, t_hist = track["x"], track["z"], track["timestamp"]
            is_moving_closer = z_hist[-1] < (z_hist[0] - moving_threshold)

            try:
                m, b = np.polyfit(x_hist, z_hist, 1)
                perp_distance = abs(b) / math.sqrt(m**2 + 1)
                delta_dist = math.sqrt((x_hist[-1] - x_hist[0])**2 + (z_hist[-1] - z_hist[0])**2)
                delta_t = t_hist[-1] - t_hist[0]
                speed = delta_dist / delta_t if delta_t > 0 else 0.0
                current_dist = math.sqrt(x_hist[-1]**2 + z_hist[-1]**2)
                tti = current_dist / speed if speed > 0.0 else float('inf')
                is_dangerous = is_moving_closer and (perp_distance < path_clearance_threshold)

                alerts[track_id] = {
                    "is_dangerous": is_dangerous, "label": track["label"],
                    "speed": speed, "tti": tti, "perp_distance": perp_distance, "current_distance": current_dist
                }
            except (np.linalg.LinAlgError, TypeError):
                pass
        return alerts


class SceneDescriber:
    SYSTEM_PROMPT = (
        "You are a wearable navigation assistant for a blind user. Describe what is in front of "
        "the user in 2 to 3 short, practical sentences. Focus on layout, landmarks, and pathways. "
        "Be spatial and direct: use left, right, ahead. Always state distances in meters, never feet. "
        "Focus on safety hazards or useful landmarks (doors, tables, counters). Do not say 'I see' or 'The image shows'."
    )

    def __init__(self, voice_assistant):
        self.voice = voice_assistant
        self.available = False
        self._processing = False
        self._last_request_time = 0.0
        self.cooldown_s = 6.0

        # API key configured directly in the script for reliability
        api_key = "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"

        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
            self.available = True
            print("🟢 [SceneDescriber] Anthropic Claude-Vision Client Initialized.")
        except ImportError:
            print("⚠️ [SceneDescriber] anthropic package not found.")

    def trigger_description(self, f_bgr, object_tracks):
        if not self.available or self._processing:
            return False
        now = time.time()
        if now - self._last_request_time < self.cooldown_s:
            return False

        self._processing = True
        self._last_request_time = now
        
        # 🚀 PREEMPTION: Lock standard notifications, clear active streams and play warning
        import audio_announcer
        audio_announcer.scene_description_active = True
        audio_announcer.interrupt_and_clear_queue()
        audio_announcer.speak("Analyzing environment")

        frame_copy = f_bgr.copy()
        tracks_snapshot = []
        for track_id, track in object_tracks.items():
            if len(track["z"]) > 0:
                tracks_snapshot.append({"label": track["label"], "x": track["x"][-1], "z": track["z"][-1]})

        threading.Thread(target=self._query_vision_model, args=(frame_copy, tracks_snapshot), daemon=True).start()
        return True

    def _query_vision_model(self, frame, tracks_snapshot):
        try:
            resized = cv2.resize(frame, (640, 480), interpolation=cv2.INTER_LINEAR)
            ok, encoded_buf = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if not ok:
                raise RuntimeError("Compression failed")
            img_b64 = base64.b64encode(encoded_buf.tobytes()).decode("utf-8")

            spatial_context = []
            for t in tracks_snapshot:
                direction = "on your left" if t["x"] < -0.25 else ("on your right" if t["x"] > 0.25 else "ahead")
                clean_lbl = t["label"].split(":")[-1].strip() if ":" in t["label"] else t["label"]
                spatial_context.append(f"{clean_lbl} {direction} at {t['z']:.1f} meters")

            sensor_payload_text = "Verified spatial depth data from sensors:\n" + (
                ", ".join(spatial_context) if spatial_context else "No close obstacles detected."
            )

            response = self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
                system=self.SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                        {"type": "text", "text": f"Analyze the scene. {sensor_payload_text}"}
                    ]
                }]
            )
            description_text = response.content[0].text.strip()
            self.voice.speak_info(description_text)
        except Exception as e:
            print(f"❌ [SceneDescriber] API Call failed: {e}")
            self.voice.speak_info("Description failed")
        finally:
            self._processing = False


class YoloPostProcessing:
    def __init__(self, score_threshold=0.30, model_type="yolov8"):
        self.score_threshold = score_threshold
        self.model_type = model_type.lower()
        self.labels = [
            "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
            "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
            "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
            "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
            "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
            "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
            "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
            "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
            "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book",
            "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
        ]

    def denormalize_box(self, box, img_h, img_w):
        size = max(img_h, img_w)
        padding_length = int(abs(img_h - img_w) / 2)
        ymin, xmin, ymax, xmax = box[:4]
        xmin_px, ymin_px = int(xmin * size), int(ymin * size)
        xmax_px, ymax_px = int(xmax * size), int(ymax * size)

        if img_h < size:
            ymin_px -= padding_length
            ymax_px -= padding_length
        elif img_w < size:
            xmin_px -= padding_length
            xmax_px -= padding_length
        return [max(0, xmin_px), max(0, ymin_px), min(img_w - 1, xmax_px), min(img_h - 1, ymax_px)]

    def get_spatial_zone(self, xmin, xmax, img_w):
        center_x = (xmin + xmax) / 2
        left_boundary, right_boundary = img_w * 0.33, img_w * 0.66
        if center_x < left_boundary: return "LEFT"
        elif center_x > right_boundary: return "RIGHT"
        else: return "CENTER"

    def calculate_distance(self, depth_map, box):
        if depth_map is None:
            return 0.0
        img_h, img_w = depth_map.shape[:2]
        bx1, by1, bx2, by2 = box
        bw, bh = bx2 - bx1, by2 - by1
        if bw < 8 or bh < 8:
            return 0.0

        cw, ch = int(bw * 0.6), int(bh * 0.6)
        cx, cy = bx1 + bw // 2, by1 + bh // 2
        sx1 = max(0, cx - cw // 2)
        sy1 = max(0, cy - ch // 2)
        sx2 = min(img_w - 1, cx + cw // 2)
        sy2 = min(img_h - 1, cy + ch // 2)

        region_area = (sy2 - sy1) * (sx2 - sx1)
        stride = max(1, int(math.sqrt(region_area / 4000)))
        
        depth_roi = depth_map[sy1:sy2:stride, sx1:sx2:stride]
        valid_depths = depth_roi[depth_roi > 0]
        
        if len(valid_depths) > 30:
            p10 = np.percentile(valid_depths, 10)
            p90 = np.percentile(valid_depths, 90)
            trimmed = valid_depths[(valid_depths >= p10) & (valid_depths <= p90)]
            median_depth_mm = np.median(trimmed) if len(trimmed) > 10 else np.median(valid_depths)
            return float(median_depth_mm / 1000.0)
        return 0.0

    def check_walkable_paths(self, depth_map):
        if depth_map is None:
            return {"LEFT": True, "CENTER": True, "RIGHT": True, "WALL_DIST": 0.0}
        h, w = depth_map.shape[:2]
        near_y1, near_y2 = int(h * 0.75), int(h * 0.95)
        far_y1, far_y2 = int(h * 0.55), int(h * 0.75)
        cols = {"LEFT": (0, int(w * 0.33)), "CENTER": (int(w * 0.33), int(w * 0.66)), "RIGHT": (int(w * 0.66), w)}

        paths, wall_distance = {}, 0.0
        for name, (col_x1, col_x2) in cols.items():
            near_slice = depth_map[near_y1:near_y2, col_x1:col_x2]
            far_slice = depth_map[far_y1:far_y2, col_x1:col_x2]
            near_valid = near_slice[near_slice > 0]
            far_valid = far_slice[far_slice > 0]
            near_z_m = (np.median(near_valid) / 1000.0) if len(near_valid) > 100 else 0.0
            far_z_m = (np.median(far_valid) / 1000.0) if len(far_valid) > 100 else 0.0

            is_walkable = True
            if near_z_m > 0.0 and far_z_m > 0.0:
                if abs(far_z_m - near_z_m) < 0.20:
                    is_walkable = False
                    if name == "CENTER": wall_distance = near_z_m
                elif near_z_m < 0.7:
                    is_walkable = False
            else:
                is_walkable = False
            paths[name] = is_walkable

        paths["WALL_DIST"] = wall_distance
        return paths

    def process_and_draw(self, raw_detections, image, depth_map=None):
        display_image = image.copy()
        img_h, img_w = display_image.shape[:2]
        cv2.line(display_image, (int(img_w * 0.33), 0), (int(img_w * 0.33), img_h), (255, 255, 255), 2, cv2.LINE_AA)
        cv2.line(display_image, (int(img_w * 0.66), 0), (int(img_w * 0.66), img_h), (255, 255, 255), 2, cv2.LINE_AA)
        parsed_objects = []

        try:
            key = list(raw_detections.keys())[0] if isinstance(raw_detections, dict) else None
            detections = raw_detections[key][0] if key else (raw_detections[0] if raw_detections else [])

            if self.model_type == "yolo26":
                for det in detections:
                    if len(det) < 6 or float(det[4]) < self.score_threshold: continue
                    ymin, xmin, ymax, xmax = det[:4]
                    orig_box = self.denormalize_box([ymin, xmin, ymax, xmax], img_h, img_w)
                    class_id = int(det[5])
                    if class_id < len(self.labels):
                        label = f"ID {class_id}: {self.labels[class_id]}"
                        zone = self.get_spatial_zone(orig_box[0], orig_box[2], img_w)
                        distance = self.calculate_distance(depth_map, orig_box)
                        parsed_objects.append({"label": label, "zone": zone, "score": float(det[4]), "box": orig_box, "distance": distance, "class_id": class_id})
            else:
                for class_id, detection_list in enumerate(detections):
                    for det in detection_list:
                        if len(det) < 5 or float(det[4]) < self.score_threshold: continue
                        ymin, xmin, ymax, xmax = det[:4]
                        orig_box = self.denormalize_box([ymin, xmin, ymax, xmax], img_h, img_w)
                        label = f"ID {class_id}: {self.labels[class_id]}" if class_id < len(self.labels) else f"ID {class_id}: Unknown"
                        zone = self.get_spatial_zone(orig_box[0], orig_box[2], img_w)
                        distance = self.calculate_distance(depth_map, orig_box)
                        parsed_objects.append({"label": label, "zone": zone, "score": float(det[4]), "box": orig_box, "distance": distance, "class_id": class_id})

            for obj in parsed_objects:
                label, zone, dist, (bx1, by1, bx2, by2) = obj["label"], obj["zone"], obj["distance"], obj["box"]
                color = (0, 0, 255) if zone == "CENTER" else (0, 140, 255)
                cv2.rectangle(display_image, (bx1, by1), (bx2, by2), color, 3)
                dist_text = f"{dist:.2f}m" if dist > 0.0 else "Too Close / Far"
                hud_text = f"{label} {dist_text} | {zone}"
                text_size = cv2.getTextSize(hud_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                cv2.rectangle(display_image, (bx1, by1-30), (bx1 + text_size[0] + 10, by1), color, -1)
                cv2.putText(display_image, hud_text, (bx1+5, by1-8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
        except Exception as e:
            print(f"Parsing error: {e}")
        return display_image, parsed_objects