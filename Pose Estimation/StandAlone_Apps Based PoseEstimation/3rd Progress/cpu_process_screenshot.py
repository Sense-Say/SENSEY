import cv2
import pickle
import json
import os
import face_recognition
import numpy as np

# --- CONFIGURATION ---
SCREENSHOT_PATH = "/home/raspberrypi/Documents/temp_screenshot.jpg"
BOXES_PATH = "/home/raspberrypi/Documents/temp_boxes.json"
DB_PATH = "/home/raspberrypi/Documents/cpu_encodings.pickle"
MAP_PATH = "/home/raspberrypi/Documents/name_map.json"

def is_point_in_box(point, box):
    x, y = point
    xmin, ymin, xmax, ymax = box
    return xmin <= x <= xmax and ymin <= y <= ymax

def process_image():
    print("📸 Processing Screenshot with Spatial Matching...")
    
    # 1. Load Image and Boxes
    if not os.path.exists(SCREENSHOT_PATH) or not os.path.exists(BOXES_PATH):
        print("❌ Error: Missing screenshot or box data.")
        return
    
    frame = cv2.imread(SCREENSHOT_PATH)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    with open(BOXES_PATH, "r") as f:
        pose_boxes = json.load(f) # List of {"id": "0", "box": [xmin, ymin, xmax, ymax]}
    
    with open(DB_PATH, "rb") as f:
        data = pickle.load(f)

    # 2. Detect Faces
    face_locations = face_recognition.face_locations(rgb, model="hog")
    face_encodings = face_recognition.face_encodings(rgb, face_locations)

    current_map = {}
    if os.path.exists(MAP_PATH):
        with open(MAP_PATH, "r") as f:
            current_map = json.load(f)

    # 3. Match Faces to Bodies Spatially
    for (top, right, bottom, left), encoding in zip(face_locations, face_encodings):
        # Calculate face center
        face_center_x = (left + right) // 2
        face_center_y = (top + bottom) // 2
        
        matches = face_recognition.compare_faces(data["encodings"], encoding, tolerance=0.55)
        name = "Unknown"
        
        if True in matches:
            distances = face_recognition.face_distance(data["encodings"], encoding)
            best_idx = np.argmin(distances)
            if matches[best_idx]:
                name = data["names"][best_idx]
        
        # FIND WHICH POSE BOX THIS FACE IS INSIDE
        for item in pose_boxes:
            body_id = item["id"]
            box = item["box"]
            if is_point_in_box((face_center_x, face_center_y), box):
                current_map[body_id] = name
                print(f"✅ Body {body_id} mapped to Name: {name}")
                break

    # 4. Save Map
    with open(MAP_PATH, "w") as f:
        json.dump(current_map, f)

if __name__ == "__main__":
    process_image()