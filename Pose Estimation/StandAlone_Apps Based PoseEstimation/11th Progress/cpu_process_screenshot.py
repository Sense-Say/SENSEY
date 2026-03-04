import cv2, pickle, json, os, face_recognition, numpy as np

SCREENSHOT_PATH = "/home/raspberrypi/Documents/temp_screenshot.jpg"
BOXES_PATH = "/home/raspberrypi/Documents/temp_boxes.json"
DB_PATH = "/home/raspberrypi/Documents/cpu_encodings.pickle"
MAP_PATH = "/home/raspberrypi/Documents/name_map.json"

def is_point_in_box(point, box):
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]

def process():
    print("📸 [HYBRID] Processing 4:3 Spatial Snapshot...")
    if not os.path.exists(SCREENSHOT_PATH) or not os.path.exists(BOXES_PATH): return
    
    frame = cv2.imread(SCREENSHOT_PATH); rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    with open(BOXES_PATH, "r") as f: pose_boxes = json.load(f)
    
    try:
        with open(DB_PATH, "rb") as f: db = pickle.load(f)
    except: return

    # 🚀 LOAD AND RESET MAP
    current_map = {}
    if os.path.exists(MAP_PATH):
        try:
            with open(MAP_PATH, "r") as f:
                c = f.read().strip()
                if c: current_map = json.loads(c)
        except: pass
    
    # VITAL: Remove names for every ID the Pose AI currently sees.
    # This ensures that if the Face AI finds 0 faces, they revert to "Student X".
    for item in pose_boxes:
        bid = str(item["id"])
        if bid in current_map: 
            print(f"   - Resetting ID {bid} to default status...")
            del current_map[bid]

    # RECOGNITION
    boxes = face_recognition.face_locations(rgb, model="hog")
    encodings = face_recognition.face_encodings(rgb, boxes)
    all_possible = [] 
    
    for box, enc in zip(boxes, encodings):
        face_center = ((box[3] + box[1]) // 2, (box[0] + box[2]) // 2)
        matches = face_recognition.compare_faces(db["encodings"], enc, tolerance=0.50)
        
        if True in matches:
            dists = face_recognition.face_distance(db["encodings"], enc)
            best_idx = np.argmin(dists)
            name = db["names"][best_idx]
            
            for item in pose_boxes:
                if is_point_in_box(face_center, item['box']):
                    # Only map if the match is confident
                    all_possible.append((1.0 - dists[best_idx], str(item['id']), name))

    # GREEDY RESOLUTION
    all_possible.sort(key=lambda x: x[0], reverse=True)
    assigned_names = set()
    for conf, body_id, name in all_possible:
        if body_id not in current_map and name not in assigned_names:
            current_map[body_id] = name
            assigned_names.add(name)
            print(f"   ✅ SUCCESS: {name} recognized.")

    # SAVE AND PURGE
    with open(MAP_PATH, "w") as f: json.dump(current_map, f, indent=4)
    if os.path.exists(SCREENSHOT_PATH): os.remove(SCREENSHOT_PATH)
    if os.path.exists(BOXES_PATH): os.remove(BOXES_PATH)
    print("✅ Identification Complete.")

if __name__ == "__main__":
    process()