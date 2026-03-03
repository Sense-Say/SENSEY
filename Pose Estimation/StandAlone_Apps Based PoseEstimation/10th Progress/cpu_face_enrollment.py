import os
import cv2
import depthai as dai
import pickle
import threading
import numpy as np
import customtkinter as ctk
from PIL import Image
import face_recognition # 🚀 NEW: Using CPU library

# --- CONFIGURATION ---
NUM_PHOTOS_REQUIRED = 15 
PICKLE_PATH = "/home/raspberrypi/Documents/cpu_encodings.pickle"
# We still use the VPU for fast detection (finding the box)
FACE_DETECTOR_BLOB = "/home/raspberrypi/Documents/face_detector1.blob"

class CPUFaceEnrollApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SENSEY High-Res CPU Enrollment")
        self.geometry("1000x900")
        self.configure(bg="#2c3e50")
        
        # --- UI Setup ---
        self.video_label = ctk.CTkLabel(self, text="Initializing OAK-D 1080p Stream...")
        self.video_label.pack(pady=10, fill="both", expand=True)
        
        self.status_label = ctk.CTkLabel(self, text="Initializing Sensors...", font=("Arial", 16, "bold"))
        self.status_label.pack(pady=10)

        self.name_entry = ctk.CTkEntry(self, placeholder_text="Enter Student Name", width=250)
        self.name_entry.pack(pady=10)

        self.enroll_btn = ctk.CTkButton(self, text="Capture Sample (0/15)", command=self.capture_sample, state="disabled")
        self.enroll_btn.pack(pady=10)
        
        self.save_btn = ctk.CTkButton(self, text="Save to Database", command=self.save_db, state="disabled", fg_color="#2ecc71")
        self.save_btn.pack(pady=10)

        # --- Internal State ---
        self.running = True
        self.current_display_frame = None 
        self.current_highres_frame = None 
        self.face_box = None 
        self.database = {"encodings": [], "names": []}
        self.count = 0
        
        self.guides = [
            "Look STRAIGHT", "Look STRAIGHT", "Look STRAIGHT",
            "Turn LEFT slightly", "Turn LEFT slightly", "Turn LEFT slightly",
            "Turn RIGHT slightly", "Turn RIGHT slightly", "Turn RIGHT slightly",
            "Look UP slightly", "Look UP slightly",
            "Look DOWN slightly", "Look DOWN slightly",
            "Smile", "Neutral Expression"
        ]

        self.setup_pipeline()
        threading.Thread(target=self.hardware_worker, daemon=True).start()
        self.ui_update_loop()

    def setup_pipeline(self):
        self.pipeline = dai.Pipeline()

        # 1. Camera Node
        cam = self.pipeline.create(dai.node.ColorCamera)
        cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        cam.setVideoSize(1280, 720) 
        cam.setPreviewSize(640, 640)
        cam.setInterleaved(False)
        cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR) # Standard BGR
        cam.setFps(30)
        cam.initialControl.setManualFocus(0)

        # 2. Face Detector (VPU) - Retained for finding the box
        det_nn = self.pipeline.create(dai.node.MobileNetDetectionNetwork)
        det_nn.setBlobPath(FACE_DETECTOR_BLOB)
        det_nn.setConfidenceThreshold(0.5)
        
        manip_det = self.pipeline.create(dai.node.ImageManip)
        manip_det.initialConfig.setResize(300, 300)
        manip_det.initialConfig.setFrameType(dai.RawImgFrame.Type.BGR888p)

        # 3. XLink Outputs
        x_vid = self.pipeline.create(dai.node.XLinkOut); x_vid.setStreamName("video")
        x_isp = self.pipeline.create(dai.node.XLinkOut); x_isp.setStreamName("isp")
        x_det = self.pipeline.create(dai.node.XLinkOut); x_det.setStreamName("det")

        # --- LINKING ---
        cam.video.link(x_vid.input) 
        cam.isp.link(x_isp.input)   
        cam.preview.link(manip_det.inputImage)
        manip_det.out.link(det_nn.input)
        det_nn.out.link(x_det.input)

        try:
            self.device = dai.Device(self.pipeline)
            self.q_vid = self.device.getOutputQueue("video", 1, False)
            self.q_isp = self.device.getOutputQueue("isp", 1, False)
            self.q_det = self.device.getOutputQueue("det", 1, False)
        except Exception as e:
            print(f"❌ Hardware Error: {e}")

    def hardware_worker(self):
        while self.running:
            try:
                vid_pkt = self.q_vid.get()
                isp_pkt = self.q_isp.get()
                det_pkt = self.q_det.get()
                
                if vid_pkt is not None:
                    self.current_display_frame = vid_pkt.getCvFrame()
                    self.current_highres_frame = isp_pkt.getCvFrame()
                    
                    detections = det_pkt.detections
                    if len(detections) > 0:
                        face = detections[0]
                        ih, iw = self.current_display_frame.shape[:2]
                        self.face_box = [int(face.xmin*iw), int(face.ymin*ih), int(face.xmax*iw), int(face.ymax*ih)]
                        # Store detection normalization for high-res cropping later
                        self.last_det = face
                    else:
                        self.face_box = None
            except: pass

    def ui_update_loop(self):
        if self.current_display_frame is not None:
            draw_frame = self.current_display_frame.copy()
            if self.face_box:
                cv2.rectangle(draw_frame, (self.face_box[0], self.face_box[1]), 
                              (self.face_box[2], self.face_box[3]), (0, 255, 0), 2)
            
            # Display BGR -> RGB for GUI
            img = Image.fromarray(cv2.cvtColor(draw_frame, cv2.COLOR_BGR2RGB))
            self.video_label.configure(image=ctk.CTkImage(img, size=(800, 450)), text="")
        
        if self.count < NUM_PHOTOS_REQUIRED:
            if self.face_box is not None:
                self.status_label.configure(text=f"GUIDE: {self.guides[self.count]}", text_color="#2ecc71")
                self.enroll_btn.configure(state="normal")
            else:
                self.status_label.configure(text="STATUS: Finding Face...", text_color="#f39c12")
                self.enroll_btn.configure(state="disabled")
        
        self.after(20, self.ui_update_loop)

    def capture_sample(self):
        """🚀 REVISED: Performs CPU Encoding calculation on capture."""
        name = self.name_entry.get().strip().lower()
        if not name or self.face_box is None: return
        
        self.status_label.configure(text="Encoding on CPU...", text_color="#3498db")
        
        # 1. Use the high-res 1080p frame for encoding accuracy
        fh, fw = self.current_highres_frame.shape[:2]
        fx1, fy1 = int(self.last_det.xmin * fw), int(self.last_det.ymin * fh)
        fx2, fy2 = int(self.last_det.xmax * fw), int(self.last_det.ymax * fh)
        
        # Crop and convert to RGB for face_recognition library
        crop = self.current_highres_frame[max(0,fy1):min(fh,fy2), max(0,fx1):min(fw,fx2)]
        rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        
        # 2. Generate 128-d encoding on CPU
        # We tell the library the face is the whole crop to speed it up
        encodings = face_recognition.face_encodings(rgb_crop, [(0, rgb_crop.shape[1], rgb_crop.shape[0], 0)])
        
        if len(encodings) > 0:
            self.database["encodings"].append(encodings[0])
            self.database["names"].append(name)
            self.count += 1
            self.enroll_btn.configure(text=f"Capture ({self.count}/15)")
            
            if self.count >= NUM_PHOTOS_REQUIRED:
                self.save_btn.configure(state="normal")
                self.enroll_btn.configure(state="disabled")
                self.status_label.configure(text="Photos Complete. Click Save.", text_color="#2ecc71")
        else:
            self.status_label.configure(text="Error: Could not encode face. Try again.", text_color="#e74c3c")

    def save_db(self):
        # 🚀 STACKING: Load old data if it exists
        if os.path.exists(PICKLE_PATH):
            with open(PICKLE_PATH, "rb") as f:
                old = pickle.load(f)
                self.database["encodings"].extend(old["encodings"])
                self.database["names"].extend(old["names"])
        
        with open(PICKLE_PATH, "wb") as f:
            pickle.dump(self.database, f)
        self.status_label.configure(text=f"✅ Saved Database (CPU Mode)!", text_color="#2ecc71")

    def on_closing(self):
        self.running = False
        if hasattr(self, 'device'): self.device.close()
        self.destroy()

if __name__ == "__main__":
    app = CPUFaceEnrollApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()