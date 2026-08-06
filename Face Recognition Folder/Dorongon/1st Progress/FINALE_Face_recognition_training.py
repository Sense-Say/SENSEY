import os
import cv2
import pickle
import threading
from datetime import datetime
from imutils import paths
import face_recognition
import customtkinter as ctk
from PIL import Image
from picamera2 import Picamera2

# --- Color Palette from the design ---
COLOR_PRIMARY_BLUE = "#007bff"  # A standard bright blue for buttons and highlights
COLOR_DARK_BLUE = "#2c3e50"     # A dark, professional blue for the main background
COLOR_BACKGROUND = "#1f2b38"    # A slightly lighter dark blue for frames
COLOR_TEXT = "#ecf0f1"          # A light, almost white color for text
COLOR_SUCCESS = "#2ecc71"       # Green for success messages
COLOR_ERROR = "#e74c3c"         # Red for error messages
COLOR_WARNING = "#f39c12"       # Orange for warning/in-progress messages
COLOR_BUTTON_HOVER = "#0056b3"  # Darker blue for button hover effect

class ThemedFaceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Face Recognition System")
        self.root.geometry("800x780")
        self.root.configure(bg=COLOR_DARK_BLUE)
        ctk.set_appearance_mode("dark")
        # Removed ctk.set_default_color_theme as we are setting colors explicitly

        # --- Header ---
        header_frame = ctk.CTkFrame(root, corner_radius=0, fg_color=COLOR_PRIMARY_BLUE)
        header_frame.pack(fill="x")
        header_label = ctk.CTkLabel(header_frame, text="Face Recognition System", text_color=COLOR_TEXT,
                                    font=ctk.CTkFont(family="Arial", size=20, weight="bold"))
        header_label.pack(pady=10)

        # --- Main Content Frame (Video + Status) ---
        main_frame = ctk.CTkFrame(root, fg_color=COLOR_DARK_BLUE)
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        self.video_label = ctk.CTkLabel(main_frame, text="", fg_color=COLOR_BACKGROUND) # Set background for video area
        self.video_label.pack(pady=10, fill="both", expand=True) # Allow video label to expand

        self.status_label = ctk.CTkLabel(main_frame, text="Status: Ready", text_color=COLOR_SUCCESS,
                                         font=ctk.CTkFont(family="Arial", size=14))
        self.status_label.pack(pady=10, fill="x")

        # --- Footer Controls ---
        footer_frame = ctk.CTkFrame(root, corner_radius=0, fg_color=COLOR_BACKGROUND, border_width=1, border_color=COLOR_PRIMARY_BLUE)
        footer_frame.pack(fill="x", side="bottom")
        
        # --- Input Section ---
        input_frame = ctk.CTkFrame(footer_frame, fg_color="transparent")
        input_frame.pack(pady=15)

        self.name_label = ctk.CTkLabel(input_frame, text="Name:", text_color=COLOR_TEXT, font=ctk.CTkFont(family="Arial", size=14))
        self.name_label.pack(side="left", padx=(10, 5))
        self.name_entry = ctk.CTkEntry(input_frame, placeholder_text="Enter person's name", width=250,
                                        fg_color=COLOR_DARK_BLUE, text_color=COLOR_TEXT,
                                        border_color=COLOR_PRIMARY_BLUE, border_width=2,
                                        # Explicitly set placeholder text color if needed, depends on CTk version
                                        # placeholder_text_color=COLOR_TEXT 
                                        )
        self.name_entry.pack(side="left", padx=(0, 20))

        # --- Button Section ---
        button_frame = ctk.CTkFrame(footer_frame, fg_color="transparent")
        button_frame.pack(pady=(0, 15))

        self.enroll_button = ctk.CTkButton(button_frame, text="Enrollment", # No image argument
                                           command=self.capture_photo, corner_radius=8,
                                           font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
                                           fg_color=COLOR_PRIMARY_BLUE, hover_color=COLOR_BUTTON_HOVER,
                                           text_color=COLOR_TEXT) # Ensure button text color is white
        self.enroll_button.pack(side="left", padx=10)
        
        self.train_button = ctk.CTkButton(button_frame, text="Train Model", # No image argument
                                          command=self.start_training_thread, corner_radius=8,
                                          font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
                                          fg_color=COLOR_PRIMARY_BLUE, hover_color=COLOR_BUTTON_HOVER,
                                          text_color=COLOR_TEXT) # Ensure button text color is white
        self.train_button.pack(side="left", padx=10)

        self.exit_button = ctk.CTkButton(button_frame, text="Exit", # No image argument
                                         command=self.on_closing, corner_radius=8,
                                         font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
                                         fg_color=COLOR_ERROR, hover_color="#c0392b",
                                         text_color=COLOR_TEXT) # Ensure button text color is white
        self.exit_button.pack(side="left", padx=10)

        # --- Camera Setup ---
        self.picam2 = Picamera2()
        self.picam2.configure(self.picam2.create_preview_configuration(main={"format": 'XRGB8888', "size": (640, 480)}))
        self.picam2.start()
        
        self.update_video_feed()
        
        # --- Fix for focus issue ---
        self.root.after(100, self.name_entry.focus_set)

    # Removed _load_icon helper function

    def update_video_feed(self):
        frame = self.picam2.capture_array()
        # This conversion is crucial for displaying correctly in CTkImage and for face_recognition
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) 
        
        pil_img = Image.fromarray(rgb_frame)
        # Resize to fit the label if needed, or keep original camera size
        # size=(640, 480) matches picam2 config.
        ctk_img = ctk.CTkImage(light_image=pil_img, size=(640, 480)) 
        
        self.video_label.configure(image=ctk_img)
        self.video_label.image = ctk_img
        
        self.root.after(15, self.update_video_feed)

    def capture_photo(self):
        person_name = self.name_entry.get().strip().lower()
        if not person_name:
            self.update_status("Error: Please enter a name.", COLOR_ERROR)
            return
            
        dataset_folder = "dataset"
        person_folder = os.path.join(dataset_folder, person_name)
        if not os.path.exists(person_folder):
            os.makedirs(person_folder)
            
        frame = self.picam2.capture_array()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{person_name}_{timestamp}.png"
        filepath = os.path.join(person_folder, filename)
        
        cv2.imwrite(filepath, frame)
        self.update_status(f"Success: Saved {filename}", COLOR_SUCCESS)
        print(f"Photo saved: {filepath}")

    def start_training_thread(self):
        self.enroll_button.configure(state="disabled")
        self.train_button.configure(state="disabled")
        self.exit_button.configure(state="disabled")
        self.update_status("Training started...", COLOR_WARNING)
        
        threading.Thread(target=self.run_model_training, daemon=True).start()

    def run_model_training(self):
        imagePaths = list(paths.list_images("dataset"))
        if not imagePaths:
            self.root.after(0, self.training_finished, "Error: No images found in dataset folder.", COLOR_ERROR)
            return

        knownEncodings = []
        knownNames = []
        total_images = len(imagePaths)

        for (i, imagePath) in enumerate(imagePaths):
            status_msg = f"Processing image {i + 1}/{total_images}..."
            self.root.after(0, self.update_status, status_msg, COLOR_WARNING)
            
            name = imagePath.split(os.path.sep)[-2]
            
            image = cv2.imread(imagePath)
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            boxes = face_recognition.face_locations(rgb, model="hog")
            encodings = face_recognition.face_encodings(rgb, boxes)
            
            for encoding in encodings:
                knownEncodings.append(encoding)
                knownNames.append(name)

        data = {"encodings": knownEncodings, "names": knownNames}
        with open("encodings.pickle", "wb") as f:
            f.write(pickle.dumps(data))
            
        self.root.after(0, self.training_finished, "Training complete! Encodings saved.", COLOR_SUCCESS)

    def training_finished(self, message, color):
        self.update_status(message, color)
        self.enroll_button.configure(state="normal")
        self.train_button.configure(state="normal")
        self.exit_button.configure(state="normal")

    def update_status(self, text, color):
        self.status_label.configure(text=f"Status: {text}", text_color=color)

    def on_closing(self):
        print("[INFO] Shutting down camera and application...")
        if self.picam2:
            self.picam2.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = ctk.CTk()
    app = ThemedFaceApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()