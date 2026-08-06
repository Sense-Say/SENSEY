import numpy as np
import cv2

class YoloPostProcessing:
    def __init__(self, score_threshold=0.30, model_type="yolov8"):
        self.score_threshold = score_threshold
        self.model_type = model_type.lower()
        
        # Standard COCO Mapping
        self.classroom_map = {
            0: "Person",
            13: "Student Chair",    # COCO: bench
            24: "Student Bag",      # COCO: backpack
            26: "Bag",              # COCO: handbag
            39: "Water Bottle",     # COCO: bottle
            41: "Cup",              # COCO: cup
            56: "Student Chair",    # COCO: chair
            60: "Desk",             # COCO: dining table
            62: "TV Screen",        # COCO: tv
            63: "Laptop",           # COCO: laptop
            64: "Computer Mouse",   # COCO: mouse
            66: "Keyboard",         # COCO: keyboard
            67: "Cellphone",        # COCO: cell phone
            73: "Book"              # COCO: book
        }

    def denormalize_box(self, box, img_h, img_w, model_size=640):
        """Maps Hailo's letterboxed 640x640 output back to the camera resolution."""
        scale = min(model_size / img_w, model_size / img_h)
        new_w, new_h = int(img_w * scale), int(img_h * scale)
        x_offset = (model_size - new_w) // 2
        y_offset = (model_size - new_h) // 2
        
        xmin = max(0, int((box[0] * model_size - x_offset) / scale))
        ymin = max(0, int((box[1] * model_size - y_offset) / scale))
        xmax = min(img_w - 1, int((box[2] * model_size - x_offset) / scale))
        ymax = min(img_h - 1, int((box[3] * model_size - y_offset) / scale))
        
        return [xmin, ymin, xmax, ymax]

    def get_spatial_zone(self, xmin, xmax, img_w):
        """Divides the screen into Left, Center, Right zones."""
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
        """Extracts a tight central ROI from the depth map and computes the median distance."""
        if depth_map is None:
            return 0.0
            
        img_h, img_w = depth_map.shape[:2]
        bx1, by1, bx2, by2 = box
        
        bw = bx2 - bx1
        bh = by2 - by1
        cx = bx1 + bw // 2
        cy = by1 + bh // 2
        
        # Center crop slice (15%)
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

    # --- 🚀 NEW: FLOOR-PLANE WALKABLE PATH EXTRACTOR ---
    def check_walkable_paths(self, depth_map):
        """Analyzes the lower floor plane to find clear walkways vs dead-ends."""
        if depth_map is None:
            return {"LEFT": False, "CENTER": False, "RIGHT": False}

        h, w = depth_map.shape[:2]

        # Bottom 30% of the screen represents the floor directly ahead of the user
        floor_y1 = int(h * 0.65)
        floor_y2 = int(h * 0.95)

        # Slice floor sectors
        left_floor = depth_map[floor_y1:floor_y2, 0:int(w * 0.33)]
        center_floor = depth_map[floor_y1:floor_y2, int(w * 0.33):int(w * 0.66)]
        right_floor = depth_map[floor_y1:floor_y2, int(w * 0.66):w]

        # We require at least 1.5 meters of open space ahead to declare a path walkable
        walkable_threshold_mm = 1500

        paths = {}
        for name, floor_slice in [("LEFT", left_floor), ("CENTER", center_floor), ("RIGHT", right_floor)]:
            valid_pixels = floor_slice[floor_slice > 0]
            # Must find a minimum number of valid depth pixels to calculate median
            if len(valid_pixels) > 100:
                median_depth = np.median(valid_pixels)
                paths[name] = True if (median_depth > walkable_threshold_mm) else False
            else:
                paths[name] = False # Blocked if too close to read depth

        return paths

    def process_and_draw(self, raw_detections, image, depth_map=None, model_size=640):
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
                        x1, y1, x2, y2 = det[:4]
                        box = [
                            np.clip(x1 / model_size, 0, 1),
                            np.clip(y1 / model_size, 0, 1),
                            np.clip(x2 / model_size, 0, 1),
                            np.clip(y2 / model_size, 0, 1)
                        ]
                        
                        orig_box = self.denormalize_box(box, img_h, img_w, model_size)
                        class_id = int(det[5])
                        
                        if class_id in self.classroom_map:
                            label = self.classroom_map[class_id]
                            zone = self.get_spatial_zone(orig_box[0], orig_box[2], img_w)
                            distance = self.calculate_distance(depth_map, orig_box)
                            
                            parsed_objects.append({
                                "label": label,
                                "zone": zone,
                                "score": score,
                                "box": orig_box,
                                "distance": distance
                            })
            else:
                for class_id, detection_list in enumerate(detections):
                    if class_id not in self.classroom_map:
                        continue
                    for det in detection_list:
                        if len(det) < 5: 
                            continue
                        score = float(det[4])
                        if score >= self.score_threshold:
                            ymin, xmin, ymax, xmax = det[:4]
                            box = [xmin, ymin, xmax, ymax]
                            orig_box = self.denormalize_box(box, img_h, img_w, model_size)
                            
                            label = self.classroom_map[class_id]
                            zone = self.get_spatial_zone(orig_box[0], orig_box[2], img_w)
                            distance = self.calculate_distance(depth_map, orig_box)
                            
                            parsed_objects.append({
                                "label": label,
                                "zone": zone,
                                "score": score,
                                "box": orig_box,
                                "distance": distance
                            })

            for obj in parsed_objects:
                label = obj["label"]
                zone = obj["zone"]
                score = obj["score"]
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