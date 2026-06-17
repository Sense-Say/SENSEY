import numpy as np
import cv2
import math
import time

def draw_birds_eye_view(tracks, width=250, height=250, max_range_m=4.0):
    """
    Renders a live, real-time top-down map of all tracked obstacle trajectories.
    - width, height: pixel dimensions of the mini-map canvas
    - max_range_m: scale of the map (displays up to 4.0 meters away)
    """
    # Create a blank black canvas for the map
    bev = np.zeros((height, width, 3), dtype=np.uint8)
    
    # User / Camera origin represented at bottom-center
    cx, cy = width // 2, height - 15
    cv2.circle(bev, (cx, cy), 6, (0, 0, 255), -1) # Red dot for User
    cv2.putText(bev, "YOU", (cx - 13, cy + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1, cv2.LINE_AA)
    
    # Draw horizontal distance grid lines
    for dist_m in range(1, int(max_range_m) + 1):
        py_grid = int(cy - (dist_m / max_range_m) * (height - 30))
        cv2.line(bev, (10, py_grid), (width - 10, py_grid), (40, 40, 40), 1, cv2.LINE_AA)
        cv2.putText(bev, f"{dist_m}m", (12, py_grid - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (100, 100, 100), 1, cv2.LINE_AA)

    # Draw camera FOV boundaries (68.3 degree horizontal coverage)
    fov_rad = math.radians(68.3 / 2)
    dx = int((height - 30) * math.tan(fov_rad))
    cv2.line(bev, (cx, cy), (cx - dx, 15), (80, 80, 80), 1, cv2.LINE_AA)
    cv2.line(bev, (cx, cy), (cx + dx, 15), (80, 80, 80), 1, cv2.LINE_AA)
    
    # Plot obstacle paths
    for track_id, track in tracks.items():
        if len(track["x"]) == 0:
            continue
        
        rx = track["x"][-1]
        rz = track["z"][-1]
        
        # Translate meters to pixel canvas coordinates
        px = int(cx + (rx / max_range_m) * (width / 2))
        py = int(cy - (rz / max_range_m) * (height - 30))
        
        if 0 <= px < width and 0 <= py < height:
            # Draw historical path trajectory line
            if len(track["x"]) > 1:
                pts = []
                for hx, hz in zip(track["x"], track["z"]):
                    h_px = int(cx + (hx / max_range_m) * (width / 2))
                    h_py = int(cy - (hz / max_range_m) * (height - 30))
                    pts.append((h_px, h_py))
                for i in range(len(pts) - 1):
                    cv2.line(bev, pts[i], pts[i+1], (0, 140, 255), 1, cv2.LINE_AA)
                    
            # Draw current position as a green dot
            cv2.circle(bev, (px, py), 5, (0, 255, 0), -1)
            
            # Clean up the display class label
            clean_lbl = track["label"].split(":")[-1].strip() if ":" in track["label"] else track["label"]
            cv2.putText(bev, f"{clean_lbl} (ID {track_id})", (px + 7, py + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            
    return bev


class HostCollisionTracker:
    def __init__(self, fx, fy, cx, cy, max_history=10):
        # Camera intrinsic matrix parameters
        self.fx = fx
        self.fy = fy
        self.cx = cx
        self.cy = cy
        
        self.max_history = max_history
        self.object_tracks = {}
        self.next_track_id = 0

    def project_to_3d(self, bbox, depth_m):
        """Projects 2D center point and physical depth value into real-world coordinate meters."""
        bx1, by1, bx2, by2 = bbox
        center_x = (bx1 + bx2) / 2.0
        center_y = (by1 + by2) / 2.0
        
        real_z = depth_m
        real_x = ((center_x - self.cx) * real_z) / self.fx
        real_y = ((center_y - self.cy) * real_z) / self.fy
        return real_x, real_y, real_z

    def update_tracks(self, detected_objects):
        """Performs simple distance association to maintain consistent IDs across frames."""
        current_time = time.time()
        updated_tracks = {}

        for obj in detected_objects:
            bbox = obj["box"]
            depth_m = obj["distance"]
            label = obj["label"]
            if depth_m <= 0.0:
                continue 

            x, y, z = self.project_to_3d(bbox, depth_m)

            # Match with closest active track within 0.8 meters
            matched_id = None
            min_dist = 0.8 

            for track_id, track_data in self.object_tracks.items():
                last_x = track_data["x"][-1]
                last_z = track_data["z"][-1]
                dist_3d = math.sqrt((x - last_x)**2 + (z - last_z)**2)
                
                if dist_3d < min_dist:
                    min_dist = dist_3d
                    matched_id = track_id

            if matched_id is None:
                matched_id = self.next_track_id
                self.next_track_id += 1
                self.object_tracks[matched_id] = {
                    "x": [], "z": [], "timestamp": [], 
                    "label": label
                }

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

        # Keep track memory briefly during short detection dropouts (up to 0.5 seconds)
        for track_id, track_data in self.object_tracks.items():
            if track_id not in updated_tracks:
                if len(track_data["timestamp"]) > 0 and (current_time - track_data["timestamp"][-1] < 0.5):
                    updated_tracks[track_id] = track_data

        self.object_tracks = updated_tracks
        return self.object_tracks

    def analyze_collisions(self, path_clearance_threshold=0.25, moving_threshold=0.08):
        """Calculates linear trajectory models, velocities, and predicted Time-to-Impact."""
        alerts = {}

        for track_id, track in self.object_tracks.items():
            if len(track["x"]) < 4:  # Needs at least 4 tracking frames to estimate trajectory
                continue

            x_hist = track["x"]
            z_hist = track["z"]
            t_hist = track["timestamp"]

            # Validate if object is actively moving closer
            is_moving_closer = z_hist[-1] < (z_hist[0] - moving_threshold)

            try:
                # Linear trajectory regression (z = m * x + b)
                m, b = np.polyfit(x_hist, z_hist, 1)
                perp_distance = abs(b) / math.sqrt(m**2 + 1)
                
                # Compute Speed (m/s)
                delta_dist = math.sqrt((x_hist[-1] - x_hist[0])**2 + (z_hist[-1] - z_hist[0])**2)
                delta_t = t_hist[-1] - t_hist[0]
                speed = delta_dist / delta_t if delta_t > 0 else 0.0
                
                current_dist = math.sqrt(x_hist[-1]**2 + z_hist[-1]**2)
                tti = current_dist / speed if speed > 0.0 else float('inf')

                # Collision triggers if trajectory intersects centerline and object moves closer
                is_dangerous = is_moving_closer and (perp_distance < path_clearance_threshold)

                alerts[track_id] = {
                    "is_dangerous": is_dangerous,
                    "label": track["label"],
                    "speed": speed,
                    "tti": tti,
                    "perp_distance": perp_distance,
                    "current_distance": current_dist
                }
            except (np.linalg.LinAlgError, TypeError):
                pass

        return alerts


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
            "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
            "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator",
            "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
        ]

    def denormalize_box(self, box, img_h, img_w):
        size = max(img_h, img_w)
        padding_length = int(abs(img_h - img_w) / 2)
        ymin, xmin, ymax, xmax = box[:4]
        
        xmin_px = int(xmin * size)
        ymin_px = int(ymin * size)
        xmax_px = int(xmax * size)
        ymax_px = int(ymax * size)

        if img_h < size:
            ymin_px -= padding_length
            ymax_px -= padding_length
        elif img_w < size:
            xmin_px -= padding_length
            xmax_px -= padding_length

        return [
            max(0, xmin_px),
            max(0, ymin_px),
            min(img_w - 1, xmax_px),
            min(img_h - 1, ymax_px)
        ]

    def get_spatial_zone(self, xmin, xmax, img_w):
        center_x = (xmin + xmax) / 2
        left_boundary = img_w * 0.33
        right_boundary = img_w * 0.66
        
        if center_x < left_boundary:
            return "LEFT"
        elif center_x > right_boundary:
            return "RIGHT"
        else:
            return "CENTER"

    def calculate_distance(self, depth_map, box):
        if depth_map is None:
            return 0.0
            
        img_h, img_w = depth_map.shape[:2]
        bx1, by1, bx2, by2 = box
        
        bw = bx2 - bx1
        bh = by2 - by1
        cx = bx1 + bw // 2
        cy = by1 + bh // 2
        
        roi_w = int(bw * 0.15)
        roi_h = int(bh * 0.15)
        
        rx1 = max(0, cx - roi_w)
        rx2 = min(img_w - 1, cx + roi_w)
        ry1 = max(0, cy - roi_h)
        ry2 = min(img_h - 1, cy + roi_h)
        
        depth_roi = depth_map[ry1:ry2, rx1:rx2]
        valid_depths = depth_roi[depth_roi > 0]
        
        if len(valid_depths) > 0:
            median_depth_mm = np.median(valid_depths)
            return float(median_depth_mm / 1000.0) 
        return 0.0

    def check_walkable_paths(self, depth_map):
        if depth_map is None:
            return {"LEFT": True, "CENTER": True, "RIGHT": True, "WALL_DIST": 0.0}

        h, w = depth_map.shape[:2]

        near_y1, near_y2 = int(h * 0.75), int(h * 0.95)
        far_y1, far_y2 = int(h * 0.55), int(h * 0.75)

        cols = {
            "LEFT": (0, int(w * 0.33)),
            "CENTER": (int(w * 0.33), int(w * 0.66)),
            "RIGHT": (int(w * 0.66), w)
        }

        paths = {}
        wall_distance = 0.0

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
                    if name == "CENTER":
                        wall_distance = near_z_m
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
            if isinstance(raw_detections, dict):
                key = list(raw_detections.keys())[0]
                detections = raw_detections[key][0] 
            else:
                detections = raw_detections[0]

            if self.model_type == "yolo26":
                for det in detections:
                    if len(det) < 6:
                        continue
                    score = float(det[4])
                    if score >= self.score_threshold:
                        ymin, xmin, ymax, xmax = det[:4]
                        orig_box = self.denormalize_box([ymin, xmin, ymax, xmax], img_h, img_w)
                        class_id = int(det[5])
                        
                        if class_id < len(self.labels):
                            label = f"ID {class_id}: {self.labels[class_id]}"
                            zone = self.get_spatial_zone(orig_box[0], orig_box[2], img_w)
                            distance = self.calculate_distance(depth_map, orig_box)
                            
                            parsed_objects.append({
                                "label": label,
                                "zone": zone,
                                "score": score,
                                "box": orig_box,
                                "distance": distance, 
                                "class_id": class_id
                            })
            else:
                for class_id, detection_list in enumerate(detections):
                    for det in detection_list:
                        if len(det) < 5: 
                            continue
                        score = float(det[4])
                        if score >= self.score_threshold:
                            ymin, xmin, ymax, xmax = det[:4]
                            orig_box = self.denormalize_box([ymin, xmin, ymax, xmax], img_h, img_w)
                            
                            label = f"ID {class_id}: {self.labels[class_id]}" if class_id < len(self.labels) else f"ID {class_id}: Unknown"
                            zone = self.get_spatial_zone(orig_box[0], orig_box[2], img_w)
                            distance = self.calculate_distance(depth_map, orig_box)
                            
                            parsed_objects.append({
                                "label": label,
                                "zone": zone,
                                "score": score,
                                "box": orig_box,
                                "distance": distance,
                                "class_id": class_id
                            })

            for obj in parsed_objects:
                label = obj["label"]
                zone = obj["zone"]
                dist = obj["distance"]
                bx1, by1, bx2, by2 = obj["box"]

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