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

FOCAL_LENGTH = 500.0  
CAMERA_HEIGHT = 1.1 

def calculate_spatial_coords(center_x, center_y, depth_frame):
    if depth_frame is None: return None
    h, w = depth_frame.shape
    if center_x >= w or center_y >= h: return None
    roi_size = 4 
    d_min_x, d_max_x = max(0, center_x - roi_size), min(w, center_x + roi_size)
    d_min_y, d_max_y = max(0, center_y - roi_size), min(h, center_y + roi_size)
    region = depth_frame[d_min_y:d_max_y, d_min_x:d_max_x]
    valid_depths = region[(region > 200) & (region < 10000)]
    if len(valid_depths) == 0: return None
    return (0, np.median(valid_depths) / 1000.0)

def draw_ar_elements(image, waypoints, current_pos, current_yaw, color=(0, 255, 0)):
    if not waypoints: return
    curr_x, curr_z = current_pos
    yaw_rad = math.radians(current_yaw)
    height, width = image.shape[:2]
    points_2d = []

    for wp in waypoints:
        dx, dz = wp[0] - curr_x, wp[1] - curr_z
        rx = dx * math.cos(-yaw_rad) - dz * math.sin(-yaw_rad)
        rz = dx * math.sin(-yaw_rad) + dz * math.cos(-yaw_rad)
        if rz > 0.3:
            sx = int((rx * FOCAL_LENGTH / rz) + width / 2)
            sy = int((CAMERA_HEIGHT * FOCAL_LENGTH / rz) + height / 2)
            if -100 < sx < width + 100 and -100 < sy < height + 100:
                points_2d.append((sx, sy, rz))

    for x, y, dist in points_2d:
        radius = max(4, int(40 / dist))
        alpha = max(0.2, 1.0 - (dist / 10.0))
        overlay = image.copy()
        cv2.circle(overlay, (x, y), radius, color, -1)
        cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

    if len(points_2d) > 1:
        for i in range(len(points_2d) - 1):
            cv2.line(image, points_2d[i][:2], points_2d[i+1][:2], color, 3)

def extract_detections(image, detections, config_data):
    visualization_params = config_data["visualization_params"]
    score_threshold = visualization_params.get("score_thres", 0.5)
    max_boxes = visualization_params.get("max_boxes_to_draw", 50)
    img_height, img_width = image.shape[:2]
    size = max(img_height, img_width)
    padding_length = int(abs(img_height - img_width) / 2)
    all_detections = []
    for class_id, class_detections in enumerate(detections):
        if len(class_detections) == 0: continue
        for det in class_detections:
            if len(det) < 5: continue
            bbox, score = det[:4], det[4]
            if score >= score_threshold:
                box = [int(x * size) for x in bbox]
                for i in range(4):
                    if i % 2 == 0:
                        if img_height != size: box[i] -= padding_length
                    else:
                        if img_width != size: box[i] -= padding_length
                all_detections.append((score, class_id, [box[1], box[0], box[3], box[2]]))
    all_detections.sort(reverse=True, key=lambda x: x[0])
    top = all_detections[:max_boxes]
    if not top: return {'detection_boxes': [], 'detection_classes': [], 'detection_scores': [], 'num_detections': 0}
    s, c, b = zip(*top)
    return {'detection_boxes': list(b), 'detection_classes': list(c), 'detection_scores': list(s), 'num_detections': len(top)}

def inference_result_handler(original_frame, infer_results, labels, config_data, tracker=None, vio_data=None, waypoints=None, nav_waypoints=None, depth_frame=None, state_text="IDLE"):
    detections = extract_detections(original_frame, infer_results, config_data)
    height, width, _ = original_frame.shape
    if vio_data:
        dist_total, yaw = vio_data
        curr_pos = (dist_total * math.sin(math.radians(yaw)), dist_total * math.cos(math.radians(yaw)))
        if waypoints: draw_ar_elements(original_frame, waypoints, curr_pos, yaw, color=(0, 0, 255))
        if nav_waypoints: draw_ar_elements(original_frame, nav_waypoints, curr_pos, yaw, color=(0, 255, 0))
        overlay = original_frame.copy()
        cv2.rectangle(overlay, (0, height-60), (width, height), (0,0,0), -1)
        cv2.addWeighted(overlay, 0.6, original_frame, 0.4, 0, original_frame)
        cv2.putText(original_frame, f"MODE: {state_text} | NAV: {dist_total:.1f}m | HEAD: {int(yaw)} deg", (20, height-20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    boxes, classes = detections["detection_boxes"], detections["detection_classes"]
    for idx in range(len(boxes)):
        xmin, ymin, xmax, ymax = map(int, boxes[idx])
        color = tuple(id_to_color(classes[idx]).tolist())
        center_x, center_y = (xmin + xmax) // 2, (ymin + ymax) // 2
        pos = "[C]" if (width/3) <= center_x <= (2*width/3) else ("[L]" if center_x < width/3 else "[R]")
        spatial = ""
        if depth_frame is not None:
            coords = calculate_spatial_coords(center_x, center_y, depth_frame)
            if coords: spatial = f"{coords[1]:.1f}m"
        cv2.rectangle(original_frame, (xmin, ymin), (xmax, ymax), color, 2)
        cv2.putText(original_frame, f"{labels[classes[idx]]} {pos} {spatial}", (xmin, ymin - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
    return original_frame