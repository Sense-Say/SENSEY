import cv2
import depthai as dai
import numpy as np
import pickle
import json
import os
import face_recognition

# --- CONFIG ---
SCREENSHOT_PATH = "/home/raspberrypi/Documents/temp_screenshot.jpg"
BOXES_PATH = "/home/raspberrypi/Documents/temp_boxes.json"
DB_PATH = "/home/raspberrypi/Documents/cpu_encodings.pickle"
MAP_PATH = "/home/raspberrypi/Documents/name_map.json"
FACE_BLOB = "/home/raspberrypi/Documents/face_detector1.blob"

# Stricter tolerance for 128-d CPU encodings
TOLERANCE = 0.50 

def is_point_in_box(point, box):
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]

def process():
    print("📸 [HYBRID] Processing 1080p Snapshot (VPU Detect + CPU Recog)...")
    
    if not os.path.exists(SCREENSHOT_PATH) or not os.path.exists(BOXES_PATH):
        print("❌ Error: Missing snapshot files.")
        return

    # 1. LOAD DATA
    full_frame = cv2.imread(SCREENSHOT_PATH) # 1080p BGR
    if full_frame is None: return
    
    with open(BOXES_PATH, "r") as f: pose_boxes = json.load(f)
    with open(DB_PATH, "rb") as f: db = pickle.load(f)

    # 2. SETUP DETECTION PIPELINE
    pipeline = dai.Pipeline()
    xin_det = pipeline.create(dai.node.XLinkIn); xin_det.setStreamName("in_det")
    det_nn = pipeline.create(dai.node.MobileNetDetectionNetwork)
    det_nn.setBlobPath(FACE_BLOB)
    det_nn.setConfidenceThreshold(0.5)
    xout_det = pipeline.create(dai.node.XLinkOut); xout_det.setStreamName("out_det")
    xin_det.out.link(det_nn.input); det_nn.out.link(xout_det.input)

    # Temporary storage for Greedy Match logic
    all_possible_matches = [] 

    with dai.Device(pipeline) as device:
        q_in = device.getInputQueue("in_det")
        q_out = device.getOutputQueue("out_det")

        # Step A: Prepare 300x300 for VPU (This bypasses the 5MB limit)
        det_img = cv2.resize(full_frame, (300, 300))
        img_msg = dai.ImgFrame()
        img_msg.setData(det_img.transpose(2, 0, 1).flatten())
        img_msg.setType(dai.ImgFrame.Type.BGR888p)
        img_msg.setWidth(300); img_msg.setHeight(300)
        q_in.send(img_msg)
        
        detections = q_out.get().detections
        print(f"   - VPU found {len(detections)} faces. Analyzing on CPU...")

        # Step B: CPU Recognition on 1080p Crops
        for face in detections:
            ih, iw = full_frame.shape[:2]
            # Convert normalized VPU coords to 1080p pixel coords
            x1, y1 = int(face.xmin * iw), int(face.ymin * ih)
            x2, y2 = int(face.xmax * iw), int(face.ymax * ih)
            face_center = ((x1 + x2) // 2, (y1 + y2) // 2)
            
            # Crop from the high-res 1080p image in RAM
            crop = full_frame[max(0,y1):min(ih,y2), max(0,x1):min(iw,x2)]
            if crop.size == 0: continue
            
            # CPU Recognition
            rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            encs = face_recognition.face_encodings(rgb_crop, [(0, rgb_crop.shape[1], rgb_crop.shape[0], 0)])
            
            if len(encs) > 0:
                live_enc = encs[0]
                matches = face_recognition.compare_faces(db["encodings"], live_enc, tolerance=TOLERANCE)
                if True in matches:
                    distances = face_recognition.face_distance(db["encodings"], live_enc)
                    best_idx = np.argmin(distances)
                    best_name = db["names"][best_idx]
                    conf = 1.0 - distances[best_idx]
                    
                    # Link to Pose Box Spatially
                    for item in pose_boxes:
                        if is_point_in_box(face_center, item['box']):
                            all_possible_matches.append((conf, str(item['id']), best_name))
                            break

    # --- 3. GREEDY IDENTITY RESOLUTION ---
    all_possible_matches.sort(key=lambda x: x[0], reverse=True)

    # Reset current map for IDs in view
    final_map = {}
    if os.path.exists(MAP_PATH):
        try:
            with open(MAP_PATH, "r") as f: final_map = json.load(f)
        except: pass
    for item in pose_boxes:
        bid = str(item["id"])
        if bid in final_map: del final_map[bid]

    assigned_names = set()
    for conf, body_id, name in all_possible_matches:
        if body_id not in final_map and name not in assigned_names:
            final_map[body_id] = name
            assigned_names.add(name)
            print(f"   ✅ ASSIGNED: {name} to Body {body_id} (Score: {conf:.2f})")

    # 4. SAVE AND CLEANUP
    with open(MAP_PATH, "w") as f:
        json.dump(final_map, f, indent=4)
    
    if os.path.exists(SCREENSHOT_PATH): os.remove(SCREENSHOT_PATH)
    if os.path.exists(BOXES_PATH): os.remove(BOXES_PATH)
    print("✅ Hybrid Identification Complete.")

if __name__ == "__main__":
    process()