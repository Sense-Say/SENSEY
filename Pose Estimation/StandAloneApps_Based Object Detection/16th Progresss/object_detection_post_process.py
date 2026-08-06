import cv2
import numpy as np
import math
import os
import sys

try:
    from hailo_apps.python.core.common.toolbox import id_to_color
except ImportError:
    from pathlib import Path
    core_dir = Path(__file__).resolve().parents[2] / "core"
    sys.path.insert(0, str(core_dir))
    from common.toolbox import id_to_color

def calculate_spatial_coords(center_x, center_y, depth_frame):
    if depth_frame is None: return None
    h, w = depth_frame.shape
    if center_x >= w or center_y >= h: return None
    roi_size = 6
    region = depth_frame[max(0, center_y-roi_size):min(h, center_y+roi_size), 
                         max(0, center_x-roi_size):min(w, center_x+roi_size)]
    valid = region[(region > 200) & (region < 10000)]
    if len(valid) == 0: return None
    return (0, np.median(valid) / 1000.0)

def extract_detections(image, detections, config_data):
    visualization_params = config_data["visualization_params"]
    score_threshold = visualization_params.get("score_thres", 0.5)
    max_boxes = visualization_params.get("max_boxes_to_draw", 50)
    img_h, img_w = image.shape[:2]
    all_detections = []
    if len(detections) == 1 and isinstance(detections, list):
        detections = detections[0]
    for class_id, class_list in enumerate(detections):
        if len(class_list) == 0: continue
        for det in class_list:
            if len(det) < 5: continue
            try:
                score = float(np.array(det[4]).flatten()[0])
            except: continue
            if score >= score_threshold:
                ymin, xmin, ymax, xmax = det[:4]
                box = [int(xmin * img_w), int(ymin * img_h), int(xmax * img_w), int(ymax * img_h)]
                all_detections.append((score, class_id, box))
    all_detections.sort(reverse=True, key=lambda x: x[0])
    top = all_detections[:max_boxes]
    if not top: return {'detection_boxes': [], 'detection_classes': [], 'detection_scores': [], 'num_detections': 0}
    s, c, b = zip(*top)
    return {'detection_boxes': list(b), 'detection_classes': list(c), 'detection_scores': list(s), 'num_detections': len(top)}

def draw_detections(detections: dict, img_out: np.ndarray, labels, vio_data=None, target_yaw=None, target_dist=None, depth_frame=None, state_text="IDLE"):
    height, width = img_out.shape[:2]
    center_x = width // 2
    l_lim, r_lim = width // 3, 2 * width // 3 
    
    # 1. Visual Boundaries
    cv2.line(img_out, (l_lim, 0), (l_lim, height), (255, 255, 255), 1)
    cv2.line(img_out, (r_lim, 0), (r_lim, height), (255, 255, 255), 1)

    if vio_data:
        dist_total, yaw, pitch, roll = vio_data
        
        # Compass Bar (Top)
        cv2.rectangle(img_out, (0, 0), (width, 70), (0, 0, 0), -1)
        cv2.line(img_out, (center_x, 10), (center_x, 60), (0, 255, 255), 2) 

        pixels_per_degree = width / 90 
        for deg in range(int(yaw - 45), int(yaw + 45)):
            screen_x = center_x + int((deg - yaw) * pixels_per_degree)
            if 0 < screen_x < width:
                if deg % 15 == 0:
                    cv2.line(img_out, (screen_x, 20), (screen_x, 40), (255, 255, 255), 2)
                    cv2.putText(img_out, str(deg % 360), (screen_x - 10, 60), 0, 0.4, (255, 255, 255), 1)

        # Pinned Green Arrow
        if target_yaw is not None:
            relative_angle = (target_yaw - yaw + 180) % 360 - 180
            arrow_x = center_x + int(relative_angle * pixels_per_degree)
            if 0 < arrow_x < width:
                in_center = l_lim <= arrow_x <= r_lim
                color = (0, 255, 0) if in_center else (150, 150, 150)
                pts = np.array([[arrow_x, 15], [arrow_x-10, 5], [arrow_x+10, 5]], np.int32)
                cv2.fillPoly(img_out, [pts], color)
                if target_dist is not None:
                    cv2.putText(img_out, f"{target_dist:.2f}m", (arrow_x - 15, 35), 0, 0.5, color, 2)

        # 🚀 REVISED DASHBOARD: Show Pitch and Roll
        overlay = img_out.copy()
        cv2.rectangle(overlay, (0, height-60), (width, height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, img_out, 0.4, 0, img_out)
        
        dashboard_text = f"MODE: {state_text} | DIST: {dist_total:.2f}m | YAW: {int(yaw)}' | P: {int(pitch)}' | R: {int(roll)}'"
        cv2.putText(img_out, dashboard_text, (20, height-20), 0, 0.6, (255, 255, 255), 2)

    # Object Detection Loop
    for idx in range(detections["num_detections"]):
        xmin, ymin, xmax, ymax = map(int, detections["detection_boxes"][idx])
        cls_id = detections["detection_classes"][idx]
        color = tuple(id_to_color(cls_id).tolist()) if 'id_to_color' in globals() else (255,255,255)
        cx, cy = (xmin + xmax) // 2, (ymin + ymax) // 2
        pos = "[C]" if l_lim <= cx <= r_lim else ("[L]" if cx < l_lim else "[R]")
        spatial = ""
        if depth_frame is not None:
            coords = calculate_spatial_coords(cx, cy, depth_frame)
            if coords: spatial = f"{coords[1]:.1f}m"
        label = f"{labels[cls_id]} {pos} {spatial}"
        cv2.rectangle(img_out, (xmin, ymin), (xmax, ymax), color, 2)
        cv2.putText(img_out, label, (xmin, ymin - 10), 0, 0.5, (255, 255, 255), 1)
        
    return img_out

def inference_result_handler(original_frame, infer_results, labels, config_data, tracker=None, vio_data=None, target_yaw=None, target_dist=None, depth_frame=None, state_text="IDLE"):
    detections = extract_detections(original_frame, infer_results, config_data)
    return draw_detections(detections, original_frame, labels, vio_data=vio_data, target_yaw=target_yaw, target_dist=target_dist, depth_frame=depth_frame, state_text=state_text)