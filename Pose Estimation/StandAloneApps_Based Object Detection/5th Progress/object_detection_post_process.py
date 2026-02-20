import cv2
import numpy as np
try:
    from hailo_apps.python.core.common.toolbox import id_to_color
except ImportError:
    from pathlib import Path
    import sys
    core_dir = Path(__file__).resolve().parents[2] / "core"
    sys.path.insert(0, str(core_dir))
    from common.toolbox import id_to_color

import os
from collections import deque

tracklet_history = {}
trail_length = 30 
TRACKLET_CLASSES = [0, 67]

# --- HELPER: CALCULATE XYZ ---
def calculate_spatial_coords(center_x, center_y, depth_frame):
    if depth_frame is None: return None
    h, w = depth_frame.shape
    if center_x >= w or center_y >= h: return None

    # Increase ROI to 4x4 or 6x6 to smooth out noise
    roi_size = 4 
    d_min_x = max(0, center_x - roi_size)
    d_max_x = min(w, center_x + roi_size)
    d_min_y = max(0, center_y - roi_size)
    d_max_y = min(h, center_y + roi_size)
    
    region = depth_frame[d_min_y:d_max_y, d_min_x:d_max_x]
    
    # Filter out 0 (invalid) and very large values (glitches)
    # Only keep realistic distances (e.g. 200mm to 10000mm)
    valid_depths = region[(region > 200) & (region < 10000)]
    
    if len(valid_depths) == 0: return None

    z_mm = np.median(valid_depths)
    z_meters = z_mm / 1000.0
    
    return (0, z_meters) # We only care about Z for now

def inference_result_handler(original_frame, infer_results, labels, config_data, tracker=None, draw_trail=False, depth_frame=None):
    detections = extract_detections(original_frame, infer_results, config_data)
    frame_with_detections = draw_detections(detections, original_frame, labels, tracker=tracker, draw_trail=draw_trail, depth_frame=depth_frame)
    return frame_with_detections

def denormalize_and_rm_pad(box, size, padding_length, input_height, input_width):
    box = [int(x * size) for x in box]
    for i in range(4):
        if i % 2 == 0:
            if input_height != size: box[i] -= padding_length
        else:
            if input_width != size: box[i] -= padding_length
    return [box[1], box[0], box[3], box[2]]

def extract_detections(image, detections, config_data):
    visualization_params = config_data["visualization_params"]
    score_threshold = visualization_params.get("score_thres", 0.5)
    max_boxes = visualization_params.get("max_boxes_to_draw", 50)
    img_height, img_width = image.shape[:2]
    size = max(img_height, img_width)
    padding_length = int(abs(img_height - img_width) / 2)
    all_detections = []

    # FIX: Remove np.array(detections) call to avoid inhomogeneous shape error
    # We iterate directly. We expect detections to be [Classes, Boxes, Data]
    
    for class_id, class_detections in enumerate(detections):
        # class_detections is a list/array of boxes for this class
        if len(class_detections) == 0: continue
        
        for det in class_detections:
            # Check for valid data length (ymin, xmin, ymax, xmax, score)
            if len(det) < 5: continue
            
            bbox, score = det[:4], det[4]
            if score >= score_threshold:
                denorm_bbox = denormalize_and_rm_pad(bbox, size, padding_length, img_height, img_width)
                all_detections.append((score, class_id, denorm_bbox))

    all_detections.sort(reverse=True, key=lambda x: x[0])
    top_detections = all_detections[:max_boxes]
    scores, class_ids, boxes = zip(*top_detections) if top_detections else ([], [], [])
    
    return {'detection_boxes': list(boxes), 'detection_classes': list(class_ids), 'detection_scores': list(scores), 'num_detections': len(top_detections)}

def draw_detection(image, box, labels, score, color, track=False):
    xmin, ymin, xmax, ymax = map(int, box)
    cv2.rectangle(image, (xmin, ymin), (xmax, ymax), color, 2)
    font = cv2.FONT_HERSHEY_SIMPLEX
    top_text = f"{labels[0]}"
    cv2.putText(image, top_text, (xmin + 4, ymin + 20), font, 0.5, (0,0,0), 2, cv2.LINE_AA)
    cv2.putText(image, top_text, (xmin + 4, ymin + 20), font, 0.5, (255,255,255), 1, cv2.LINE_AA)

def get_position_text(xmin, xmax, width):
    center_x = (xmin + xmax) // 2
    if center_x < width / 3: return "[LEFT]"
    elif center_x < (width * 2) / 3: return "[CENTER]"
    else: return "[RIGHT]"

def draw_detections(detections: dict, img_out: np.ndarray, labels, tracker=None, draw_trail=False, depth_frame=None) -> np.ndarray:
    height, width, _ = img_out.shape
    
    # Grid lines
    left_limit = int(width / 3)
    right_limit = int(width * 2 / 3)
    cv2.line(img_out, (left_limit, 0), (left_limit, height), (255, 255, 255), 2)
    cv2.line(img_out, (right_limit, 0), (right_limit, height), (255, 255, 255), 2)

    boxes = detections["detection_boxes"] 
    scores = detections["detection_scores"]
    num_detections = detections["num_detections"]
    classes = detections["detection_classes"]

    for idx in range(num_detections):
        xmin, ymin, xmax, ymax = map(int, boxes[idx])
        color = tuple(id_to_color(classes[idx]).tolist())
        
        # Position Logic
        pos_text = get_position_text(xmin, xmax, width)
        
        # Spatial Logic
        spatial_text = ""
        if depth_frame is not None:
            center_x = (xmin + xmax) // 2
            center_y = (ymin + ymax) // 2
            coords = calculate_spatial_coords(center_x, center_y, depth_frame)
            if coords:
                _, z_m = coords
                spatial_text = f"{z_m:.2f}m"
        
        class_name = labels[classes[idx]]
        # FINAL LABEL
        final_label = f"{class_name} {pos_text} {spatial_text}"
        
        draw_detection(img_out, boxes[idx], [final_label], scores[idx] * 100.0, color)

    return img_out

def find_best_matching_detection_index(track_box, detection_boxes):
    best_iou = 0; best_idx = -1
    for i, det_box in enumerate(detection_boxes):
        iou = compute_iou(track_box, det_box)
        if iou > best_iou: best_iou = iou; best_idx = i
    return best_idx if best_idx != -1 else None

def compute_iou(boxA, boxB):
    xA, yA = max(boxA[0], boxB[0]), max(boxA[1], boxB[1])
    xB, yB = min(boxA[2], boxB[2]), min(boxA[3], boxB[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    areaA = max(1e-5, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
    areaB = max(1e-5, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))
    return inter / (areaA + areaB - inter + 1e-5)