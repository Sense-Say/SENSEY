import cv2, pickle, json, os, face_recognition, numpy as np

# --- CONFIGURATION (UPDATED) ---
BASE_DIR = "/home/raspberrypi/Student Monitoring"
SCREENSHOT_PATH = f"{BASE_DIR}/temp_screenshot.jpg"
BOXES_PATH = f"{BASE_DIR}/temp_boxes.json"
DB_PATH = f"{BASE_DIR}/cpu_encodings.pickle"
MAP_PATH = f"{BASE_DIR}/name_map.json"

def is_point_in_box(point, box):
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]

def process():
    print("📸 [CPU] Processing 4:3 Spatial Snapshot...")
    if not os.path.exists(SCREENSHOT_PATH) or not os.path.exists(BOXES_PATH):
        print("⚠️ No snapshot to process.")
        return

    # 1. LOAD DATA
    frame = cv2.imread(SCREENSHOT_PATH)
    if frame is None: return
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    with open(BOXES_PATH, "r") as f: pose_boxes = json.load(f)
    
    try:
        with open(DB_PATH, "rb") as f: db = pickle.load(f)
    except:
        print("❌ Error: Encodings pickle not found.")
        return

    # 2. LOAD EXISTING MAP & RESET VISIBLE IDs
    current_map = {}
    if os.path.exists(MAP_PATH):
        try:
            with open(MAP_PATH, "r") as f:
                c = f.read().strip()
                if c: current_map = json.loads(c)
        except: pass
    
    for item in pose_boxes:
        bid = str(item["id"])
        if bid in current_map: del current_map[bid]

    # 3. RECOGNITION
    boxes = face_recognition.face_locations(rgb, model="hog")
    encodings = face_recognition.face_encodings(rgb, boxes)

    all_matches = [] 
    for box, enc in zip(boxes, encodings):
        face_center = ((box[3] + box[1]) // 2, (box[0] + box[2]) // 2)
        matches = face_recognition.compare_faces(db["encodings"], enc, tolerance=0.50)
        
        if True in matches:
            dists = face_recognition.face_distance(db["encodings"], enc)
            best_idx = np.argmin(dists)
            name = db["names"][best_idx]
            
            for item in pose_boxes:
                if is_point_in_box(face_center, item['box']):
                    all_matches.append((1.0 - dists[best_idx], str(item['id']), name))

    # 4. GREEDY RESOLUTION
    all_matches.sort(key=lambda x: x[0], reverse=True)
    assigned_names = set()
    for conf, body_id, name in all_matches:
        if body_id not in current_map and name not in assigned_names:
            current_map[body_id] = name
            assigned_names.add(name)
            print(f"   ✅ SUCCESS: {name} recognized.")

    # 5. SAVE AND CLEANUP
    with open(MAP_PATH, "w") as f: json.dump(current_map, f, indent=4)
    if os.path.exists(SCREENSHOT_PATH): os.remove(SCREENSHOT_PATH)
    if os.path.exists(BOXES_PATH): os.remove(BOXES_PATH)
    print("✅ Identification Complete.")

if __name__ == "__main__":
    process()