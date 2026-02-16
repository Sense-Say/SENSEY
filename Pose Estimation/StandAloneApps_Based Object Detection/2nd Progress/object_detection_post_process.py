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

# Dictionary to store a limited history of tracklet coordinates.
tracklet_history = {}
trail_length = 30 
TRACKLET_CLASSES = [0, 67]  # PERSON, SMARTPHONE

def inference_result_handler(original_frame, infer_results, labels, config_data, tracker=None, draw_trail=False):
    """
    Processes inference results and draw detections (with optional tracking).
    """
    detections = extract_detections(original_frame, infer_results, config_data)
    frame_with_detections = draw_detections(detections, original_frame, labels, tracker=tracker, draw_trail=draw_trail)
    return frame_with_detections


def draw_detection(image: np.ndarray, box: list, labels: list, score: float, color: tuple, track=False):
    """
    Draw box and label for one detection.
    """
    xmin, ymin, xmax, ymax = map(int, box)
    cv2.rectangle(image, (xmin, ymin), (xmax, ymax), color, 2)
    font = cv2.FONT_HERSHEY_SIMPLEX

    # Compose texts
    top_text = f"{labels[0]}: {score:.1f}%" if not track or len(labels) == 2 else f"{score:.1f}%"
    bottom_text = None

    if track:
        if len(labels) == 2:
            bottom_text = labels[1]
        else:
            bottom_text = labels[0]

    # Set colors
    text_color = (255, 255, 255)  # White
    border_color = (0, 0, 0)  # Black

    # Draw top text with black border first
    cv2.putText(image, top_text, (xmin + 4, ymin + 20), font, 0.5, border_color, 2, cv2.LINE_AA)
    cv2.putText(image, top_text, (xmin + 4, ymin + 20), font, 0.5, text_color, 1, cv2.LINE_AA)

    # Draw bottom text if exists
    if bottom_text:
        pos = (xmax - 50, ymax - 6)
        cv2.putText(image, bottom_text, pos, font, 0.5, border_color, 2, cv2.LINE_AA)
        cv2.putText(image, bottom_text, pos, font, 0.5, text_color, 1, cv2.LINE_AA)


def denormalize_and_rm_pad(box: list, size: int, padding_length: int, input_height: int, input_width: int) -> list:
    """
    Denormalize bounding box coordinates and remove padding.
    """
    # Scale box coordinates
    box = [int(x * size) for x in box]

    # Apply padding correction
    for i in range(4):
        if i % 2 == 0:  # x-coordinates
            if input_height != size:
                box[i] -= padding_length
        else:  # y-coordinates
            if input_width != size:
                box[i] -= padding_length

    # Swap to [ymin, xmin, ymax, xmax]
    return [box[1], box[0], box[3], box[2]]


def extract_detections(image: np.ndarray, detections: list, config_data) -> dict:
    """
    Extract detections from the input data.
    """
    visualization_params = config_data["visualization_params"]
    score_threshold = visualization_params.get("score_thres", 0.5)
    max_boxes = visualization_params.get("max_boxes_to_draw", 50)

    img_height, img_width = image.shape[:2]
    size = max(img_height, img_width)
    padding_length = int(abs(img_height - img_width) / 2)

    all_detections = []

    for class_id, detection in enumerate(detections):
        for det in detection:
            bbox, score = det[:4], det[4]
            if score >= score_threshold:
                denorm_bbox = denormalize_and_rm_pad(bbox, size, padding_length, img_height, img_width)
                all_detections.append((score, class_id, denorm_bbox))

    all_detections.sort(reverse=True, key=lambda x: x[0])
    top_detections = all_detections[:max_boxes]
    scores, class_ids, boxes = zip(*top_detections) if top_detections else ([], [], [])

    return {
        'detection_boxes': list(boxes),
        'detection_classes': list(class_ids),
        'detection_scores': list(scores),
        'num_detections': len(top_detections)
    }

# --- NEW HELPER FUNCTION ---
def get_position_text(xmin, xmax, width):
    """Calculates if object is Left, Center, or Right."""
    center_x = (xmin + xmax) // 2
    if center_x < width / 3:
        return "[LEFT]"
    elif center_x < (width * 2) / 3:
        return "[CENTER]"
    else:
        return "[RIGHT]"

def draw_detections(detections: dict, img_out: np.ndarray, labels, tracker=None, draw_trail=False) -> np.ndarray:
    """
    Draw detections with Spatial Awareness (Left/Center/Right).
    """

    # --- 1. DRAW PARTITION LINES (Visual Guide) ---
    height, width, _ = img_out.shape
    left_limit = int(width / 3)
    right_limit = int(width * 2 / 3)
    
    # Draw White lines to divide the screen
    cv2.line(img_out, (left_limit, 0), (left_limit, height), (255, 255, 255), 2)
    cv2.line(img_out, (right_limit, 0), (right_limit, height), (255, 255, 255), 2)
    # ---------------------------------------------

    boxes = detections["detection_boxes"] 
    scores = detections["detection_scores"]
    num_detections = detections["num_detections"]
    classes = detections["detection_classes"]

    if tracker:
        dets_for_tracker = []
        for idx in range(num_detections):
            box = boxes[idx]
            score = scores[idx]
            dets_for_tracker.append([*box, score])

        if not dets_for_tracker:
            return img_out

        online_targets = tracker.update(np.array(dets_for_tracker))

        for track in online_targets:
            track_id = track.track_id
            x1, y1, x2, y2 = track.tlbr
            xmin, ymin, xmax, ymax = map(int, [x1, y1, x2, y2])
            
            # --- 2. GET SPATIAL POSITION ---
            pos_text = get_position_text(xmin, xmax, width)
            # -------------------------------

            best_idx = find_best_matching_detection_index(track.tlbr, boxes)
            color = tuple(id_to_color(classes[best_idx]).tolist())
            
            if best_idx is None:
                # Add position to ID label
                label = f"ID {track_id} {pos_text}"
                draw_detection(img_out, [xmin, ymin, xmax, ymax], [label],
                               track.score * 100.0, color, track=True)
            else:
                # Add position to Class label (e.g. "Person [CENTER]")
                class_name = labels[classes[best_idx]]
                label_list = [f"{class_name} {pos_text}", f"ID {track_id}"]
                
                draw_detection(img_out, [xmin, ymin, xmax, ymax], label_list,
                               track.score * 100.0, color, track=True)
                               
            if not classes[best_idx] in TRACKLET_CLASSES:
                continue

            center_x = int((x1 + x2) / 2)
            center_y = int((y1 + y2) / 2)
            centroid = (center_x, center_y)
            
            if track_id not in tracklet_history:
                tracklet_history[track_id] = deque(maxlen=trail_length)
            tracklet_history[track_id].append(centroid)

            if draw_trail:
                for i in range(1, len(tracklet_history[track_id])):
                    point_a = tracklet_history[track_id][i-1]
                    point_b = tracklet_history[track_id][i]
                    cv2.line(img_out, point_a, point_b, color, 3)
                    cv2.circle(img_out, point_b, radius=20, thickness=1, color=color)

    else:
        # No tracking — draw raw model detections with Spatial info
        for idx in range(num_detections):
            color = tuple(id_to_color(classes[idx]).tolist())
            
            xmin, ymin, xmax, ymax = map(int, boxes[idx])
            
            # --- 3. GET SPATIAL POSITION ---
            pos_text = get_position_text(xmin, xmax, width)
            # -------------------------------
            
            # Update label string
            class_label = labels[classes[idx]]
            final_label = f"{class_label} {pos_text}"
            
            draw_detection(img_out, boxes[idx], [final_label], scores[idx] * 100.0, color)

    return img_out


def find_best_matching_detection_index(track_box, detection_boxes):
    """
    Finds the index of the detection box with the highest IoU relative to the given tracking box.
    """
    best_iou = 0
    best_idx = -1

    for i, det_box in enumerate(detection_boxes):
        iou = compute_iou(track_box, det_box)
        if iou > best_iou:
            best_iou = iou
            best_idx = i

    return best_idx if best_idx != -1 else None


def compute_iou(boxA, boxB):
    """
    Compute Intersection over Union (IoU) between two bounding boxes.
    """
    xA, yA = max(boxA[0], boxB[0]), max(boxA[1], boxB[1])
    xB, yB = min(boxA[2], boxB[2]), min(boxA[3], boxB[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    areaA = max(1e-5, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
    areaB = max(1e-5, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))
    return inter / (areaA + areaB - inter + 1e-5)