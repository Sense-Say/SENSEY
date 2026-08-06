import os
import cv2
import depthai as dai
import pickle
import threading
import numpy as np
import customtkinter as ctk
from PIL import Image

# --- CONFIGURATION ---
NUM_PHOTOS_REQUIRED = 15 
PICKLE_PATH = "/home/raspberrypi/Documents/vpu_encodings.pickle"
FACE_DETECTOR_BLOB = "/home/raspberrypi/Documents/face_detector1.blob"
ARC_BLOB = "/home/raspberrypi/Documents/arcface.blob"

class VPUFaceEnrollApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SENSEY High-Res VPU Enrollment")
        self.geometry("1000x900")
        self.configure(bg="#2c3e50")
        
        # --- UI Setup ---
        self.video_label = ctk.CTkLabel(self, text="Initializing OAK-D 1080p Stream...")
        self.video_label.pack(pady=10, fill="both", expand=True)
        
        self.status_label = ctk.CTkLabel(self, text="Initializing Sensors...", font=("Arial", 16, "bold"))
        self.status_label.pack(pady=10)

        self.name_entry = ctk.CTkEntry(self, placeholder_text="Enter Student Name", width=250)
        self.name_entry.pack(pady=10)

        self.enroll_btn = ctk.CTkButton(self, text="Capture Vector (0/15)", command=self.capture_vector, state="disabled")
        self.enroll_btn.pack(pady=10)
        
        self.save_btn = ctk.CTkButton(self, text="Save to Database", command=self.save_db, state="disabled", fg_color="#2ecc71")
        self.save_btn.pack(pady=10)

        # --- Internal State ---
        self.running = True
        self.current_display_frame = None # 720p for the teacher
        self.current_highres_frame = None # 1080p for the AI
        self.latest_vector = None
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
        # 🚀 THE SPLIT: Video is 720p (Display), Preview is 640x640 (AI Detection)
        # We also use the ISP output for the raw 1080p capture math.
        cam.setVideoSize(1280, 720) 
        cam.setPreviewSize(640, 640)
        cam.setInterleaved(False)
        cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
        cam.setFps(30)
        cam.initialControl.setManualFocus(0) # INFINITY FOCUS LOCK

        # 2. Face Detector (VPU)
        det_nn = self.pipeline.create(dai.node.MobileNetDetectionNetwork)
        det_nn.setBlobPath(FACE_DETECTOR_BLOB)
        det_nn.setConfidenceThreshold(0.5)
        
        # We need a small resizer for the 300x300 detector
        manip_det = self.pipeline.create(dai.node.ImageManip)
        manip_det.initialConfig.setResize(300, 300)
        manip_det.initialConfig.setFrameType(dai.RawImgFrame.Type.BGR888p)

        # 3. ArcFace Recognizer (VPU)
        rec_nn = self.pipeline.create(dai.node.NeuralNetwork)
        rec_nn.setBlobPath(ARC_BLOB)

        # 4. XLink Outputs
        x_vid = self.pipeline.create(dai.node.XLinkOut); x_vid.setStreamName("video") # 720p
        x_isp = self.pipeline.create(dai.node.XLinkOut); x_isp.setStreamName("isp")   # 1080p
        x_det = self.pipeline.create(dai.node.XLinkOut); x_det.setStreamName("det")
        
        x_rec_in = self.pipeline.create(dai.node.XLinkIn); x_rec_in.setStreamName("rec_in")
        x_rec_out = self.pipeline.create(dai.node.XLinkOut); x_rec_out.setStreamName("rec_out")

        # --- LINKING ---
        cam.video.link(x_vid.input) # 720p for GUI
        cam.isp.link(x_isp.input)   # 1080p for Face Math
        
        cam.preview.link(manip_det.inputImage)
        manip_det.out.link(det_nn.input)
        det_nn.out.link(x_det.input)
        
        x_rec_in.out.link(rec_nn.input)
        rec_nn.out.link(x_rec_out.input)

        try:
            self.device = dai.Device(self.pipeline)
            self.q_vid = self.device.getOutputQueue("video", 1, False)
            self.q_isp = self.device.getOutputQueue("isp", 1, False)
            self.q_det = self.device.getOutputQueue("det", 1, False)
            self.q_rec_in = self.device.getInputQueue("rec_in")
            self.q_rec_out = self.device.getOutputQueue("rec_out", 1, False)
        except Exception as e:
            print(f"❌ Hardware Error: {e}")

    def hardware_worker(self):
        while self.running:
            try:
                # 1. Get Frames and Detections
                vid_pkt = self.q_vid.get()
                isp_pkt = self.q_isp.get()
                det_pkt = self.q_det.get()
                
                if vid_pkt is not None:
                    # 720p for UI
                    self.current_display_frame = vid_pkt.getCvFrame()
                    # 1080p for AI
                    self.current_highres_frame = isp_pkt.getCvFrame()
                    
                    # 2. Process Detection
                    detections = det_pkt.detections
                    if len(detections) > 0:
                        face = detections[0]
                        # Map coordinates to the 720p frame for the UI box
                        ih, iw = self.current_display_frame.shape[:2]
                        x1, y1 = int(face.xmin * iw), int(face.ymin * ih)
                        x2, y2 = int(face.xmax * iw), int(face.ymax * ih)
                        self.face_box = [x1, y1, x2, y2]
                        
                        # 🚀 CROP FROM 1080p for ArcFace accuracy
                        fh, fw = self.current_highres_frame.shape[:2]
                        fx1, fy1 = int(face.xmin * fw), int(face.ymin * fh)
                        fx2, fy2 = int(face.xmax * fw), int(face.ymax * fh)
                        
                        crop = self.current_highres_frame[max(0,fy1):min(fh,fy2), max(0,fx1):min(fw,fx2)]
                        
                        if crop.size > 0:
                            # Pre-process for VPU math
                            f_resized = cv2.resize(crop, (112, 112))
                            f_rgb = cv2.cvtColor(f_resized, cv2.COLOR_BGR2RGB)
                            
                            img_msg = dai.ImgFrame()
                            img_msg.setData(f_rgb.transpose(2, 0, 1).flatten())
                            img_msg.setType(dai.ImgFrame.Type.BGR888p)
                            img_msg.setWidth(112); img_msg.setHeight(112)
                            
                            self.q_rec_in.send(img_msg)
                            rec_data = self.q_rec_out.get()
                            self.latest_vector = np.array(rec_data.getFirstLayerFp16())
                    else:
                        self.face_box = None
                        self.latest_vector = None
            except: pass

    def ui_update_loop(self):
        if self.current_display_frame is not None:
            draw_frame = self.current_display_frame.copy()
            if self.face_box and self.latest_vector is not None:
                cv2.rectangle(draw_frame, (self.face_box[0], self.face_box[1]), 
                              (self.face_box[2], self.face_box[3]), (0, 255, 0), 2)
            
            # Show BGR -> RGB for GUI
            img = Image.fromarray(cv2.cvtColor(draw_frame, cv2.COLOR_BGR2RGB))
            self.video_label.configure(image=ctk.CTkImage(img, size=(800, 450)), text="")
        
        if self.count < NUM_PHOTOS_REQUIRED:
            if self.latest_vector is not None:
                self.status_label.configure(text=f"GUIDE: {self.guides[self.count]}", text_color="#2ecc71")
                self.enroll_btn.configure(state="normal")
            else:
                self.status_label.configure(text="STATUS: Finding Face...", text_color="#f39c12")
                self.enroll_btn.configure(state="disabled")
        
        self.after(20, self.ui_update_loop)

    def capture_vector(self):
        name = self.name_entry.get().strip().lower()
        if not name or self.latest_vector is None: return
        
        self.database["encodings"].append(self.latest_vector)
        self.database["names"].append(name)
        self.count += 1
        self.enroll_btn.configure(text=f"Capture ({self.count}/15)")
        self.latest_vector = None 
        
        if self.count >= NUM_PHOTOS_REQUIRED:
            self.save_btn.configure(state="normal")
            self.enroll_btn.configure(state="disabled")
            self.status_label.configure(text="Capture Complete! Click Save.", text_color="#2ecc71")

    def save_db(self):
        # 🚀 STACKING: Load old data if it exists
        if os.path.exists(PICKLE_PATH):
            with open(PICKLE_PATH, "rb") as f:
                old = pickle.load(f)
                self.database["encodings"].extend(old["encodings"])
                self.database["names"].extend(old["names"])
        
        with open(PICKLE_PATH, "wb") as f:
            pickle.dump(self.database, f)
        self.status_label.configure(text=f"✅ Saved Database to Documents!", text_color="#2ecc71")

    def on_closing(self):
        self.running = False
        if hasattr(self, 'device'): self.device.close()
        self.destroy()

if __name__ == "__main__":
    app = VPUFaceEnrollApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()