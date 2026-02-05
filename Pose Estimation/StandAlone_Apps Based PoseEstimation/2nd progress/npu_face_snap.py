import cv2, numpy as np, pickle, json, os, time
from hailo_platform import HEF, VDevice, HailoStreamInterface, InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams, FormatType

def identify_classroom():
    print("🔴 [NPU] Starting Face Scan...")
    
    # 1. Capture Frame
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()
    if not ret: return

    # 2. Init Hailo
    hef_path = "/home/raspberrypi/hailo-apps/resources/models/hailo8/arcface_mobilefacenet.hef"
    target = VDevice()
    hef = HEF(hef_path)
    conf = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
    group = target.configure(hef, conf)[0]
    
    in_params = InputVStreamParams.make(group, format_type=FormatType.FLOAT32)
    out_params = OutputVStreamParams.make(group, format_type=FormatType.FLOAT32)

    # 3. Load Database
    with open("/home/raspberrypi/Downloads/npu_encodings.pickle", "rb") as f:
        db = pickle.load(f)

    new_map = {}
    
    # 4. Detect Faces (We use a simple scan here; in a real classroom, we'd loop through body crops)
    # FOR THIS DEMO: We assume the first person is at index 0
    with group.activate():
        with InferVStreams(group, in_params, out_params) as pipe:
            # Crop middle of screen (where student is)
            ih, iw, _ = frame.shape
            crop = frame[ih//4:3*ih//4, iw//4:3*iw//4]
            f_input = cv2.resize(crop, (112, 112))
            f_input = cv2.cvtColor(f_input, cv2.COLOR_BGR2RGB).astype(np.float32)
            
            out = pipe.infer(np.expand_dims(f_input, axis=0))
            live_vec = list(out.values())[0][0]
            
            best_name, max_sim = "Unknown", 0
            for db_vec, db_name in zip(db['encodings'], db['names']):
                sim = np.dot(live_vec, db_vec) / (np.linalg.norm(live_vec) * np.linalg.norm(db_vec))
                if sim > max_sim: max_sim, best_name = sim, db_name
            
            if max_sim > 0.45:
                new_map["0"] = best_name
                print(f"✅ Identified student as: {best_name}")

    # 5. Save the Map
    with open("/home/raspberrypi/Downloads/name_map.json", "w") as f:
        json.dump(new_map, f)
    print("🏁 Snap complete. Name Map updated.")

if __name__ == "__main__":
    identify_classroom()