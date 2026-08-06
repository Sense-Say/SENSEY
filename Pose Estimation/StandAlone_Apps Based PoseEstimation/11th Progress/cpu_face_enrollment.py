import os
import cv2
import depthai as dai
import pickle
import threading
import face_recognition
import customtkinter as ctk
from PIL import Image
from imutils import paths
import numpy as np

# --- CONFIGURATION ---
NUM_PHOTOS_REQUIRED = 5 
PICKLE_PATH = "/home/raspberrypi/Documents/cpu_encodings.pickle"
DATASET_PATH = "/home/raspberrypi/Documents/cpu_dataset"

class CPUEnrollApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SENSEY CPU Enrollment (OAK-D Calibrated)")
        self.geometry("800x850")
        self.configure(bg="#2c3e50")
        
        # --- UI SETUP ---
        self.video_label = ctk.CTkLabel(self, text="Init OAK-D...")
        self.video_label.pack(pady=10, fill="both", expand=True)
        
        self.status_label = ctk.CTkLabel(self, text="Ready", font=("Arial", 16, "bold"), text_color="#f39c12")
        self.status_label.pack(pady=10)
        
        self.name_entry = ctk.CTkEntry(self, placeholder_text="Enter Student Name", width=250)
        self.name_entry.pack(pady=10)
        
        self.btn = ctk.CTkButton(self, text="Capture Photo (0/5)", command=self.capture)
        self.btn.pack(pady=10)
        
        self.train_btn = ctk.CTkButton(self, text="Generate CPU Encodings", command=self.start_train, state="disabled", fg_color="#2ecc71")
        self.train_btn.pack(pady=10)

        # --- CAMERA STATE ---
        self.running = True
        self.current_frame = None 
        self.count = 0
        
        self.setup_oak()
        threading.Thread(target=self.worker, daemon=True).start()
        self.loop()

    def setup_oak(self):
        self.pipeline = dai.Pipeline()
        cam = self.pipeline.create(dai.node.ColorCamera)
        # 🚀 4:3 Calibration Setup
        cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_12_MP)
        cam.setIspScale(1, 3) # Result: 1344x1008
        cam.setInterleaved(False)
        cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
        cam.initialControl.setManualFocus(0) # 🚀 Match Monitor Focus
        cam.setBoardSocket(dai.CameraBoardSocket.CAM_A)

        xout = self.pipeline.create(dai.node.XLinkOut)
        xout.setStreamName("rgb")
        cam.isp.link(xout.input)
        
        self.device = dai.Device(self.pipeline)
        self.q_rgb = self.device.getOutputQueue("rgb", 1, False)

    def worker(self):
        while self.running:
            try:
                pkt = self.q_rgb.get()
                if pkt:
                    self.current_frame = pkt.getCvFrame()
            except: break

    def loop(self):
        if not self.running: return
        if self.current_frame is not None:
            # Display BGR -> RGB conversion for GUI
            img_rgb = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(img_rgb)
            ctk_img = ctk.CTkImage(light_image=img, size=(640, 480))
            self.video_label.configure(image=ctk_img, text="")
        self.after(15, self.loop)

    def capture(self):
        name = self.name_entry.get().strip().lower()
        if not name or self.current_frame is None: return
        path = os.path.join(DATASET_PATH, name)
        os.makedirs(path, exist_ok=True)
        # Save raw BGR
        cv2.imwrite(os.path.join(path, f"{name}_{self.count}.png"), self.current_frame)
        self.count += 1
        self.btn.configure(text=f"Capture ({self.count}/5)")
        if self.count >= NUM_PHOTOS_REQUIRED:
            self.status_label.configure(text="Photos Complete! Click Generate.", text_color="#2ecc71")
            self.train_btn.configure(state="normal")
            self.btn.configure(state="disabled")

    def start_train(self):
        self.train_btn.configure(state="disabled")
        self.status_label.configure(text="Encoding... (Pi 5 CPU mode)", text_color="#3498db")
        threading.Thread(target=self.run_train, daemon=True).start()

    def run_train(self):
        imagePaths = list(paths.list_images(DATASET_PATH))
        knownEncodings, knownNames = [], []
        for imagePath in imagePaths:
            name = imagePath.split(os.path.sep)[-2]
            image = cv2.imread(imagePath)
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            boxes = face_recognition.face_locations(rgb, model="hog")
            encodings = face_recognition.face_encodings(rgb, boxes)
            for enc in encodings:
                knownEncodings.append(enc)
                knownNames.append(name)
        
        # Stacking logic
        if os.path.exists(PICKLE_PATH):
            with open(PICKLE_PATH, "rb") as f:
                old = pickle.load(f)
                knownEncodings.extend(old["encodings"])
                knownNames.extend(old["names"])

        with open(PICKLE_PATH, "wb") as f:
            pickle.dump({"encodings": knownEncodings, "names": knownNames}, f)
            
        # 🚀 FIX: Use self.after instead of self.root.after
        self.after(0, lambda: self.status_label.configure(text="✅ DATABASE UPDATED", text_color="#2ecc71"))

    def on_closing(self):
        self.running = False
        self.device.close()
        self.destroy()

if __name__ == "__main__":

    app = CPUEnrollApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()