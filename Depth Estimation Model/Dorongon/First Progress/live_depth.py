import cv2
import numpy as np
import onnxruntime as ort
import time

# --- CONFIGURATION ---
# 1. Check this filename matches your new file exactly
MODEL_PATH = "depth_anything_v2_vits.onnx" 

# 2. Input size. 
# 252 is good quality but might be slow (2-3 FPS).
# Change to 196 or 168 if it's too laggy.
INPUT_SIZE = 252

# 3. Camera ID (0 is usually the default USB/Pi Cam)
CAM_ID = 0 

class DepthEstimator:
    def __init__(self, model_path):
        print(f"Loading model from {model_path}...")
        self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        print("Model loaded successfully!")

    def infer(self, frame):
        # Resize to model input size
        h_orig, w_orig = frame.shape[:2]
        image = cv2.resize(frame, (INPUT_SIZE, INPUT_SIZE))
        
        # Preprocessing (Standard ImageNet normalization)
        # 1. Convert to float32 first
        image = image.astype(np.float32) / 255.0
        
        # 2. Define mean and std explicitly as float32 to prevent auto-promotion to double
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        
        # 3. Perform math (result stays float32)
        image = (image - mean) / std
        
        # Transpose to Channel-First (CHW) and add Batch dimension
        image = image.transpose(2, 0, 1)[None, :, :, :]

        # Run Inference
        depth = self.session.run(None, {self.input_name: image})[0]
        
        # Post-processing
        depth = depth[0, :, :]
        depth_min, depth_max = depth.min(), depth.max()
        depth_normalized = (depth - depth_min) / (depth_max - depth_min) * 255.0
        depth_normalized = depth_normalized.astype(np.uint8)
        
        # Resize back to original frame width/height
        depth_colored = cv2.resize(depth_normalized, (w_orig, h_orig), interpolation=cv2.INTER_LINEAR)
        
        # Apply Color Map
        depth_colored = cv2.applyColorMap(depth_colored, cv2.COLORMAP_INFERNO)
        
        return depth_colored

def main():
    cap = cv2.VideoCapture(CAM_ID)
    
    # Lower camera resolution for speed
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    try:
        estimator = DepthEstimator(MODEL_PATH)
    except Exception as e:
        print(f"Error loading ONNX model: {e}")
        return

    print("Starting video. Press 'q' to quit.")
    
    fps_start = time.time()
    frames = 0
    fps = 0

    while True:
        ret, frame = cap.read()
        if not ret: break

        # Calculate Depth
        depth_map = estimator.infer(frame)

        # FPS Counter
        frames += 1
        if frames >= 5:
            fps = frames / (time.time() - fps_start)
            frames = 0
            fps_start = time.time()

        # Stack images side-by-side
        combined = np.hstack((frame, depth_map))
        
        cv2.putText(combined, f"FPS: {fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow('Depth Anything V2 (RPi)', combined)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()