import customtkinter as ctk
from PIL import Image
import cv2
import depthai as dai
import numpy as np
import sys
import os
import time
import threading
import traceback

# --- 1. HARDWARE ENVIRONMENT SETUP ---
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"
os.environ["HAILO_SCHEDULER"] = "1"

from hailo_platform import (HEF, VDevice, InferVStreams, ConfigureParams, 
                            InputVStreamParams, OutputVStreamParams, 
                            FormatType, HailoStreamInterface)

sys.path.append("/home/raspberrypi/hailo-apps/hailo_apps/python/standalone_apps/pose_estimation")
from pose_estimation_utils import PoseEstPostProcessing

try:
    sys.path.append("/home/raspberrypi/Documents")
    from action_logic import StudentActionMonitor
except ImportError:
    print("❌ Critical: action_logic.py not found.")
    sys.exit(1)

HEF_PATH = "/home/raspberrypi/hailo-apps/resources/models/hailo8/yolov8m_pose.hef"
KP_NAMES = ["Nose", "L_Eye", "R_Eye", "L_Ear", "R_Ear", "L_Shldr", "R_Shldr", "L_Elbow", "R_Elbow", "L_Wrist", "R_Wrist", "L_Hip", "R_Hip", "L_Knee", "R_Knee", "L_Ankle", "R_Ankle"]
JOINT_PAIRS = [[0,1],[1,3],[0,2],[2,4],[5,6],[5,7],[7,9],[6,8],[8,10],[5,11],[6,12],[11,12],[11,13],[12,14],[13,15],[14,16]]

class KinectDiagnosticDash(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SENSEY Kinect-Style 3D Diagnostic")
        self.geometry("1500x900")
        
        self.current_frame = None
        self.current_students = []
        self.running = True

        # --- UI LAYOUT ---
        self.grid_columnconfigure(0, weight=2) # Video
        self.grid_columnconfigure(1, weight=1) # Table
        self.grid_rowconfigure(0, weight=1)

        # Video Panel
        self.video_label = ctk.CTkLabel(self, text="Syncing OAK-D Focus & Hailo NPU...")
        self.video_label.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Data Panel
        self.data_panel = ctk.CTkFrame(self, fg_color="#0a0a0a")
        self.data_panel.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(self.data_panel, text="SPATIAL PARAMETERS (MM)", font=("Arial", 18, "bold"), text_color="#00FF00").pack(pady=10)
        
        # ID Selector
        self.id_sel = ctk.CTkSegmentedButton(self.data_panel, values=["0", "1", "2"])
        self.id_sel.set("0")
        self.id_sel.pack(pady=5, padx=10, fill="x")

        self.lbl_action = ctk.CTkLabel(self.data_panel, text="ACTION: ---", font=("Arial", 22, "bold"))
        self.lbl_action.pack(pady=10)

        # --- Table Header ---
        t_header = ctk.CTkFrame(self.data_panel, fg_color="#222222")
        t_header.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(t_header, text="JOINT", width=100, anchor="w", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=5)
        ctk.CTkLabel(t_header, text="X", width=60, font=("Arial", 12, "bold")).grid(row=0, column=1)
        ctk.CTkLabel(t_header, text="Y", width=60, font=("Arial", 12, "bold")).grid(row=0, column=2)
        ctk.CTkLabel(t_header, text="Z", width=60, font=("Arial", 12, "bold")).grid(row=0, column=3)

        # --- Table Rows ---
        self.scroll_table = ctk.CTkScrollableFrame(self.data_panel, fg_color="transparent")
        self.scroll_table.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.table_data = {} # Dict to store labels for easy updating
        for i, name in enumerate(KP_NAMES):
            row = ctk.CTkFrame(self.scroll_table, fg_color="transparent")
            row.pack(fill="x", pady=1)
            
            ctk.CTkLabel(row, text=name, width=100, anchor="w", font=("Courier", 12)).grid(row=0, column=0, padx=5)
            lx = ctk.CTkLabel(row, text="0", width=60, text_color="#FF3333", font=("Courier", 12, "bold"))
            ly = ctk.CTkLabel(row, text="0", width=60, text_color="#33FF33", font=("Courier", 12, "bold"))
            lz = ctk.CTkLabel(row, text="0", width=60, text_color="#3333FF", font=("Courier", 12, "bold"))
            
            lx.grid(row=0, column=1)
            ly.grid(row=0, column=2)
            lz.grid(row=0, column=3)
            
            self.table_data[i] = {"x": lx, "y": ly, "z": lz}

        self.post_proc = PoseEstPostProcessing(max_detections=10, score_threshold=0.3, nms_iou_thresh=0.45, regression_length=15, strides=[8, 16, 32])
        self.action_monitor = StudentActionMonitor()
        
        threading.Thread(target=self.worker, daemon=True).start()
        self.ui_loop()

    def ui_loop(self):
        if not self.running: return
        if self.current_frame is not None:
            img = Image.fromarray(self.current_frame)
            ctk_img = ctk.CTkImage(light_image=img, size=(900, 675))
            self.video_label.configure(image=ctk_img, text="")

            sel = int(self.id_sel.get())
            target = next((s for s in self.current_students if s['id'] == sel), None)
            if target:
                self.lbl_action.configure(text=target['action'], text_color='#{:02x}{:02x}{:02x}'.format(*target['color'][::-1]))
                for i in range(17):
                    p = target['world_kp'][i]
                    self.table_data[i]["x"].configure(text=f"{int(p[0])}")
                    self.table_data[i]["y"].configure(text=f"{int(p[1])}")
                    self.table_data[i]["z"].configure(text=f"{int(p[2])}")
            else:
                self.lbl_action.configure(text="ID NOT SEEN", text_color="gray")
                for i in range(17):
                    for axis in ["x", "y", "z"]: self.table_data[i][axis].configure(text="---")

        self.after(30, self.ui_loop)

    def worker(self):
        try:
            # Hailo Init
            target = VDevice()
            hef = HEF(HEF_PATH)
            conf = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
            group = target.configure(hef, conf)[0]
            in_name = hef.get_input_vstream_infos()[0].name

            # OAK-D Init
            pipeline = dai.Pipeline()
            cam = pipeline.create(dai.node.ColorCamera)
            cam.setPreviewSize(640, 640)
            cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
            cam.setInterleaved(False)
            cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
            
            # 🚀 FIXED FOCUS AT ZERO (INFINITY)
            cam.initialControl.setManualFocus(0) 
            
            stereo = pipeline.create(dai.node.StereoDepth)
            left = pipeline.create(dai.node.MonoCamera)
            right = pipeline.create(dai.node.MonoCamera)
            left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
            right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
            left.setBoardSocket(dai.CameraBoardSocket.CAM_B)
            right.setBoardSocket(dai.CameraBoardSocket.CAM_C)
            stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
            stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
            
            x_rgb, x_dep = pipeline.create(dai.node.XLinkOut), pipeline.create(dai.node.XLinkOut)
            x_rgb.setStreamName("rgb"); x_dep.setStreamName("depth")
            left.out.link(stereo.left); right.out.link(stereo.right)
            cam.preview.link(x_rgb.input); stereo.depth.link(x_dep.input)

            with dai.Device(pipeline) as device:
                calib = device.readCalibration()
                intrinsics = calib.getCameraIntrinsics(dai.CameraBoardSocket.CAM_A, 640, 640)
                fx, fy, cx, cy = intrinsics[0][0], intrinsics[1][1], intrinsics[0][2], intrinsics[1][2]

                q_rgb = device.getOutputQueue("rgb", 1, False)
                q_dep = device.getOutputQueue("depth", 1, False)

                with group.activate():
                    with InferVStreams(group, InputVStreamParams.make(group, format_type=FormatType.FLOAT32), 
                                       OutputVStreamParams.make(group, format_type=FormatType.FLOAT32)) as pipe:
                        while self.running:
                            f_rgb = q_rgb.get().getCvFrame()
                            f_dep = q_dep.get().getFrame()
                            
                            input_data = {in_name: np.expand_dims(np.ascontiguousarray(f_rgb), axis=0).astype(np.float32)}
                            raw_res = pipe.infer(input_data)
                            parsed = self.post_proc.post_process(raw_res, 640, 640, 1)
                            
                            self.process_fusion(f_rgb, f_dep, parsed, fx, fy, cx, cy)
        except Exception:
            traceback.print_exc()

    def process_fusion(self, frame, depth, results, fx, fy, cx, cy):
        try:
            if 'predictions' in results: b_d, s_d, k_d, ks_d = results['predictions']
            elif 'bboxes' in results: b_d, s_d, k_d, ks_d = results['bboxes'][0], results['scores'][0], results['keypoints'][0], results['joint_scores'][0]
            else: return

            student_list = []
            for i in range(len(b_d)):
                if s_d[i] < 0.4: continue
                
                box = self.post_proc.map_box_to_original_coords(b_d[i], 640, 640, 640, 640)
                kp = k_d[i].reshape(17, 2)
                
                kp_3d, world_kp = [], []
                for idx in range(17):
                    u, v = int(kp[idx][0]), int(kp[idx][1])
                    z = 0
                    if 0 <= u < 640 and 0 <= v < 640:
                        patch = depth[max(0,v-1):v+2, max(0,u-1):u+2]
                        z = np.median(patch) if patch.size > 0 else 0
                    
                    x_mm = (u - cx) * z / fx
                    y_mm = (v - cy) * z / fy
                    kp_3d.append([u, v, z, ks_d[i][idx]])
                    world_kp.append([x_mm, y_mm, z])
                
                student_list.append({"id": i, "box": box, "keypoints": kp_3d, "world_kp": world_kp})

            analyzed = self.action_monitor.get_classroom_actions(student_list)
            
            for st in analyzed:
                bx = [int(x) for x in st['box']]
                cv2.rectangle(frame, (bx[0], bx[1]), (bx[2], bx[3]), st['color'], 2)
                for j in JOINT_PAIRS:
                    p1, p2 = st['keypoints'][j[0]], st['keypoints'][j[1]]
                    if p1[3] > 0.4 and p2[3] > 0.4:
                        cv2.line(frame, (p1[0], p1[1]), (p2[0], p2[1]), (0, 255, 255), 2)

            self.current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.current_students = analyzed

        except Exception:
            traceback.print_exc()

    def on_closing(self):
        self.running = False
        self.destroy()

if __name__ == "__main__":
 
    app = KinectDiagnosticDash()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()