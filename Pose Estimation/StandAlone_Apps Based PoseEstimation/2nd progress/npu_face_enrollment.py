import os
import cv2
import pickle
import threading
import numpy as np
import customtkinter as ctk
from PIL import Image
from hailo_platform import HEF, VDevice, HailoStreamInterface, InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams, FormatType

# --- Color Palette ---
COLOR_PRIMARY_BLUE = "#007bff"
COLOR_DARK_BLUE = "#2c3e50"
COLOR_BACKGROUND = "#1f2b38"
COLOR_TEXT = "#ecf0f1"
COLOR_SUCCESS = "#2ecc71"
COLOR_ERROR = "#e74c3c"
COLOR_WARNING = "#f39c12"

class NPUFaceEnrollApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NPU Face Enrollment (ArcFace)")
        self.root.geometry("800x800")
        self.root.configure(bg=COLOR_DARK_BLUE)
        
        # --- UI Setup ---
        header_frame = ctk.CTkFrame(root, corner_radius=0, fg_color=COLOR_PRIMARY_BLUE)
        header_frame.pack(fill="x")
        ctk.CTkLabel(header_frame, text="NPU Face Database Creator", text_color=COLOR_TEXT, font=("Arial", 20, "bold")).pack(pady=10)

        main_frame = ctk.CTkFrame(root, fg_color=COLOR_DARK_BLUE)
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        self.video_label = ctk.CTkLabel(main_frame, text="", fg_color=COLOR_BACKGROUND)
        self.video_label.pack(pady=10, fill="both", expand=True)

        self.status_label = ctk.CTkLabel(main_frame, text="Status: Initializing NPU...", text_color=COLOR_WARNING)
        self.status_label.pack(pady=10, fill="x")

        footer_frame = ctk.CTkFrame(root, corner_radius=0, fg_color=COLOR_BACKGROUND)
        footer_frame.pack(fill="x", side="bottom")
        
        self.name_entry = ctk.CTkEntry(footer_frame, placeholder_text="Enter Student Name", width=250)
        self.name_entry.pack(pady=10)

        btn_frame = ctk.CTkFrame(footer_frame, fg_color="transparent")
        btn_frame.pack(pady=10)

        self.enroll_btn = ctk.CTkButton(btn_frame, text="Capture Photo", command=self.capture_photo, fg_color=COLOR_PRIMARY_BLUE)
        self.enroll_btn.pack(side="left", padx=10)
        
        self.train_btn = ctk.CTkButton(btn_frame, text="Generate NPU Encodings", command=self.start_training, fg_color=COLOR_SUCCESS)
        self.train_btn.pack(side="left", padx=10)

        # --- Hailo & Camera Setup ---
        self.hef_path = "/home/raspberrypi/hailo-apps/resources/models/hailo8/arcface_mobilefacenet.hef"
        self.cap = cv2.VideoCapture(0)
        self.running = True
        
        # Start the video feed
        self.update_video_feed()
        self.update_status("Ready to Enroll", COLOR_SUCCESS)

    def update_status(self, text, color):
        self.status_label.configure(text=f"Status: {text}", text_color=color)

    def update_video_feed(self):
        if not self.running: return
        ret, frame = self.cap.read()
        if ret:
            # Display BGR camera to RGB GUI
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb_frame)
            ctk_img = ctk.CTkImage(light_image=img, size=(640, 480))
            self.video_label.configure(image=ctk_img)
            self.video_label.image = ctk_img
        self.root.after(15, self.update_video_feed)

    def capture_photo(self):
        name = self.name_entry.get().strip().lower()
        if not name:
            self.update_status("Error: Enter a name!", COLOR_ERROR)
            return
            
        path = f"npu_dataset/{name}"
        os.makedirs(path, exist_ok=True)
        
        ret, frame = self.cap.read()
        if ret:
            img_path = os.path.join(path, f"{name}_{len(os.listdir(path))}.png")
            cv2.imwrite(img_path, frame)
            self.update_status(f"Captured for {name}", COLOR_SUCCESS)

    def start_training(self):
        self.enroll_btn.configure(state="disabled")
        self.train_btn.configure(state="disabled")
        self.update_status("NPU Encoding in Progress...", COLOR_WARNING)
        threading.Thread(target=self.run_npu_inference, daemon=True).start()

    def run_npu_inference(self):
        # 1. Initialize Hailo NPU for ArcFace
        target = VDevice()
        hef = HEF(self.hef_path)
        configure_params = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
        network_group = target.configure(hef, configure_params)[0]
        network_group_params = network_group.create_params()
        
        input_vstreams_params = InputVStreamParams.make(network_group, format_type=FormatType.FLOAT32)
        output_vstreams_params = OutputVStreamParams.make(network_group, format_type=FormatType.FLOAT32)

        known_encodings = []
        known_names = []
        
        # ArcFace input size is usually 112x112
        input_info = hef.get_input_vstream_infos()[0]
        h, w, _ = input_info.shape

        dataset_path = "npu_dataset"
        
        with network_group.activate(network_group_params):
            with InferVStreams(network_group, input_vstreams_params, output_vstreams_params) as infer_pipeline:
                
                for person_name in os.listdir(dataset_path):
                    person_dir = os.path.join(dataset_path, person_name)
                    for img_name in os.listdir(person_dir):
                        img = cv2.imread(os.path.join(person_dir, img_name))
                        
                        # Pre-process for ArcFace (Resize to 112x112, RGB)
                        # We use a simple face crop (middle of image) for enrollment
                        ih, iw, _ = img.shape
                        crop = img[ih//4:3*ih//4, iw//4:3*iw//4]
                        face_resized = cv2.resize(crop, (w, h))
                        face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB).astype(np.float32)
                        
                        # Add batch dimension
                        input_data = {input_info.name: np.expand_dims(face_rgb, axis=0)}
                        
                        # Inference on NPU
                        output = infer_pipeline.infer(input_data)
                        # ArcFace returns a 512-dim vector
                        vector = list(output.values())[0][0]
                        
                        known_encodings.append(vector)
                        known_names.append(person_name)

        # Save NPU Encodings
        data = {"encodings": known_encodings, "names": known_names}
        with open("/home/raspberrypi/Downloads/npu_encodings.pickle", "wb") as f:
            f.write(pickle.dumps(data))
            
        self.root.after(0, self.training_complete)

    def training_complete(self):
        self.update_status("NPU Database Saved!", COLOR_SUCCESS)
        self.enroll_btn.configure(state="normal")
        self.train_btn.configure(state="normal")

    def on_closing(self):
        self.running = False
        self.cap.release()
        self.root.destroy()

if __name__ == "__main__":
    root = ctk.CTk()
    app = NPUFaceEnrollApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()