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
PATH_WIDTH = 0.6 
CYLINDER_RADIUS = 0.3 

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

def draw_3d_checkpoint(image, target_wp, curr_x, curr_z, current_yaw):
    height, width = image.shape[:2]
    yaw_rad = math.radians(current_yaw)
    dx, dz = target_wp[0] - curr_x, target_wp[1] - curr_z
    rx = dx * math.cos(-yaw_rad) - dz * math.sin(-yaw_rad)
    rz = dx * math.sin(-yaw_rad) + dz * math.cos(-yaw_rad)
    if rz < 0.5: return
    cx = int((rx * FOCAL_LENGTH / rz) + width / 2)
    by = int((CAMERA_HEIGHT * FOCAL_LENGTH / rz) + height / 2)
    ty = int(((CAMERA_HEIGHT - 1.0) * FOCAL_LENGTH / rz) + height / 2)
    p_w = int((CYLINDER_RADIUS * FOCAL_LENGTH) / rz)
    p_h = int(p_w * 0.3) 
    color = (0, 0, 255) # Red
    overlay = image.copy()
    pts = np.array([[cx-p_w, ty],[cx+p_w, ty],[cx+p_w, by],[cx-p_w, by]], np.int32)
    cv2.fillPoly(overlay, [pts], color)
    cv2.ellipse(overlay, (cx, by), (p_w, p_h), 0, 0, 360, color, -1)
    cv2.ellipse(overlay, (cx, ty), (p_w, p_h), 0, 0, 360, color, -1)
    cv2.addWeighted(overlay, 0.4, image, 0.6, 0, image)
    cv2.polylines(image, [pts], True, color, 2)
    cv2.ellipse(image, (cx, by), (p_w, p_h), 0, 0, 360, color, 2)
    cv2.ellipse(image, (cx, ty), (p_w, p_h), 0, 0, 360, color, 2)

def draw_ar_path(image, waypoints, current_pos, current_yaw, is_navigating=False):
    if not waypoints or len(waypoints) < 2: return
    curr_x, curr_z = current_pos
    yaw_rad = math.radians(current_yaw)
    height, width = image.shape[:2]
    
    active_waypoints = waypoints
    target_landmark = None
    if is_navigating:
        target_idx = len(waypoints)
        for i, wp in enumerate(waypoints):
            if len(wp) > 2 and "point" in str(wp[2]).lower():
                target_idx, target_landmark = i + 1, wp
                break
        active_waypoints = waypoints[:target_idx]

    l_pts, r_pts = [], []
    for i in range(len(active_waypoints)):
        wp = active_waypoints[i]
        dx, dz = (active_waypoints[i+1][0]-wp[0], active_waypoints[i+1][1]-wp[1]) if i<len(active_waypoints)-1 else (0, 1)
        L = math.sqrt(dx*dx + dz*dz) + 0.001
        px, pz = -dz/L, dx/L
        for x_w, z_w, lst in [(wp[0]+px*PATH_WIDTH/2, wp[1]+pz*PATH_WIDTH/2, l_pts), (wp[0]-px*PATH_WIDTH/2, wp[1]-pz*PATH_WIDTH/2, r_pts)]:
            rx = (x_w-curr_x)*math.cos(-yaw_rad)-(z_w-curr_z)*math.sin(-yaw_rad)
            rz = (x_w-curr_x)*math.sin(-yaw_rad)+(z_w-curr_z)*math.cos(-yaw_rad)
            if rz > 0.2: lst.append((int((rx*FOCAL_LENGTH/rz)+width/2), int((CAMERA_HEIGHT*FOCAL_LENGTH/rz)+height/2)))

    if len(l_pts) > 1 and len(r_pts) > 1:
        color = (255, 150, 0) if is_navigating else (0, 0, 255) # Blue for Nav
        overlay = image.copy()
        pts = np.array(l_pts + r_pts[::-1], np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(overlay, [pts], color)
        cv2.addWeighted(overlay, 0.5, image, 0.5, 0, image)
        cv2.polylines(image, [pts], True, color, 2)
    if target_landmark: draw_3d_checkpoint(image, target_landmark, curr_x, curr_z, current_yaw)

def extract_detections(image, detections, config_data):
    visualization_params = config_data["visualization_params"]
    score_threshold = visualization_params.get("score_thres", 0.5)
    max_boxes = visualization_params.get("max_boxes_to_draw", 50)
    img_h, img_w = image.shape[:2]
    all_detections = []
    
    # 🚀 REVERTED TO WORKING LOGIC, WITH ADDED FIX FOR CLASS ID
    if len(detections) == 1 and isinstance(detections, list):
        detections = detections[0] # Strip outer batch if present

    for class_id, class_list in enumerate(detections):
        if len(class_list) == 0: continue
        for det in class_list:
            if len(det) < 5: continue
            
            # The Fix: Safe extraction of the score
            try:
                score = float(np.array(det[4]).flatten()[0])
            except Exception:
                continue

            if score >= score_threshold:
                # Map stretched 640x640 back to 1080p
                ymin, xmin, ymax, xmax = det[:4]
                box = [int(xmin * img_w), int(ymin * img_h), int(xmax * img_w), int(ymax * img_h)]
                
                # 🚀 The Fix: We save the class_id here so we know if it's a chair(56) or person(0)
                all_detections.append((score, class_id, box))
    
    all_detections.sort(reverse=True, key=lambda x: x[0])
    top = all_detections[:max_boxes]
    if not top: return {'detection_boxes': [], 'detection_classes': [], 'detection_scores': [], 'num_detections': 0}
    s, c, b = zip(*top)
    return {'detection_boxes': list(b), 'detection_classes': list(c), 'detection_scores': list(s), 'num_detections': len(top)}

def draw_detections(detections, img_out, labels, vio_data=None, depth_frame=None, state_text="IDLE"):
    height, width = img_out.shape[:2]
    l_lim, r_lim = width // 3, 2 * width // 3
    
    if vio_data:
        dist, yaw, pitch, roll = vio_data
        overlay = img_out.copy()
        cv2.rectangle(overlay, (0, height-60), (width, height), (0,0,0), -1)
        cv2.addWeighted(overlay, 0.6, img_out, 0.4, 0, img_out)
        cv2.putText(img_out, f"MODE: {state_text} | NAV: {dist:.1f}m | YAW: {int(yaw)} | P: {int(pitch)} | R: {int(roll)}", 
                    (20, height-20), 0, 0.6, (255, 255, 255), 2)
                    
    cv2.line(img_out, (l_lim, 0), (l_lim, height), (255, 255, 255), 1)
    cv2.line(img_out, (right_limit, 0), (right_limit, height), (255, 255, 255), 1)
    
    for idx in range(detections["num_detections"]):
        xmin, ymin, xmax, ymax = map(int, detections["detection_boxes"][idx])
        
        # 🚀 Use the corrected class ID to grab the color and name
        cls_id = detections["detection_classes"][idx]
        color = tuple(id_to_color(cls_id).tolist())
        
        cx, cy = (xmin + xmax) // 2, (ymin + ymax) // 2
        pos = "[C]" if l_lim <= cx <= r_lim else ("[L]" if cx < l_lim else "[R]")
        spatial = ""
        if depth_frame is not None:
            coords = calculate_spatial_coords(cx, (ymin+ymax)//2, depth_frame)
            if coords: spatial = f"{coords[1]:.1f}m"
            
        # 🚀 Display the correct label
        label = f"{labels[cls_id]} {pos} {spatial}"
        
        cv2.rectangle(img_out, (xmin, ymin), (xmax, ymax), color, 2)
        cv2.putText(img_out, label, (xmin, ymin - 10), 0, 0.5, (255,255,255), 1)
        
    return img_out

def draw_detections(detections: dict, img_out: np.ndarray, labels, vio_data=None, depth_frame=None, state_text="IDLE"):
    """
    Renders the 6 DOF Dashboard and Object Labels.
    """
    height, width = img_out.shape[:2]
    l_lim, r_lim = width // 3, 2 * width // 3
    
    # --- 1. DRAW 6 DOF DASHBOARD ---
    if vio_data:
        # We unpack 4 values now: Distance, Yaw, Pitch, Roll
        dist, yaw, pitch, roll = vio_data
        
        # Draw semi-transparent black background for the dashboard
        overlay = img_out.copy()
        cv2.rectangle(overlay, (0, height-70), (width, height), (0,0,0), -1)
        cv2.addWeighted(overlay, 0.6, img_out, 0.4, 0, img_out)
        
        # Format the 6 DOF string
        # Yaw is Heading | Pitch is Up/Down | Roll is Side Tilt
        nav_text = f"MODE: {state_text} | DIST: {dist:.1f}m | YAW: {int(yaw)}' | PITCH: {int(pitch)}' | ROLL: {int(roll)}'"
        cv2.putText(img_out, nav_text, (20, height-25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # --- 2. DRAW PARTITION LINES ---
    cv2.line(img_out, (l_lim, 0), (l_lim, height), (255, 255, 255), 1)
    cv2.line(img_out, (r_lim, 0), (r_lim, height), (255, 255, 255), 1)
    
    # --- 3. DRAW OBJECTS ---
    for idx in range(detections["num_detections"]):
        xmin, ymin, xmax, ymax = map(int, detections["detection_boxes"][idx])
        cls_id = detections["detection_classes"][idx]
        color = tuple(id_to_color(cls_id).tolist())
        cx, cy = (xmin + xmax) // 2, (ymin + ymax) // 2
        
        pos = "[C]" if l_lim <= cx <= r_lim else ("[L]" if cx < l_lim else "[R]")
        spatial = ""
        if depth_frame is not None:
            coords = calculate_spatial_coords(cx, cy, depth_frame)
            if coords: spatial = f"{coords[1]:.1f}m"
        
        label = f"{labels[cls_id]} {pos} {spatial}"
        cv2.rectangle(img_out, (xmin, ymin), (xmax, ymax), color, 2)
        cv2.putText(img_out, label, (xmin, ymin - 10), 0, 0.5, (255,255,255), 1)
        
    return img_out
def inference_result_handler(original_frame, infer_results, labels, config_data, tracker=None, vio_data=None, waypoints=None, nav_waypoints=None, depth_frame=None, state_text="IDLE"):
    detections = extract_detections(original_frame, infer_results, config_data)
    
    if vio_data:
        # 🚀 FIX: Unpack all 4 values from the 6-DOF engine
        dist_total, yaw, pitch, roll = vio_data
        
        curr_pos = (dist_total * math.sin(math.radians(yaw)), dist_total * math.cos(math.radians(yaw)))
        if waypoints: draw_ar_path(original_frame, waypoints, curr_pos, yaw, is_navigating=False)
        if nav_waypoints: draw_ar_path(original_frame, nav_waypoints, curr_pos, yaw, is_navigating=True)
        
    return draw_detections(detections, original_frame, labels, vio_data=vio_data, depth_frame=depth_frame, state_text=state_text)
