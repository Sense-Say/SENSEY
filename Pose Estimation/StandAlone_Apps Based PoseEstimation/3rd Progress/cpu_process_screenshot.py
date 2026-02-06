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
    print("📸 Processing Screenshot with ID Reset Logic...")
    
    if not os.path.exists(SCREENSHOT_PATH) or not os.path.exists(BOXES_PATH):
        print("❌ Error: Missing files.")
        return
    
    frame = cv2.imread(SCREENSHOT_PATH)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # 1. Load Current Pose IDs
    try:
        with open(BOXES_PATH, "r") as f:
            pose_boxes = json.load(f) # List of {"id": "0", "box": [...]}
    except: return

    # 2. Load Existing Name Map
    current_map = {}
    if os.path.exists(MAP_PATH):
        try:
            with open(MAP_PATH, "r") as f:
                content = f.read().strip()
                if content: current_map = json.loads(content)
        except: current_map = {}

    # --- 3. THE RESET STEP ---
    # For every person currently visible in the Pose Monitor, 
    # we REMOVE their name from the map first.
    # This ensures that if they aren't recognized now, they become "Student X".
    for item in pose_boxes:
        body_id = str(item["id"])
        if body_id in current_map:
            print(f"   - Resetting ID {body_id} to 'Student' status...")
            del current_map[body_id]

    # 4. Load Face Database
    try:
        with open(DB_PATH, "rb") as f:
            data = pickle.load(f)
    except: 
        print("❌ Database Error.")
        return

    # 5. Detect and Recognize Faces
    face_locations = face_recognition.face_locations(rgb, model="hog")
    face_encodings = face_recognition.face_encodings(rgb, face_locations)

    print(f"   - Found {len(face_encodings)} faces to check.")

    for (top, right, bottom, left), encoding in zip(face_locations, face_encodings):
        face_center = ((left + right) // 2, (top + bottom) // 2)
        
        matches = face_recognition.compare_faces(data["encodings"], encoding, tolerance=0.55)
        name = "Unknown"
        
        if True in matches:
            distances = face_recognition.face_distance(data["encodings"], encoding)
            best_idx = np.argmin(distances)
            name = data["names"][best_idx]
        
        # 6. MATCH RECOGNIZED FACE TO POSE BOX
        if name != "Unknown":
            for item in pose_boxes:
                body_id = str(item["id"])
                box = item["box"]
                if is_point_in_box(face_center, box):
                    current_map[body_id] = name
                    print(f"   ✅ SUCCESS: ID {body_id} identified as {name}")
                    break

    # 7. Save the Cleaned/Updated Map
    with open(MAP_PATH, "w") as f:
        json.dump(current_map, f, indent=4)
    print(f"✅ Map Updated. Visible students without names will show as 'Student X'.")

if __name__ == "__main__":
    process_image()
