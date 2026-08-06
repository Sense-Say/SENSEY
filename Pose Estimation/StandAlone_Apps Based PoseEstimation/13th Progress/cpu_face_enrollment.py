import os, cv2, depthai as dai, pickle, threading, face_recognition, customtkinter as ctk, subprocess
from PIL import Image
from imutils import paths

# --- CONFIGURATION ---
PIPER_EXE = "/home/raspberrypi/TTS-STT-AUDIO/piper/piper"
PIPER_MODEL = "/home/raspberrypi/TTS-STT-AUDIO/en_US-lessac-medium.onnx"
BASE_DIR = "/home/raspberrypi/Student Monitoring"
PICKLE_PATH = f"{BASE_DIR}/cpu_encodings.pickle"
DATASET_PATH = f"{BASE_DIR}/cpu_dataset"

class CPUEnrollApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SENSEY Voice-Guided Enrollment")
        self.geometry("800x850")
        self.configure(bg="#2c3e50")
        
        self.video_label = ctk.CTkLabel(self, text="Camera Loading...")
        self.video_label.pack(pady=10, fill="both", expand=True)
        self.status_label = ctk.CTkLabel(self, text="Initializing...", font=("Arial", 16, "bold"))
        self.status_label.pack(pady=10)
        
        self.name_entry = ctk.CTkEntry(self, placeholder_text="Student Name", width=250)
        self.name_entry.pack(pady=10)
        
        self.btn = ctk.CTkButton(self, text="Capture Photo (0/5)", command=self.capture)
        self.btn.pack(pady=10)
        
        self.train_btn = ctk.CTkButton(self, text="Generate Encodings", command=self.start_train, state="disabled")
        self.train_btn.pack(pady=10)

        self.running, self.current_frame, self.count = True, None, 0
        self.guides = [
            "Please look straight at the camera.",
            "Now, turn your head slightly to the left.",
            "Now, turn your head slightly to the right.",
            "Look upward slightly.",
            "Finally, look slightly downward ."
        ]
        
        self.setup_oak()
        threading.Thread(target=self.worker, daemon=True).start()
        
        # Initial Voice Welcome
        self.speak("Face enrollment system is ready. Please enter the student name and look straight ahead.")
        self.loop()

    def speak(self, text):
        def _run():
            try:
                cmd = f'echo "{text}" | {PIPER_EXE} --model {PIPER_MODEL} --length_scale 1.0 --output-raw | aplay -r 22050 -f S16_LE -t raw'
                subprocess.run(cmd, shell=True)
            except: pass
        threading.Thread(target=_run, daemon=True).start()

    def setup_oak(self):
        pipeline = dai.Pipeline()
        cam = pipeline.create(dai.node.ColorCamera)
        cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_12_MP)
        cam.setIspScale(1, 3)
        cam.setInterleaved(False)
        cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
        cam.initialControl.setManualFocus(0)
        xout = pipeline.create(dai.node.XLinkOut); xout.setStreamName("rgb")
        cam.isp.link(xout.input)
        self.device = dai.Device(pipeline)
        self.q_rgb = self.device.getOutputQueue("rgb", 1, False)

    def worker(self):
        while self.running: self.current_frame = self.q_rgb.get().getCvFrame()

    def loop(self):
        if self.current_frame is not None:
            img = Image.fromarray(cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB))
            self.video_label.configure(image=ctk.CTkImage(img, size=(640, 480)), text="")
        self.after(15, self.loop)

    def capture(self):
        name = self.name_entry.get().strip().lower()
        if not name:
            self.speak("Please enter a name before capturing.")
            return
            
        path = os.path.join(DATASET_PATH, name)
        os.makedirs(path, exist_ok=True)
        cv2.imwrite(os.path.join(path, f"{name}_{self.count}.png"), self.current_frame)
        
        self.count += 1
        self.btn.configure(text=f"Capture ({self.count}/5)")
        
        if self.count < 5:
            self.speak(f"Captured. {self.guides[self.count]}")
        else:
            self.speak("All photos captured. Please click the generate encodings button.")
            self.train_btn.configure(state="normal")
            self.btn.configure(state="disabled")

    def start_train(self):
        self.speak("Training started. Please wait a few moments.")
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
                knownEncodings.append(enc); knownNames.append(name)
        
        with open(PICKLE_PATH, "wb") as f:
            pickle.dump({"encodings": knownEncodings, "names": knownNames}, f)
        
        self.speak("Training complete. Student has been added to the database.")
        self.after(0, lambda: self.status_label.configure(text="✅ DATABASE UPDATED", text_color="#2ecc71"))

    def on_closing(self):
        self.running = False; self.device.close(); self.destroy()

if __name__ == "__main__":
    app = CPUEnrollApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()