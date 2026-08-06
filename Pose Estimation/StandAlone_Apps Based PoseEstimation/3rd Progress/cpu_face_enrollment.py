import os
import cv2
import pickle
import threading
import face_recognition
import customtkinter as ctk
from PIL import Image
from imutils import paths

# --- CONFIGURATION ---
NUM_PHOTOS_REQUIRED = 5
# Save dataset inside Documents folder
DATASET_PATH = "/home/raspberrypi/Documents/cpu_dataset" 
# Save database to Documents
PICKLE_PATH = "/home/raspberrypi/Documents/cpu_encodings.pickle"

# --- COLOR PALETTE ---
COLOR_PRIMARY_BLUE = "#007bff"
COLOR_DARK_BLUE = "#2c3e50"
COLOR_BACKGROUND = "#1f2b38"
COLOR_TEXT = "#ecf0f1"
COLOR_SUCCESS = "#2ecc71"
COLOR_ERROR = "#e74c3c"
COLOR_WARNING = "#f39c12"

class CPUFaceEnrollApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CPU Face Enrollment (Documents)")
        self.root.geometry("800x800")
        self.root.configure(bg=COLOR_DARK_BLUE)
        
        # --- UI SETUP ---
        header = ctk.CTkFrame(root, corner_radius=0, fg_color=COLOR_PRIMARY_BLUE)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Robust Face Database Creator", text_color=COLOR_TEXT, font=("Arial", 20, "bold")).pack(pady=10)

        main_frame = ctk.CTkFrame(root, fg_color=COLOR_DARK_BLUE)
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        self.video_label = ctk.CTkLabel(main_frame, text="", fg_color=COLOR_BACKGROUND)
        self.video_label.pack(pady=10, fill="both", expand=True)

        self.status_label = ctk.CTkLabel(main_frame, text="Status: Ready", text_color=COLOR_WARNING)
        self.status_label.pack(pady=10, fill="x")

        footer = ctk.CTkFrame(root, corner_radius=0, fg_color=COLOR_BACKGROUND)
        footer.pack(fill="x", side="bottom")
        
        self.name_entry = ctk.CTkEntry(footer, placeholder_text="Enter Name", width=250)
        self.name_entry.pack(pady=10)

        btn_frame = ctk.CTkFrame(footer, fg_color="transparent")
        btn_frame.pack(pady=10)

        self.enroll_btn = ctk.CTkButton(btn_frame, text=f"Capture (0/{NUM_PHOTOS_REQUIRED})", command=self.capture_photo, fg_color=COLOR_PRIMARY_BLUE)
        self.enroll_btn.pack(side="left", padx=10)
        
        self.train_btn = ctk.CTkButton(btn_frame, text="Train CPU Model", command=self.start_training, fg_color=COLOR_SUCCESS, state="disabled")
        self.train_btn.pack(side="left", padx=10)

        # --- CAMERA ---
        self.cap = cv2.VideoCapture(0)
        self.running = True
        self.current_count = 0
        
        self.update_feed()

    def update_status(self, text, color):
        self.status_label.configure(text=f"Status: {text}", text_color=color)

    def update_feed(self):
        if not self.running: return
        ret, frame = self.cap.read()
        if ret:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            ctk_img = ctk.CTkImage(light_image=img, size=(640, 480))
            self.video_label.configure(image=ctk_img)
        self.root.after(15, self.update_feed)

    def capture_photo(self):
        name = self.name_entry.get().strip().lower()
        if not name:
            self.update_status("Enter a name!", COLOR_ERROR)
            return
            
        path = os.path.join(DATASET_PATH, name)
        os.makedirs(path, exist_ok=True)
        
        ret, frame = self.cap.read()
        if ret:
            cv2.imwrite(os.path.join(path, f"{name}_{self.current_count}.png"), frame)
            self.current_count += 1
            self.enroll_btn.configure(text=f"Capture ({self.current_count}/{NUM_PHOTOS_REQUIRED})")
            
            if self.current_count >= NUM_PHOTOS_REQUIRED:
                self.update_status("Photos Done. Click Train.", COLOR_SUCCESS)
                self.enroll_btn.configure(state="disabled")
                self.train_btn.configure(state="normal")

    def start_training(self):
        self.update_status("Training CPU Model...", COLOR_WARNING)
        threading.Thread(target=self.train_model, daemon=True).start()

    def train_model(self):
        print("[CPU] Starting training...")
        if not os.path.exists(DATASET_PATH): return
        
        imagePaths = list(paths.list_images(DATASET_PATH))
        knownEncodings = []
        knownNames = []

        for (i, imagePath) in enumerate(imagePaths):
            name = imagePath.split(os.path.sep)[-2]
            image = cv2.imread(imagePath)
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            boxes = face_recognition.face_locations(rgb, model="hog")
            encodings = face_recognition.face_encodings(rgb, boxes)

            for encoding in encodings:
                knownEncodings.append(encoding)
                knownNames.append(name)

        data = {"encodings": knownEncodings, "names": knownNames}
        with open(PICKLE_PATH, "wb") as f:
            pickle.dump(data, f)
            
        self.root.after(0, lambda: self.update_status(f"Saved to {PICKLE_PATH}", COLOR_SUCCESS))
        self.current_count = 0
        self.enroll_btn.configure(state="normal", text=f"Capture (0/{NUM_PHOTOS_REQUIRED})")

    def on_closing(self):
        self.running = False
        self.cap.release()
        self.root.destroy()

if __name__ == "__main__":
    root = ctk.CTk()
    app = CPUFaceEnrollApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloo
