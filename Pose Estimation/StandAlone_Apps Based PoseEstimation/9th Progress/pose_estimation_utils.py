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

# Try importing Audio libraries (Fail gracefully if not installed)
try:
    from gtts import gTTS
    from playsound import playsound
    AUDIO_ENABLED = True
except ImportError:
    print("⚠️ gTTS or playsound not found. Voice feedback disabled.")
    AUDIO_ENABLED = False

try:
    from hailo_apps.python.core.common.hailo_logger import get_logger
except ImportError:
    core_dir = Path(__file__).resolve().parents[2] / "core"
    sys.path.insert(0, str(core_dir))
    from common.hailo_logger import get_logger

logger = get_logger(__name__)

# --- GPIO SETUP (For Physical Button) ---
try:
    from gpiozero import Button
    GPIO_AVAILABLE = True
except ImportError:
    print("⚠️ gpiozero not found. Physical button disabled.")
    GPIO_AVAILABLE = False

# Joint pairs used for drawing pose estimations
JOINT_PAIRS = [
    [0, 1], [1, 3], [0, 2], [2, 4],
    [5, 6], [5, 7], [7, 9], [6, 8], [8, 10],
    [5, 11], [6, 12], [11, 12],
    [11, 13], [12, 14], [13, 15], [14, 16]
]

class PoseEstPostProcessing:
    def __init__(self, max_detections=15, score_threshold=0.3, nms_iou_thresh=0.45, regression_length=15, strides=[8, 16, 32]):
        self.max_detections = max_detections
        self.score_threshold = score_threshold
        self.nms_iou_thresh = nms_iou_thresh
        self.regression_length = regression_length
        self.strides = strides
        
        # 🚀 FIXED: Pre-define all attributes to prevent AttributeError
        self.name_map = {}
        self.logic_initialized = False
        self.snap_button = None
        self.gpio_ready = False
        self.action_monitor = None
        self.prev_time = time.time()
        self.report_printed = True

    def inference_result_handler(
            self, image, raw_detections: dict, model_height: int, model_width: int, class_num: int = 1
    ) -> None:
        """
        Post-process the inference results and return the output image with visualizations.

        Args:
            image (np.ndarray): The input image frame.
            raw_detections (dict): Raw inference results from the model.
            model_height (int): The height of the model input.
            model_width (int): The width of the model input.
            class_num (int, optional): Number of output classes. Defaults to 1.

        Returns:
            np.ndarray: The image with visualized inference results.
        """
        # Post-process results
        results = self.post_process(raw_detections, model_height, model_width, class_num)

        # Visualize and save results
        output_image = self.visualize_pose_estimation_result(results, image, model_height, model_width)

        return  output_image

    def post_process(self, raw_detections: dict, height: int, width: int, class_num: int) -> dict:
        """
        Process raw detections into a structured format for pose estimation.

        Args:
            raw_detections (Dict): Raw detections from the model.
            height (int): The height of the input image.
            width (int): The width of the input image.
            class_num (int): Number of classes.

        Returns:
            Dict: Processed predictions dictionary.
        """
        raw_detections_keys = list(raw_detections.keys())
        layer_from_shape = {raw_detections[key].shape: key for key in raw_detections_keys}
        detection_output_channels = (self.regression_length + 1) * 4  # (regression length + 1) * num_coordinates
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

        predictions_dict = self.extract_pose_estimation_results(endnodes, height, width, class_num)
        return predictions_dict

    def extract_pose_estimation_results(
            self, endnodes: List[np.ndarray], height: int, width: int, class_num: int
    ) -> Dict[str, np.ndarray]:
        """
        Post-process the pose estimation results.

        Args:
            endnodes (list[np.ndarray]): list of 10 tensors from the model output.
            height (int): Height of the input image.
            width (int): Width of the input image.
            class_num (int): Number of classes.

        Returns:
            dict: Processed detections with keys:
                'bboxes': numpy.ndarray with shape (batch_size, max_detections, 4),
                'keypoints': numpy.ndarray with shape (batch_size, max_detections, 17, 2),
                'joint_scores': numpy.ndarray with shape (batch_size, max_detections, 17, 1),
                'scores': numpy.ndarray with shape (batch_size, max_detections, 1).
        """
        batch_size = endnodes[0].shape[0]
        strides = self.strides[::-1]
        image_dims = (height, width)

        raw_boxes = endnodes[:7:3]
        scores = [
            np.reshape(s, (-1, s.shape[1] * s.shape[2], class_num)) for s in endnodes[1:8:3]
        ]
        scores = np.concatenate(scores, axis=1)

        kpts = [
            np.reshape(c, (-1, c.shape[1] * c.shape[2], 17, 3)) for c in endnodes[2:9:3]
        ]

        decoded_boxes, decoded_kpts = self.decoder(raw_boxes,
                                                   kpts, strides,
                                                   image_dims, self.regression_length)
        decoded_kpts = np.reshape(decoded_kpts, (batch_size, -1, 51))
        predictions = np.concatenate([decoded_boxes, scores, decoded_kpts], axis=2)

        nms_res = self.non_max_suppression(
            predictions, conf_thres=self.score_threshold,
            iou_thres=self.nms_iou_thresh, max_det=self.max_detections
        )

        output = {
            'bboxes': np.zeros((batch_size, self.max_detections, 4)),
            'keypoints': np.zeros((batch_size, self.max_detections, 17, 2)),
            'joint_scores': np.zeros((batch_size, self.max_detections, 17, 1)),
            'scores': np.zeros((batch_size, self.max_detections, 1))
        }

        for b in range(batch_size):
            output['bboxes'][b, :nms_res[b]['num_detections']] = nms_res[b]['bboxes']
            output['keypoints'][b, :nms_res[b]['num_detections']] = nms_res[b]['keypoints'][..., :2]
            output['joint_scores'][b, :nms_res[b]['num_detections'],
            ..., 0] = self._sigmoid(nms_res[b]['keypoints'][..., 2])
            output['scores'][b, :nms_res[b]['num_detections'], ..., 0] = nms_res[b]['scores']

        return output


    def map_box_to_original_coords(self, box, orig_w, orig_h, model_w, model_h):
        # 🚀 1920 / 640 = 3.0 scale
        xmin, ymin, xmax, ymax = box
        scale_x = orig_w / model_w 
        scale_y = orig_h / model_h 
        return [xmin * scale_x, ymin * scale_y, xmax * scale_x, ymax * scale_y]

    def map_keypoints_to_original_coords(self, keypoints, orig_w, orig_h, model_w, model_h):
        scale_x = orig_w / model_w
        scale_y = orig_h / model_h
        mapped = np.zeros_like(keypoints)
        mapped[:, 0] = keypoints[:, 0] * scale_x
        mapped[:, 1] = keypoints[:, 1] * scale_y
        return mapped

    def visualize_pose_estimation_result(
            self, results, image, model_height, model_width, 
            depth_map=None, intrinsics=None, vpu_faces=None,
            detection_threshold=0.4, joint_threshold=0.4
    ) -> np.ndarray:
        
        # 🚀 1. COLOR FIX: Convert RGB (from OAK-D) back to BGR for Display
        display_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        # --- 2. INITIALIZATION ---
        if not self.logic_initialized:
            self.report_printed = True
            try:
                sys.path.append("/home/raspberrypi/Documents")
                from action_logic import StudentActionMonitor
                self.action_monitor = StudentActionMonitor()
                print("✅ 3D Action Logic Ready.")
            except:
                class Dummy: 
                    def get_classroom_actions(self, data):
                        for d in data: d['action'], d['color'] = "Monitoring", (0,255,0)
                        return data
                self.action_monitor = Dummy()
            
            if GPIO_AVAILABLE:
                try: 
                    self.snap_button = Button(26, pull_up=True, bounce_time=0.1)
                    self.gpio_ready = True
                    print("✅ Physical Button on GPIO 26 Ready.")
                except: self.gpio_ready = False

            map_path = "/home/raspberrypi/Documents/name_map.json"
            if os.path.exists(map_path):
                try:
                    with open(map_path, "r") as f: self.name_map = json.load(f)
                except: pass
            
            # Reset report if just finished a face scan
            flag_path = "/home/raspberrypi/Documents/just_scanned.flag"
            if os.path.exists(flag_path):
                self.report_printed = False 
                os.remove(flag_path)
            
            self.logic_initialized = True

        # --- 3. DATA EXTRACTION ---
        try:
            if 'predictions' in results: b_d, s_d, k_d, ks_d = results['predictions'][0], results['predictions'][1], results['predictions'][2], results['predictions'][3]
            elif 'bboxes' in results: b_d, s_d, k_d, ks_d = results['bboxes'][0], results['scores'][0], results['keypoints'][0], results['joint_scores'][0]
            else: return display_image
        except: return display_image

        orig_h, orig_w = display_image.shape[:2]
        fx, fy, cx, cy = intrinsics if intrinsics else [1, 1, 1, 1]

        # --- 4. TRIGGER HANDLING ---
        key = cv2.waitKey(1) & 0xFF
        btn_pressed = self.snap_button.is_pressed if self.gpio_ready and self.snap_button else False
        if key == ord('s') or btn_pressed:
            cv2.imwrite("/home/raspberrypi/Documents/temp_screenshot.jpg", display_image)
            p_boxes = []
            for i, (box, score) in enumerate(zip(b_d, s_d)):
                if float(score) > detection_threshold:
                    db = self.map_box_to_original_coords(box, orig_w, orig_h, model_width, model_height)
                    p_boxes.append({"id": str(i), "box": [int(x) for x in db]})
            with open("/home/raspberrypi/Documents/temp_boxes.json", "w") as f: json.dump(p_boxes, f)
            with open("/home/raspberrypi/Documents/trigger.txt", "w") as f: f.write("snap")
            print("🛑 TRIGGER: Exiting for Recognition...")
            return "TRIGGERED"
        if key == ord('q'): return "QUIT"

        # --- 5. 3D FUSION & DATA COLLECTION ---
        all_students_data = []
        for i, (box, score, kp, kp_score) in enumerate(zip(b_d, s_d, k_d, ks_d)):
            if float(score) < detection_threshold or np.isnan(box).any(): continue
            
            det_box = self.map_box_to_original_coords(box, orig_w, orig_h, model_width, model_height)
            mkp = self.map_keypoints_to_original_coords(kp.reshape(17, 2), orig_w, orig_h, model_width, model_height)

            kp_3d = []
            for idx in range(17):
                px, py = int(mkp[idx][0]), int(mkp[idx][1])
                z, ground_h = 0, 0
                if depth_map is not None:
                    roi = depth_map[max(0,py-1):py+2, max(0,px-1):px+2]
                    z = np.median(roi) if roi.size > 0 else 0
                    if z > 0: ground_h = 1200 - ((py - cy) * z / fy)
                kp_3d.append([px, py, z, kp_score[idx], ground_h])

            all_students_data.append({
                "id": i, "box": det_box, "keypoints": kp_3d, 
                "name": self.name_map.get(str(i), f"Student {i+1}"), # 🚀 DEFAULT TO STUDENT X
                "raw_mkp": mkp, "raw_ks": kp_score
            })

        # --- 6. LOGIC & DRAW VPU FACES ---
        processed = self.action_monitor.get_classroom_actions(all_students_data)
        if vpu_faces:
            for f in vpu_faces:
                fx1, fy1 = int(f.xmin * orig_w), int(f.ymin * orig_h)
                fx2, fy2 = int(f.xmax * orig_w), int(f.ymax * orig_h)
                cv2.rectangle(display_image, (fx1, fy1), (fx2, fy2), (255, 255, 255), 1)

        # --- 7. DRAWING & GROUPING ---
        action_groups = {} 
        for st in processed:
            xb, act, col, name = [int(x) for x in st['box']], st['action'], st['color'], st['name']
            dist = st['keypoints'][0][2] / 1000.0
            
            lbl = f"{name} | {act} | {dist:.1f}m"
            cv2.rectangle(display_image, (xb[0], xb[1]), (xb[2], xb[3]), col, 2)
            cv2.rectangle(display_image, (xb[0], xb[1]-25), (xb[0]+320, xb[1]), col, -1)
            cv2.putText(display_image, lbl, (xb[0]+5, xb[1]-7), 1, 0.5, (255,255,255), 1)
            
            for j0, j1 in JOINT_PAIRS:
                if st['raw_ks'][j0] > joint_threshold and st['raw_ks'][j1] > joint_threshold:
                    cv2.line(display_image, (int(st['raw_mkp'][j0][0]), int(st['raw_mkp'][j0][1])), (int(st['raw_mkp'][j1][0]), int(st['raw_mkp'][j1][1])), (0, 255, 255), 2)
            
            aud_n = f"{name} at {dist:.1f} meters" if dist > 0 else name
            if act not in action_groups: action_groups[act] = []
            action_groups[act].append(aud_n)

        # --- 8. SMART AUDIO REPORTING ---
        if not self.report_printed and len(action_groups) > 0:
            full_t = ""
            print("\n📊 CLASSROOM STATUS REPORT:")
            for action, n_list in action_groups.items():
                real = [n for n in n_list if "Student" not in n]
                unkn = sum(1 for n in n_list if "Student" in n)
                parts = []
                if real: parts.append(", ".join(real))
                if unkn == 1: parts.append("1 Student")
                elif unkn > 1: parts.append(f"{unkn} Students")
                
                subject = " and ".join(parts) if parts else "No one"
                verb = "is" if (len(real) + unkn) == 1 else "are"
                line = f"{subject} {verb} {action}."
                print(f"   👉 {line}"); full_t += line + " "
            
            self.report_printed = True
            if AUDIO_ENABLED:
                def speak():
                    try:
                        tts = gTTS(text=full_t, lang='en')
                        tts.save("/home/raspberrypi/Documents/report.mp3")
                        playsound("/home/raspberrypi/Documents/report.mp3")
                        os.remove("/home/raspberrypi/Documents/report.mp3")
                    except: pass
                threading.Thread(target=speak, daemon=True).start()

        fps = 1 / (time.time() - self.prev_time); self.prev_time = time.time()
        cv2.putText(display_image, f"FPS: {fps:.1f}", (20, 40), 1, 1.5, (0, 255, 0), 2)
        return display_image

    def _sigmoid(self, x: np.ndarray) -> np.ndarray:
        """
        Apply sigmoid function.

        Args:
            x (np.ndarray): Input array.

        Returns:
            np.ndarray: Sigmoid transformed array.
        """
        return 1 / (1 + np.exp(-x))

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        """
        Apply softmax function.

        Args:
            x (np.ndarray): Input array.

        Returns:
            np.ndarray: Softmax transformed array.
        """
        return np.exp(x) / np.expand_dims(np.sum(np.exp(x), axis=-1), axis=-1)

    def max_value(self, a: float, b: float) -> float:
        """
        Return the maximum of two values.

        Args:
            a (float): First value.
            b (float): Second value.

        Returns:
            float: The maximum of `a` and `b`.
        """
        return a if a >= b else b

    def min_value(self, a: float, b: float) -> float:
        """
        Return the minimum of two values.

        Args:
            a (float): First value.
            b (float): Second value.

        Returns:
            float: The minimum of `a` and `b`.
        """
        return a if a <= b else b

    def nms(self, dets: np.ndarray, thresh: float) -> np.ndarray:
        """
        Perform Non-Maximum Suppression (NMS) on detection boxes.

        Args:
            dets (np.ndarray): Detection boxes and scores array.
            thresh (float): Overlap threshold for suppression.

        Returns:
            np.ndarray: Indices of the boxes to keep.
        """
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
        """
        Decode the bounding boxes and keypoints from raw predictions.

        Args:
            raw_boxes (np.ndarray): Raw bounding box predictions.
            raw_kpts (np.ndarray): Raw keypoint predictions.
            strides (list[int]): Stride values for each prediction scale.
            image_dims (tuple[int, int]): Dimensions of the input image.
            reg_max (int): Maximum regression value for bounding boxes.

        Returns:
            tuple[np.ndarray, np.ndarray]: Decoded bounding boxes and keypoints.
        """
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
            box_distribute = np.reshape(box_distribute,
                                        (-1,
                                         box_distribute.shape[1] * box_distribute.shape[2],
                                         4,
                                         reg_max + 1))
            box_distance = self._softmax(box_distribute) * np.reshape(reg_range, (1, 1, 1, -1))
            box_distance = np.sum(box_distance, axis=-1) * stride

            box_distance = np.concatenate([box_distance[:, :, :2] * (-1), box_distance[:, :, 2:]],
                                          axis=-1)
            decode_box = np.expand_dims(center, axis=0) + box_distance

            xmin, ymin, xmax, ymax = decode_box[:, :, 0], decode_box[:, :, 1], decode_box[:, :, 2], decode_box[:, :, 3]
            decode_box = np.transpose([xmin, ymin, xmax, ymax], [1, 2, 0])

            xywh_box = np.transpose([(xmin + xmax) / 2,
                                     (ymin + ymax) / 2, xmax - xmin, ymax - ymin], [1, 2, 0])
            boxes = xywh_box if boxes is None else np.concatenate([boxes, xywh_box], axis=1)

            kpts[..., :2] *= 2
            kpts[..., :2] = stride * (kpts[..., :2] - 0.5) + np.expand_dims(center[..., :2], axis=1)
            decoded_kpts = kpts if decoded_kpts is None else np.concatenate([decoded_kpts, kpts],
                                                                            axis=1)

        return boxes, decoded_kpts

    def xywh2xyxy(self, x: np.ndarray) -> np.ndarray:
        """
        Convert bounding boxes from (x, y, w, h) to (xmin, ymin, xmax, ymax) format.

        Args:
            x (np.ndarray): Bounding boxes in (x, y, w, h) format.

        Returns:
            np.ndarray: Bounding boxes in (xmin, ymin, xmax, ymax) format.
        """
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
        """
        Non-Maximum Suppression (NMS) on inference results to reject overlapping detections.

        Args:
            prediction (np.ndarray): Inference results with shape (batch_size, num_proposals, 56).
            conf_thres (float): Confidence threshold for filtering.
            iou_thres (float): Intersection Over Union (IoU) threshold for NMS.
            max_det (int): Maximum number of detections to retain.
            n_kpts (int): Number of keypoints.

        Returns:
            list[dict]: list of dictionaries for each image containing detection results.
        """
        assert 0 <= conf_thres <= 1, f'Invalid confidence threshold {conf_thres}, valid values are between 0.0 and 1.0'
        assert 0 <= iou_thres <= 1, f'Invalid IoU threshold {iou_thres}, valid values are between 0.0 and 1.0'

        nc = prediction.shape[2] - n_kpts * 3 - 4
        xc = prediction[..., 4] > conf_thres
        ki = 4 + nc
        output = []

        for xi, x in enumerate(prediction):
            x = x[xc[xi]]

            if not x.shape[0]:
                output.append({
                    'bboxes': np.zeros((0, 4)),
                    'keypoints': np.zeros((0, n_kpts, 3)),
                    'scores': np.zeros((0)),
                    'num_detections': 0
                })
                continue

            boxes = self.xywh2xyxy(x[:, :4])
            kpts = x[:, ki:]

            conf = np.expand_dims(x[:, 4:ki].max(1), 1)
            j = np.expand_dims(x[:, 4:ki].argmax(1), 1).astype(np.float32)

            keep = np.squeeze(conf, 1) > conf_thres
            x = np.concatenate((boxes, conf, j, kpts), 1)[keep]
            x = x[x[:, 4].argsort()[::-1][:max_det]]

            if not x.shape[0]:
                output.append({
                    'bboxes': np.zeros((0, 4)),
                    'keypoints': np.zeros((0, n_kpts, 3)),
                    'scores': np.zeros((0)),
                    'num_detections': 0
                })
                continue

            boxes = x[:, :4]
            scores = x[:, 4]
            kpts = x[:, 6:].reshape(-1, n_kpts, 3)

            i = self.nms(np.concatenate((boxes, np.expand_dims(scores, 1)), axis=1), iou_thres)
            output.append({
                'bboxes': boxes[i],
                'keypoints': kpts[i],
                'scores': scores[i],
                'num_detections': len(i)
            })

        return output