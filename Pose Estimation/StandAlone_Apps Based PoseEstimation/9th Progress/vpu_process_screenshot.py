import cv2
import depthai as dai
import numpy as np
import pickle
import json
import os

# --- CONFIG ---
SCREENSHOT_PATH = "/home/raspberrypi/Documents/temp_screenshot.jpg"
BOXES_PATH = "/home/raspberrypi/Documents/temp_boxes.json"
DB_PATH = "/home/raspberrypi/Documents/vpu_encodings.pickle"
MAP_PATH = "/home/raspberrypi/Documents/name_map.json"
FACE_BLOB = "/home/raspberrypi/Documents/face_detector1.blob"
ARC_BLOB = "/home/raspberrypi/Documents/arcface.blob"

def is_point_in_box(point, box):
    x, y = point
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]

def process():
    print("📸 [VPU] Processing Screenshot with ArcFace...")
    if not os.path.exists(SCREENSHOT_PATH) or not os.path.exists(BOXES_PATH):
        print("❌ Error: Missing snapshot files.")
        return

    frame = cv2.imread(SCREENSHOT_PATH) # BGR
    with open(BOXES_PATH, "r") as f: pose_boxes = json.load(f)
    with open(DB_PATH, "rb") as f: db = pickle.load(f)
    
    # Setup VPU Pipeline for a single recognition pass
    pipeline = dai.Pipeline()
    xin = pipeline.create(dai.node.XLinkIn); xin.setStreamName("in")
    nn = pipeline.create(dai.node.NeuralNetwork); nn.setBlobPath(ARC_BLOB)
    xout = pipeline.create(dai.node.XLinkOut); xout.setStreamName("out")
    xin.out.link(nn.input); nn.out.link(xout.input)

    current_map = {}
    if os.path.exists(MAP_PATH):
        with open(MAP_PATH, "r") as f:
            try: current_map = json.load(f)
            except: current_map = {}

    # Detect faces in the screenshot using CPU (fast for 1 frame)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)

    with dai.Device(pipeline) as device:
        q_in = device.getInputQueue("in")
        q_out = device.getOutputQueue("out")

        for (x, y, w, h) in faces:
            face_center = (x + w//2, y + h//2)
            crop = frame[y:y+h, x:x+w]
            if crop.size == 0: continue
            
            # Pre-process for VPU (112x112 RGB)
            f_resized = cv2.resize(crop, (112, 112))
            f_rgb = cv2.cvtColor(f_resized, cv2.COLOR_BGR2RGB)
            
            img = dai.ImgFrame()
            img.setData(f_rgb.transpose(2, 0, 1).flatten())
            img.setType(dai.ImgFrame.Type.BGR888p)
            img.setWidth(112); img.setHeight(112)
            
            q_in.send(img)
            rec_data = q_out.get()
            live_vec = np.array(rec_data.getFirstLayerFp16())

            # Match Logic (Cosine Similarity)
            best_name, max_sim = "Unknown", 0
            for db_vec, db_name in zip(db['encodings'], db['names']):
                sim = np.dot(live_vec, db_vec) / (np.linalg.norm(live_vec) * np.linalg.norm(db_vec))
                if sim > max_sim: max_sim, best_name = sim, db_name
            
            if max_sim > 0.50: # Standard ArcFace Threshold
                for item in pose_boxes:
                    if is_point_in_box(face_center, item['box']):
                        current_map[str(item['id'])] = best_name
                        print(f"✅ Linked {best_name} (Sim: {max_sim:.2f})")

    with open(MAP_PATH, "w") as f: json.dump(current_map, f, indent=4)
    os.remove(SCREENSHOT_PATH); os.remove(BOXES_PATH)
    print("✅ VPU Identification Complete.")

if __name__ == "__main__":
    process()