import sys
from pathlib import Path
from multiprocessing import Process
import numpy as np
import cv2
from PIL import Image
from hailo_platform import HEF, VDevice, InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams, FormatType
from typing import List, Dict, Tuple
import time
import os
import json
import threading
import subprocess
import queue
import shlex

# --- UPDATED PATHS ---
PIPER_EXE = "/home/raspberrypi/TTS-STT-AUDIO/piper/piper" 
PIPER_MODEL = "/home/raspberrypi/TTS-STT-AUDIO/en_US-lessac-medium.onnx"
PIPER_READY = os.path.exists(PIPER_EXE) and os.path.exists(PIPER_MODEL)

try:
    from gpiozero import Button
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

try:
    from hailo_apps.python.core.common.hailo_logger import get_logger
except ImportError:
    core_dir = Path(__file__).resolve().parents[2] / "core"
    sys.path.insert(0, str(core_dir))
    from common.hailo_logger import get_logger

logger = get_logger(__name__)

# Joint pairs used for drawing pose estimations
JOINT_PAIRS = [
    [0, 1], [1, 3], [0, 2], [2, 4],
    [5, 6], [5, 7], [7, 9], [6, 8], [8, 10],
    [5, 11], [6, 12], [11, 12],
    [11, 13], [12, 14], [13, 15], [14, 16]
]

# --- 🚀 AUDIO QUEUE & BACKGROUND WORKER ---
audio_queue = queue.Queue()

def tts_worker():
    """Background daemon to render speech to RAM and play via PipeWire."""
    ram_file = "/dev/shm/report.wav"
    while True:
        text = audio_queue.get()
        if text is None: break
        
        try:
            # 1. Render to RAM disk (Super fast, no SD card bottleneck)
            piper_cmd = (
                f"echo {shlex.quote(text)} | "
                f"{PIPER_EXE} --model {PIPER_MODEL} --length_scale 1.0 --output_file {ram_file}"
            )
            subprocess.run(piper_cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # 2. Play via PipeWire (Handles Bluetooth buffering flawlessly)
            play_cmd = f"pw-play {ram_file}"
            subprocess.run(play_cmd, shell=True, check=True)
            
            # 3. Clean up RAM
            if os.path.exists(ram_file):
                os.remove(ram_file)
                
        except Exception as e:
            print(f"[Audio Error]: {e}")
        finally:
            audio_queue.task_done()

if PIPER_READY:
    # Start the daemon thread once when the module loads
    threading.Thread(target=tts_worker, daemon=True).start()

def speak(text):
    """Global function to drop text into the background worker queue."""
    audio_queue.put(text)


class PoseEstPostProcessing:
    def __init__(self, max_detections=15, score_threshold=0.3, nms_iou_thresh=0.45, regression_length=15, strides=[8, 16, 32]):
        self.max_detections = max_detections
        self.score_threshold = score_threshold
        self.nms_iou_thresh = nms_iou_thresh
        self.regression_length = regression_length
        self.strides = strides
        
        # State Variables
        self.name_map = {}
        self.logic_initialized = False
        self.snap_button = None
        self.gpio_ready = False
        self.action_monitor = None
        self.prev_time = time.time()
        self.report_printed = True 
        self.warmup_frames = 0 

    def map_box_to_original_coords(self, box, orig_w, orig_h, model_w, model_h):
        scale = min(model_w / orig_w, model_h / orig_h)
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        x_offset = (model_w - new_w) // 2
        y_offset = (model_h - new_h) // 2
        xmin = int((box[0] - x_offset) / scale)
        xmax = int((box[2] - x_offset) / scale)
        ymin = int((box[1] - y_offset) / scale)
        ymax = int((box[3] - y_offset) / scale)
        return [max(0, min(orig_w-1, xmin)), max(0, min(orig_h-1, ymin)), 
                max(0, min(orig_w-1, xmax)), max(0, min(orig_h-1, ymax))]

    def map_keypoints_to_original_coords(self, keypoints, orig_w, orig_h, model_w, model_h):
        scale = min(model_w / orig_w, model_h / orig_h)
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        x_offset = (model_w - new_w) // 2
        y_offset = (model_h - new_h) // 2
        keypoints[:, 0] = (keypoints[:, 0] - x_offset) / scale
        keypoints[:, 1] = (keypoints[:, 1] - y_offset) / scale
        keypoints[:, 0] = np.clip(keypoints[:, 0], 0, orig_w - 1)
        keypoints[:, 1] = np.clip(keypoints[:, 1], 0, orig_h - 1)
        return keypoints

    def visualize_pose_estimation_result(self, results, image, model_height, model_width, depth_map=None, intrinsics=None, vpu_faces=None, detection_threshold=0.4, joint_threshold=0.4, key_pressed=255):
        display_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        self.warmup_frames += 1

        if not self.logic_initialized:
            try:
                sys.path.append("/home/raspberrypi/Student Monitoring")
                from action_logic import StudentActionMonitor
                self.action_monitor = StudentActionMonitor()
                if GPIO_AVAILABLE:
                    try: 
                        self.snap_button = Button(26, pull_up=True, bounce_time=0.1)
                        self.gpio_ready = True
                    except: self.snap_button = None
                map_path = "/home/raspberrypi/Student Monitoring/name_map.json"
                if os.path.exists(map_path):
                    with open(map_path, "r") as f: self.name_map = json.load(f)
                self.logic_initialized = True
            except: pass

        try:
            if 'predictions' in results: b_d, s_d, k_d, ks_d = results['predictions'][0], results['predictions'][1], results['predictions'][2], results['predictions'][3]
            elif 'bboxes' in results: b_d, s_d, k_d, ks_d = results['bboxes'][0], results['scores'][0], results['keypoints'][0], results['joint_scores'][0]
            else: return display_image
        except: return display_image

        orig_h, orig_w = display_image.shape[:2]
        fx, fy, cx, cy = intrinsics if intrinsics else [1, 1, 1, 1]

        btn = self.snap_button.is_pressed if (self.gpio_ready and self.snap_button) else False
        if key_pressed == ord('s') or btn:
            self.report_printed = False 
            print("🔊 Generating Smart Audio Report...")

        all_students_data, action_groups = [], {}
        for i, (box, score, kp, kp_score) in enumerate(zip(b_d, s_d, k_d, ks_d)):
            if float(score) < detection_threshold or np.isnan(box).any(): continue
            det_box = self.map_box_to_original_coords(box, orig_w, orig_h, model_width, model_height)
            mkp = self.map_keypoints_to_original_coords(kp.reshape(17, 2), orig_w, orig_h, model_width, model_height)
            
            if kp_score[9] > joint_threshold: det_box[1] = min(det_box[1], int(mkp[9][1] - 20))
            if kp_score[10] > joint_threshold: det_box[1] = min(det_box[1], int(mkp[10][1] - 20))
            
            kp_3d = []
            for idx in range(17):
                px, py = int(mkp[idx][0]), int(mkp[idx][1])
                z, ground_h = 0, 0
                if idx <= 12 and depth_map is not None:
                    px_c, py_c = min(max(0, px), depth_map.shape[1] - 1), min(max(0, py), depth_map.shape[0] - 1)
                    z = depth_map[py_c, px_c]
                    if z > 0: ground_h = 1200 - ((py - cy) * z / fy)
                kp_3d.append([px, py, z, kp_score[idx], ground_h])
            all_students_data.append({"id": i, "box": det_box, "keypoints": kp_3d, "name": f"Student {i+1}", "raw_mkp": mkp, "raw_ks": kp_score})

        if self.logic_initialized and self.action_monitor is not None:
            processed = self.action_monitor.get_classroom_actions(all_students_data)
        else:
            processed = []

        for st in processed:
            xb, act, col, name = [int(x) for x in st['box']], st['action'], st['color'], st['name']
            mkp_s, ks_s = st['raw_mkp'], st['raw_ks']

            if ks_s[0] > 0.4: 
                nx, ny = int(mkp_s[0][0]), int(mkp_s[0][1])
                if ks_s[1] > 0.3 and ks_s[2] > 0.3:
                    fw = int(np.linalg.norm(mkp_s[1] - mkp_s[2]) * 2.8) 
                else:
                    fw = int((xb[2] - xb[0]) * 0.45)
                fh = int(fw * 1.35)
                
                bx1, by1 = max(0, nx - fw // 2), max(0, ny - fh // 2)
                bx2, by2 = min(orig_w - 1, nx + fw // 2), min(orig_h - 1, ny + fh // 2)
                
                if bx2 > bx1 and by2 > by1:
                    face_roi = display_image[by1:by2, bx1:bx2]
                    roi_h, roi_w = face_roi.shape[:2]
                    
                    mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
                    cv2.ellipse(mask, (roi_w // 2, roi_h // 2), (roi_w // 2, roi_h // 2), 0, 0, 360, 255, -1)
                    
                    blurred_roi = cv2.GaussianBlur(face_roi, (99, 99), 30)
                    
                    mask_inv = cv2.bitwise_not(mask)
                    bg = cv2.bitwise_and(face_roi, face_roi, mask=mask_inv)
                    fg = cv2.bitwise_and(blurred_roi, blurred_roi, mask=mask)
                    
                    display_image[by1:by2, bx1:bx2] = cv2.add(bg, fg)

            cv2.rectangle(display_image, (xb[0], xb[1]), (xb[2], xb[3]), col, 3)
            cv2.rectangle(display_image, (xb[0], xb[1]-35), (xb[0]+420, xb[1]), col, -1)
            cv2.putText(display_image, f"{name} | {act}", (xb[0]+10, xb[1]-10), 0, 0.8, (255,255,255), 2)
            
            for idx, pt in enumerate(mkp_s):
                if ks_s[idx] > joint_threshold:
                    cv2.circle(display_image, (int(pt[0]), int(pt[1])), 4, (120, 120, 255), -1)
            for j0, j1 in JOINT_PAIRS:
                if ks_s[j0] > joint_threshold and ks_s[j1] > joint_threshold:
                    cv2.line(display_image, (int(mkp_s[j0][0]), int(mkp_s[j0][1])), (int(mkp_s[j1][0]), int(mkp_s[j1][1])), (0, 255, 255), 2)
            
            if act not in action_groups: action_groups[act] = []
            action_groups[act].append(name)

        if not self.report_printed and self.warmup_frames > 35:
            self.report_printed = True 
            full_t = ""
            if len(action_groups) == 0: full_t = "No students detected."
            else:
                for action, names_list in action_groups.items():
                    count = len(names_list)
                    line = f"{count} {'Student' if count==1 else 'Students'} {'is' if count==1 else 'are'} {action}."
                    print(f"   👉 {line}")
                    full_t += line + " "
            
            if PIPER_READY:
                print(f"🗣️ Triggering Voice: {full_t}")
                speak(full_t) 

        fps = 1 / (time.time() - self.prev_time); self.prev_time = time.time()
        cv2.putText(display_image, f"FPS: {fps:.1f}", (20, 40), 1, 1.5, (0, 255, 0), 2)
        return display_image

    def _sigmoid(self, x: np.ndarray) -> np.ndarray:
        return 1 / (1 + np.exp(-x))

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        return np.exp(x) / np.expand_dims(np.sum(np.exp(x), axis=-1), axis=-1)

    def max_value(self, a: float, b: float) -> float:
        return a if a >= b else b

    def min_value(self, a: float, b: float) -> float:
        return a if a <= b else b

    def nms(self, dets: np.ndarray, thresh: float) -> np.ndarray:
        x1, y1, x2, y2 = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3]
        scores = dets[:, 4]
        areas = (x2 - x1 + 1) * (y2 - y1 + 1)
        order = np.argsort(scores)[::-1]

        suppressed = np.zeros(dets.shape[0], dtype=int)
        for i in range(len(order)):
            idx_i = order[i]
            if suppressed[idx_i] == 1:
                continue
            for j in range(i + 1, len(order)):
                idx_j = order[j]
                if suppressed[idx_j] == 1:
                    continue

                xx1 = self.max_value(x1[idx_i], x1[idx_j])
                yy1 = self.max_value(y1[idx_i], y1[idx_j])
                xx2 = self.min_value(x2[idx_i], x2[idx_j])
                yy2 = self.min_value(y2[idx_i], y2[idx_j])
                w = self.max_value(0.0, xx2 - xx1 + 1)
                h = self.max_value(0.0, yy2 - yy1 + 1)
                inter = w * h
                ovr = inter / (areas[idx_i] + areas[idx_j] - inter)

                if ovr >= thresh:
                    suppressed[idx_j] = 1

        return np.where(suppressed == 0)[0]

    def decoder(
            self, raw_boxes: np.ndarray, raw_kpts: np.ndarray, strides: List[int],
            image_dims: Tuple[int, int], reg_max: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        boxes = None
        decoded_kpts = None

        for box_distribute, kpts, stride, _ in zip(raw_boxes, raw_kpts, strides, np.arange(3)):
            shape = [int(x / stride) for x in image_dims]
            grid_x = np.arange(shape[1]) + 0.5
            grid_y = np.arange(shape[0]) + 0.5
            grid_x, grid_y = np.meshgrid(grid_x, grid_y)
            ct_row = grid_y.flatten() * stride
            ct_col = grid_x.flatten() * stride
            center = np.stack((ct_col, ct_row, ct_col, ct_row), axis=1)

            reg_range = np.arange(reg_max + 1)
            box_distribute = np.reshape(box_distribute, (-1, box_distribute.shape[1] * box_distribute.shape[2], 4, reg_max + 1))
            box_distance = self._softmax(box_distribute) * np.reshape(reg_range, (1, 1, 1, -1))
            box_distance = np.sum(box_distance, axis=-1) * stride

            box_distance = np.concatenate([box_distance[:, :, :2] * (-1), box_distance[:, :, 2:]], axis=-1)
            decode_box = np.expand_dims(center, axis=0) + box_distance

            xmin, ymin, xmax, ymax = decode_box[:, :, 0], decode_box[:, :, 1], decode_box[:, :, 2], decode_box[:, :, 3]
            decode_box = np.transpose([xmin, ymin, xmax, ymax], [1, 2, 0])

            xywh_box = np.transpose([(xmin + xmax) / 2, (ymin + ymax) / 2, xmax - xmin, ymax - ymin], [1, 2, 0])
            boxes = xywh_box if boxes is None else np.concatenate([boxes, xywh_box], axis=1)

            kpts[..., :2] *= 2
            kpts[..., :2] = stride * (kpts[..., :2] - 0.5) + np.expand_dims(center[..., :2], axis=1)
            decoded_kpts = kpts if decoded_kpts is None else np.concatenate([decoded_kpts, kpts], axis=1)

        return boxes, decoded_kpts

    def xywh2xyxy(self, x: np.ndarray) -> np.ndarray:
        y = np.copy(x)
        y[:, 0] = x[:, 0] - x[:, 2] / 2
        y[:, 1] = x[:, 1] - x[:, 3] / 2
        y[:, 2] = x[:, 0] + x[:, 2] / 2
        y[:, 3] = x[:, 1] + x[:, 3] / 2
        return y

    def non_max_suppression(
            self, prediction: np.ndarray, conf_thres: float = 0.1, iou_thres: float = 0.45,
            max_det: int = 100, n_kpts: int = 17
    ) -> List[dict]:
        assert 0 <= conf_thres <= 1, f'Invalid confidence threshold {conf_thres}, valid values are between 0.0 and 1.0'
        assert 0 <= iou_thres <= 1, f'Invalid IoU threshold {iou_thres}, valid values are between 0.0 and 1.0'

        nc = prediction.shape[2] - n_kpts * 3 - 4
        xc = prediction[..., 4] > conf_thres
        ki = 4 + nc
        output = []

        for xi, x in enumerate(prediction):
            x = x[xc[xi]]
            if not x.shape[0]:
                output.append({'bboxes': np.zeros((0, 4)), 'keypoints': np.zeros((0, n_kpts, 3)), 'scores': np.zeros((0)), 'num_detections': 0})
                continue

            boxes = self.xywh2xyxy(x[:, :4])
            kpts = x[:, ki:]
            conf = np.expand_dims(x[:, 4:ki].max(1), 1)
            j = np.expand_dims(x[:, 4:ki].argmax(1), 1).astype(np.float32)

            keep = np.squeeze(conf, 1) > conf_thres
            x = np.concatenate((boxes, conf, j, kpts), 1)[keep]
            x = x[x[:, 4].argsort()[::-1][:max_det]]

            if not x.shape[0]:
                output.append({'bboxes': np.zeros((0, 4)), 'keypoints': np.zeros((0, n_kpts, 3)), 'scores': np.zeros((0)), 'num_detections': 0})
                continue

            boxes = x[:, :4]
            scores = x[:, 4]
            kpts = x[:, 6:].reshape(-1, n_kpts, 3)

            i = self.nms(np.concatenate((boxes, np.expand_dims(scores, 1)), axis=1), iou_thres)
            output.append({'bboxes': boxes[i], 'keypoints': kpts[i], 'scores': scores[i], 'num_detections': len(i)})

        return output

    def inference_result_handler(self, image, raw_detections: dict, model_height: int, model_width: int, class_num: int = 1) -> None:
        results = self.post_process(raw_detections, model_height, model_width, class_num)
        output_image = self.visualize_pose_estimation_result(results, image, model_height, model_width)
        return output_image

    def post_process(self, raw_detections: dict, height: int, width: int, class_num: int) -> dict:
        raw_detections_keys = list(raw_detections.keys())
        layer_from_shape = {raw_detections[key].shape: key for key in raw_detections_keys}
        detection_output_channels = (self.regression_length + 1) * 4  
        keypoints = 51
        endnodes = [
            raw_detections[layer_from_shape[1, 20, 20, detection_output_channels]],
            raw_detections[layer_from_shape[1, 20, 20, class_num]],
            raw_detections[layer_from_shape[1, 20, 20, keypoints]],
            raw_detections[layer_from_shape[1, 40, 40, detection_output_channels]],
            raw_detections[layer_from_shape[1, 40, 40, class_num]],
            raw_detections[layer_from_shape[1, 40, 40, keypoints]],
            raw_detections[layer_from_shape[1, 80, 80, detection_output_channels]],
            raw_detections[layer_from_shape[1, 80, 80, class_num]],
            raw_detections[layer_from_shape[1, 80, 80, keypoints]]
        ]
        return self.extract_pose_estimation_results(endnodes, height, width, class_num)

    def extract_pose_estimation_results(self, endnodes: List[np.ndarray], height: int, width: int, class_num: int) -> Dict[str, np.ndarray]:
        batch_size = endnodes[0].shape[0]
        strides = self.strides[::-1]
        image_dims = (height, width)

        raw_boxes = endnodes[:7:3]
        scores = [np.reshape(s, (-1, s.shape[1] * s.shape[2], class_num)) for s in endnodes[1:8:3]]
        scores = np.concatenate(scores, axis=1)
        kpts = [np.reshape(c, (-1, c.shape[1] * c.shape[2], 17, 3)) for c in endnodes[2:9:3]]

        decoded_boxes, decoded_kpts = self.decoder(raw_boxes, kpts, strides, image_dims, self.regression_length)
        decoded_kpts = np.reshape(decoded_kpts, (batch_size, -1, 51))
        predictions = np.concatenate([decoded_boxes, scores, decoded_kpts], axis=2)

        nms_res = self.non_max_suppression(predictions, conf_thres=self.score_threshold, iou_thres=self.nms_iou_thresh, max_det=self.max_detections)

        # 🚀 RESTORED ORIGINAL STABLE DICTIONARY INITIALIZATION
        output = {
            'bboxes': np.zeros((batch_size, self.max_detections, 4)),
            'keypoints': np.zeros((batch_size, self.max_detections, 17, 2)),
            'joint_scores': np.zeros((batch_size, self.max_detections, 17, 1)),
            'scores': np.zeros((batch_size, self.max_detections, 1))
        }

        for b in range(batch_size):
            output['bboxes'][b, :nms_res[b]['num_detections']] = nms_res[b]['bboxes']
            output['keypoints'][b, :nms_res[b]['num_detections']] = nms_res[b]['keypoints'][..., :2]
            output['joint_scores'][b, :nms_res[b]['num_detections'], ..., 0] = self._sigmoid(nms_res[b]['keypoints'][..., 2])
            output['scores'][b, :nms_res[b]['num_detections'], ..., 0] = nms_res[b]['scores']

        return output