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

# --- HELPER: CALCULATE XYZ ---
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

def inference_result_handler(original_frame, infer_results, labels, config_data, tracker=None, vio_data=None, depth_frame=None):
    detections = extract_detections(original_frame, infer_results, config_data)
    frame_with_detections = draw_detections(detections, original_frame, labels, vio_data=vio_data, depth_frame=depth_frame)
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
    for class_id, class_detections in enumerate(detections):
        if len(class_detections) == 0: continue
        for det in class_detections:
            if len(det) < 5: continue
            bbox, score = det[:4], det[4]
            if score >= score_threshold:
                denorm_bbox = denormalize_and_rm_pad(bbox, size, padding_length, img_height, img_width)
                all_detections.append((score, class_id, denorm_bbox))
    all_detections.sort(reverse=True, key=lambda x: x[0])
    top_detections = all_detections[:max_boxes]
    scores, class_ids, boxes = zip(*top_detections) if top_detections else ([], [], [])
    return {'detection_boxes': list(boxes), 'detection_classes': list(class_ids), 'detection_scores': list(scores), 'num_detections': len(top_detections)}

def draw_detection(image, box, labels, color):
    xmin, ymin, xmax, ymax = map(int, box)
    cv2.rectangle(image, (xmin, ymin), (xmax, ymax), color, 2)
    cv2.putText(image, labels[0], (xmin + 4, ymin + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 2)
    cv2.putText(image, labels[0], (xmin + 4, ymin + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

def draw_detections(detections: dict, img_out: np.ndarray, labels, vio_data=None, depth_frame=None) -> np.ndarray:
    height, width, _ = img_out.shape
    left_limit, right_limit = int(width / 3), int(width * 2 / 3)
    
    # 1. DRAW NAVIGATION DASHBOARD (At the bottom)
    if vio_data:
        dist, yaw = vio_data
        # Draw a semi-transparent black bar at the bottom
        overlay = img_out.copy()
        cv2.rectangle(overlay, (0, height-60), (width, height), (0,0,0), -1)
        cv2.addWeighted(overlay, 0.6, img_out, 0.4, 0, img_out)
        
        # Draw VIO Stats
        cv2.putText(img_out, f"NAV: {dist:.2f}m | HEAD: {int(yaw)} deg", (20, height-20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    # Grid lines
    cv2.line(img_out, (left_limit, 0), (left_limit, height), (255, 255, 255), 1)
    cv2.line(img_out, (right_limit, 0), (right_limit, height), (255, 255, 255), 1)

    boxes, scores, num_dets, classes = detections["detection_boxes"], detections["detection_scores"], detections["num_detections"], detections["detection_classes"]

    for idx in range(num_dets):
        xmin, ymin, xmax, ymax = map(int, boxes[idx])
        color = tuple(id_to_color(classes[idx]).tolist())
        center_x, center_y = (xmin + xmax) // 2, (ymin + ymax) // 2
        
        pos = "[C]" if left_limit <= center_x <= right_limit else ("[L]" if center_x < left_limit else "[R]")
        
        spatial_text = ""
        if depth_frame is not None:
            coords = calculate_spatial_coords(center_x, center_y, depth_frame)
            if coords: spatial_text = f"{coords[1]:.1f}m"
        
        final_label = f"{labels[classes[idx]]} {pos} {spatial_text}"
        draw_detection(img_out, boxes[idx], [final_label], color)

    return img_out