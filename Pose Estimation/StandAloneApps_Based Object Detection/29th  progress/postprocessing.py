import cv2
import sys
import os
import numpy as np
from scipy.special import expit
from concurrent.futures import ThreadPoolExecutor

try:
    from .cython_nms import nms as cnms
except ImportError:
    pass

try:
    from hailo_apps.python.core.common.toolbox import id_to_color
except ImportError:
    from pathlib import Path
    core_dir = Path(__file__).resolve().parents[3] / "core"
    sys.path.insert(0, str(core_dir))
    from common.toolbox import id_to_color

# --- SENSEY SPATIAL MATH ---
def calculate_spatial_coords(center_x, center_y, depth_frame):
    if depth_frame is None: return None
    h, w = depth_frame.shape
    if center_x >= w or center_y >= h: return None
    roi_size = 6
    region = depth_frame[max(0, center_y-roi_size):min(h, center_y+roi_size), 
                         max(0, center_x-roi_size):min(w, center_x+roi_size)]
    valid = region[(region > 200) & (region < 10000)]
    if len(valid) == 0: return None
    return (0, np.median(valid) / 1000.0)

# --- SENSEY HUD RENDERER ---
def draw_detections(detections, img_out, labels, vio_data=None, target_yaw=None, target_dist=None, depth_frame=None, state_text="IDLE"):
    height, width = img_out.shape[:2]
    center_x = width // 2
    l_lim, r_lim = width // 3, 2 * width // 3 
    
    cv2.line(img_out, (l_lim, 0), (l_lim, height), (255, 255, 255), 1)
    cv2.line(img_out, (r_lim, 0), (r_lim, height), (255, 255, 255), 1)

    if vio_data:
        dist_total, yaw, pitch, roll = vio_data
        hud_yaw = yaw % 360
        
        cv2.rectangle(img_out, (0, 0), (width, 70), (0, 0, 0), -1)
        cv2.line(img_out, (center_x, 10), (center_x, 60), (0, 255, 255), 2) 

        pixels_per_degree = width / 90 
        for deg in range(int(hud_yaw - 45), int(hud_yaw + 45)):
            screen_x = center_x + int((deg - hud_yaw) * pixels_per_degree)
            if 0 < screen_x < width:
                if deg % 15 == 0:
                    cv2.line(img_out, (screen_x, 20), (screen_x, 40), (255, 255, 255), 2)
                    cv2.putText(img_out, str(deg % 360), (screen_x - 10, 60), 0, 0.4, (255, 255, 255), 1)

        if target_yaw is not None:
            relative_angle = (target_yaw - hud_yaw + 180) % 360 - 180
            arrow_x = center_x + int(relative_angle * pixels_per_degree)
            if 0 < arrow_x < width:
                in_center = l_lim <= arrow_x <= r_lim
                color = (0, 255, 0) if in_center else (150, 150, 150)
                pts = np.array([[arrow_x, 15], [arrow_x-10, 5], [arrow_x+10, 5]], np.int32)
                cv2.fillPoly(img_out, [pts], color)
                if target_dist is not None:
                    cv2.putText(img_out, f"{target_dist:.2f}m", (arrow_x - 15, 35), 0, 0.5, color, 2)

        overlay = img_out.copy()
        cv2.rectangle(overlay, (0, height-60), (width, height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, img_out, 0.4, 0, img_out)
        dashboard_text = f"MODE: {state_text} | DIST: {dist_total:.2f}m | YAW: {int(yaw)}' | P: {int(pitch)}' | R: {int(roll)}'"
        cv2.putText(img_out, dashboard_text, (20, height-20), 0, 0.6, (255, 255, 255), 2)

    # 5. Object Segmentation Rendering (Inside draw_detections)
    for idx in range(detections["num_detections"]):
        xmin, ymin, xmax, ymax = map(int, detections["detection_boxes"][idx])
        cls_id = int(detections["detection_classes"][idx])
        
        try: color = tuple(id_to_color(cls_id).tolist())
        except: color = (255, 255, 255)
        
        cx, cy = (xmin + xmax) // 2, (ymin + ymax) // 2
        pos = "[C]" if l_lim <= cx <= r_lim else ("[L]" if cx < l_lim else "[R]")
        
        spatial = ""
        if depth_frame is not None:
            coords = calculate_spatial_coords(cx, cy, depth_frame)
            if coords: spatial = f"{coords[1]:.1f}m"
            
        label_text = f"{labels[cls_id]} {pos} {spatial}"
        
        cv2.rectangle(img_out, (xmin, ymin), (xmax, ymax), color, 2)
        cv2.putText(img_out, label_text, (xmin, ymin - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    return img_out

# --- HAILO NATIVE MASK PROCESSING (From your System Instructions) ---
def _sigmoid(x):
    return 1 / (1 + np.exp(-x))

def _softmax(x):
    return np.exp(x) / np.expand_dims(np.sum(np.exp(x), axis=-1), axis=-1)

def xywh2xyxy(x):
    y = np.copy(x)
    y[:, 0] = x[:, 0] - x[:, 2] / 2
    y[:, 1] = x[:, 1] - x[:, 3] / 2
    y[:, 2] = x[:, 0] + x[:, 2] / 2
    y[:, 3] = x[:, 1] + x[:, 3] / 2
    return y

def crop_mask_roi_vectorized(masks, boxes):
    N, H, W = masks.shape
    output = np.zeros_like(masks)
    boxes = np.round(boxes).astype(int)
    boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, W - 1)
    boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, H - 1)
    for i in range(N):
        x1, y1, x2, y2 = boxes[i]
        output[i, y1:y2, x1:x2] = masks[i, y1:y2, x1:x2]
    return output

def fast_resize_masks(masks, out_shape):
    ih, iw = out_shape
    resized = np.empty((masks.shape[0], ih, iw), dtype=np.float32)
    for i in range(masks.shape[0]):
        resized[i] = cv2.resize(masks[i], (iw, ih), interpolation=cv2.INTER_LINEAR)
    return resized

def process_mask_optimized(protos, masks_in, bboxes, shape, upsample=True, downsample=False):
    mh, mw, c = protos.shape
    ih, iw = shape
    protos_flat = protos.reshape(-1, c).T  
    masks = masks_in @ protos_flat  
    masks = expit(masks).reshape(-1, mh, mw)  
    bboxes = bboxes.copy()
    if downsample:
        bboxes[:, [0, 2]] *= mw / iw
        bboxes[:, [1, 3]] *= mh / ih
        masks = crop_mask_roi_vectorized(masks, bboxes)
    if upsample:
        masks = fast_resize_masks(masks, (ih, iw))
    if not downsample:
        masks = crop_mask_roi_vectorized(masks, bboxes)
    return masks

def non_max_suppression(prediction, conf_thres=0.25, iou_thres=0.45, max_det=300, nm=32, multi_label=True):
    nc = prediction.shape[2] - nm - 5  
    xc = prediction[..., 4] > conf_thres  
    max_wh = 7680  
    mi = 5 + nc  
    output = []
    for xi, x in enumerate(prediction):  
        x = x[xc[xi]]  
        if not x.shape[0]:
            output.append({"detection_boxes": np.zeros((0, 4)), "mask": np.zeros((0, 32)), "detection_classes": np.zeros((0, 80)), "detection_scores": np.zeros((0, 80))})
            continue
        x[:, 5:] *= x[:, 4:5]
        boxes = xywh2xyxy(x[:, :4])
        mask = x[:, mi:]
        multi_label &= nc > 1
        if not multi_label:
            conf = np.expand_dims(x[:, 5:mi].max(1), 1)
            j = np.expand_dims(x[:, 5:mi].argmax(1), 1).astype(np.float32)
            keep = np.squeeze(conf, 1) > conf_thres
            x = np.concatenate((boxes, conf, j, mask), 1)[keep]
        else:
            i, j = (x[:, 5:mi] > conf_thres).nonzero()
            x = np.concatenate((boxes[i], x[i, 5 + j, None], j[:, None].astype(np.float32), mask[i]), 1)
        x = x[x[:, 4].argsort()[::-1]]
        cls_shift = x[:, 5:6] * max_wh
        boxes = x[:, :4] + cls_shift
        conf = x[:, 4:5]
        preds = np.hstack([boxes.astype(np.float32), conf.astype(np.float32)])
        
        try: keep = cnms(preds, iou_thres)
        except: 
            # Fallback if cython_nms fails
            keep = cv2.dnn.NMSBoxes(boxes.tolist(), conf.tolist(), conf_thres, iou_thres)
            keep = np.array(keep).flatten() if len(keep) > 0 else np.array([])
            
        if keep.shape[0] > max_det: keep = keep[:max_det]
        out = x[keep]
        output.append({"detection_boxes": out[:, :4], "mask": out[:, 6:], "detection_classes": out[:, 5], "detection_scores": out[:, 4]})
    return output

def _yolov8_decoding(raw_boxes, strides, image_dims, reg_max):
    boxes = None
    for box_distribute, stride in zip(raw_boxes, strides):
        shape = [int(x / stride) for x in image_dims]
        grid_x = np.arange(shape[1]) + 0.5
        grid_y = np.arange(shape[0]) + 0.5
        grid_x, grid_y = np.meshgrid(grid_x, grid_y)
        ct_row = grid_y.flatten() * stride
        ct_col = grid_x.flatten() * stride
        center = np.stack((ct_col, ct_row, ct_col, ct_row), axis=1)
        reg_range = np.arange(reg_max + 1)
        box_distribute = np.reshape(box_distribute, (-1, box_distribute.shape[1] * box_distribute.shape[2], 4, reg_max + 1))
        box_distance = _softmax(box_distribute)
        box_distance = box_distance * np.reshape(reg_range, (1, 1, 1, -1))
        box_distance = np.sum(box_distance, axis=-1) * stride
        box_distance = np.concatenate([box_distance[:, :, :2] * (-1), box_distance[:, :, 2:]], axis=-1)
        decode_box = np.expand_dims(center, axis=0) + box_distance
        xmin, ymin, xmax, ymax = decode_box[:, :, 0], decode_box[:, :, 1], decode_box[:, :, 2], decode_box[:, :, 3]
        xywh_box = np.transpose([(xmin + xmax) / 2, (ymin + ymax) / 2, xmax - xmin, ymax - ymin], [1, 2, 0])
        boxes = xywh_box if boxes is None else np.concatenate([boxes, xywh_box], axis=1)
    return boxes

def yolov8_seg_postprocess(endnodes, **kwargs):
    """
    🚀 HAILO V8 SEGMENTATION LOGIC
    """
    num_classes = kwargs["classes"]
    strides = kwargs["anchors"]["strides"][::-1]
    image_dims = tuple(kwargs["input_shape"])
    reg_max = kwargs["anchors"]["regression_length"]
    
    raw_boxes = endnodes[:7:3]
    scores = np.concatenate([np.reshape(s, (-1, s.shape[1] * s.shape[2], num_classes)) for s in endnodes[1:8:3]], axis=1)
    coeffs = np.concatenate([np.reshape(c, (-1, c.shape[1] * c.shape[2], endnodes[9].shape[-1])) for c in endnodes[2:9:3]], axis=1)
    
    decoded_boxes = _yolov8_decoding(raw_boxes, strides, image_dims, reg_max)
    
    fake_objectness = np.ones((scores.shape[0], scores.shape[1], 1))
    scores_obj = np.concatenate([fake_objectness, scores], axis=-1)
    
    predictions = np.concatenate([decoded_boxes, scores_obj, coeffs], axis=2)
    nms_res = non_max_suppression(predictions, conf_thres=kwargs["score_threshold"], iou_thres=kwargs["nms_iou_thresh"], multi_label=True)

    outputs = []
    proto_data = endnodes[9]
    batch_size = proto_data.shape[0]
    
    for b in range(batch_size):
        protos = proto_data[b].astype(np.float32, copy=False)
        masks_in = nms_res[b]["mask"].astype(np.float32, copy=False)
        
        # 🚀 MAGIC: Generate the pixel-perfect masks!
        masks = process_mask_optimized(protos, masks_in, nms_res[b]["detection_boxes"], image_dims)
        
        output = {
            "detection_boxes": np.array(nms_res[b]["detection_boxes"]) / np.tile(image_dims, 2),
            "mask": masks,
            "detection_scores": np.array(nms_res[b]["detection_scores"]),
            "detection_classes": np.array(nms_res[b]["detection_classes"]).astype(int)
        }
        outputs.append(output)
    return outputs

def decode_and_postprocess(raw_detections, config_data, arch_key):
    arch_cfg = config_data[arch_key]
    layers = arch_cfg["layers"]
    mask_channels = arch_cfg["mask_channels"]
    raw_detections_keys = list(raw_detections.keys())
    layer_from_shape = {raw_detections[key].shape: key for key in raw_detections_keys}

    def resolve_shape(layer):
        b, h, w, c_tag = layer
        if isinstance(c_tag, str):
            if c_tag == "mask_channels": c = mask_channels
            elif c_tag == "detection_output_channels": c = (arch_cfg['anchors']['regression_length'] + 1) * 4
            elif c_tag == "classes": c = arch_cfg["classes"]
            else: raise ValueError(f"Unsupported channel tag: {c_tag}")
        else: c = c_tag
        return (b, h, w, c)

    endnodes = [raw_detections[layer_from_shape[resolve_shape(layer)]] for layer in layers]
    return yolov8_seg_postprocess(endnodes, **arch_cfg)[0]

# --- THE MAIN ENTRY POINT ---
def inference_result_handler(original_frame, infer_results, labels, config_data, tracker=None, vio_data=None, target_yaw=None, target_dist=None, depth_frame=None, state_text="IDLE", get_mask=False, model_type="v8"):
    h, w = original_frame.shape[:2]
    master_mask = np.zeros((h, w), dtype=np.uint8)
    formatted_detections = []
    
    # 1. Decode Results
    decoded = decode_and_postprocess(infer_results, config_data, model_type)
    
    # 🚀 FIX: Handle potential list or dict return types safely
    if isinstance(decoded, list):
        decoded = decoded[0] if len(decoded) > 0 else {}
        
    # 🚀 FIX: Dynamic key finding (Handles 'boxes' vs 'detection_boxes')
    boxes = decoded.get("detection_boxes", decoded.get("boxes", []))
    classes = decoded.get("detection_classes", decoded.get("class_ids", []))
    scores = decoded.get("detection_scores", decoded.get("scores", []))
    masks = decoded.get("mask", decoded.get("masks", None))
    
    if len(boxes) > 0:
        # Scale boxes if they are normalized (0.0 to 1.0)
        boxes = np.array(boxes).copy()
        if boxes.max() <= 1.0:
            boxes[:, [0, 2]] *= w
            boxes[:, [1, 3]] *= h
            
        for idx in range(len(boxes)):
            score = float(scores[idx])
            if score < config_data["visualization_params"].get("score_thres", 0.45): 
                continue
            
            class_id = int(classes[idx])
            xmin, ymin, xmax, ymax = map(int, boxes[idx])
            
            # Prevent out-of-bounds
            xmin, ymin = max(0, xmin), max(0, ymin)
            xmax, ymax = min(w, xmax), min(h, ymax)
            
            formatted_detections.append({
                "class_id": class_id,
                "score": score,
                "bbox": [xmin, ymin, xmax, ymax]
            })
            
            # 2. Mask Generation
            if get_mask and "mask" in decoded and len(decoded["mask"]) > idx:
                mask_2d = decoded["mask"][idx]
                binary_mask = (mask_2d > 0.5).astype(np.uint8)
                    
                if binary_mask.shape[:2] != (h, w):
                    binary_mask = cv2.resize(binary_mask, (w, h), interpolation=cv2.INTER_NEAREST)
                    
                    # Update the Master Mask for the Exploration Engine
                    master_mask = cv2.bitwise_or(master_mask, binary_mask)
                    
                try:
                        # Use your toolbox to get the unique color
                    color = tuple(id_to_color(class_id).tolist())
                except:
                    color = (0, 100, 255) # Fallback orange
                    
                    # Apply color only to the binary mask pixels
                mask_indices = binary_mask > 0
                    
                    # Create a colored version of the frame
                colored_overlay = original_frame.copy()
                colored_overlay[mask_indices] = color
                    
                    # Blend the colored mask over the original frame
                original_frame[:] = cv2.addWeighted(original_frame, 0.6, colored_overlay, 0.4, 0)

    # 3. Draw HUD 
    output_dict = {
        "num_detections": len(formatted_detections),
        "detection_boxes": [d["bbox"] for d in formatted_detections],
        "detection_classes": [d["class_id"] for d in formatted_detections],
        "detection_scores": [d["score"] for d in formatted_detections]
    }
    
    output_frame = draw_detections(output_dict, original_frame, labels, 
                                   vio_data=vio_data, target_yaw=target_yaw, 
                                   target_dist=target_dist, depth_frame=depth_frame, 
                                   state_text=state_text)

    # 🚀 FIX: Final return structure to match exploration loop
    if get_mask:
        return output_frame, master_mask, formatted_detections
    return output_frame, formatted_detections
    l_lim, r_lim = width // 3, 2 * width // 3 
    
    cv2.line(img_out, (l_lim, 0), (l_lim, height), (255, 255, 255), 1)
    cv2.line(img_out, (r_lim, 0), (r_lim, height), (255, 255, 255), 1)

    if vio_data:
        dist_total, yaw, pitch, roll = vio_data
        hud_yaw = yaw % 360
        
        cv2.rectangle(img_out, (0, 0), (width, 70), (0, 0, 0), -1)
        cv2.line(img_out, (center_x, 10), (center_x, 60), (0, 255, 255), 2) 

        pixels_per_degree = width / 90 
        for deg in range(int(hud_yaw - 45), int(hud_yaw + 45)):
            screen_x = center_x + int((deg - hud_yaw) * pixels_per_degree)
            if 0 < screen_x < width:
                if deg % 15 == 0:
                    cv2.line(img_out, (screen_x, 20), (screen_x, 40), (255, 255, 255), 2)
                    cv2.putText(img_out, str(deg % 360), (screen_x - 10, 60), 0, 0.4, (255, 255, 255), 1)

        if target_yaw is not None:
            relative_angle = (target_yaw - hud_yaw + 180) % 360 - 180
            arrow_x = center_x + int(relative_angle * pixels_per_degree)
            if 0 < arrow_x < width:
                in_center = l_lim <= arrow_x <= r_lim
                color = (0, 255, 0) if in_center else (150, 150, 150)
                pts = np.array([[arrow_x, 15], [arrow_x-10, 5], [arrow_x+10, 5]], np.int32)
                cv2.fillPoly(img_out, [pts], color)
                if target_dist is not None:
                    cv2.putText(img_out, f"{target_dist:.2f}m", (arrow_x - 15, 35), 0, 0.5, color, 2)

        overlay = img_out.copy()
        cv2.rectangle(overlay, (0, height-60), (width, height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, img_out, 0.4, 0, img_out)
        dashboard_text = f"MODE: {state_text} | DIST: {dist_total:.2f}m | YAW: {int(yaw)}' | P: {int(pitch)}' | R: {int(roll)}'"
        cv2.putText(img_out, dashboard_text, (20, height-20), 0, 0.6, (255, 255, 255), 2)

    # 5. Object Segmentation Rendering (Inside draw_detections)
    for idx in range(detections["num_detections"]):
        xmin, ymin, xmax, ymax = map(int, detections["detection_boxes"][idx])
        cls_id = int(detections["detection_classes"][idx])
        
        try: color = tuple(id_to_color(cls_id).tolist())
        except: color = (255, 255, 255)
        
        cx, cy = (xmin + xmax) // 2, (ymin + ymax) // 2
        pos = "[C]" if l_lim <= cx <= r_lim else ("[L]" if cx < l_lim else "[R]")
        
        spatial = ""
        if depth_frame is not None:
            coords = calculate_spatial_coords(cx, cy, depth_frame)
            if coords: spatial = f"{coords[1]:.1f}m"
            
        label_text = f"{labels[cls_id]} {pos} {spatial}"
        
        cv2.rectangle(img_out, (xmin, ymin), (xmax, ymax), color, 2)
        cv2.putText(img_out, label_text, (xmin, ymin - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    return img_out

# --- HAILO NATIVE MASK PROCESSING (From your System Instructions) ---
def _sigmoid(x):
    return 1 / (1 + np.exp(-x))

def _softmax(x):
    return np.exp(x) / np.expand_dims(np.sum(np.exp(x), axis=-1), axis=-1)

def xywh2xyxy(x):
    y = np.copy(x)
    y[:, 0] = x[:, 0] - x[:, 2] / 2
    y[:, 1] = x[:, 1] - x[:, 3] / 2
    y[:, 2] = x[:, 0] + x[:, 2] / 2
    y[:, 3] = x[:, 1] + x[:, 3] / 2
    return y

def crop_mask_roi_vectorized(masks, boxes):
    N, H, W = masks.shape
    output = np.zeros_like(masks)
    boxes = np.round(boxes).astype(int)
    boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, W - 1)
    boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, H - 1)
    for i in range(N):
        x1, y1, x2, y2 = boxes[i]
        output[i, y1:y2, x1:x2] = masks[i, y1:y2, x1:x2]
    return output

def fast_resize_masks(masks, out_shape):
    ih, iw = out_shape
    resized = np.empty((masks.shape[0], ih, iw), dtype=np.float32)
    for i in range(masks.shape[0]):
        resized[i] = cv2.resize(masks[i], (iw, ih), interpolation=cv2.INTER_LINEAR)
    return resized

def process_mask_optimized(protos, masks_in, bboxes, shape, upsample=True, downsample=False):
    mh, mw, c = protos.shape
    ih, iw = shape
    protos_flat = protos.reshape(-1, c).T  
    masks = masks_in @ protos_flat  
    masks = expit(masks).reshape(-1, mh, mw)  
    bboxes = bboxes.copy()
    if downsample:
        bboxes[:, [0, 2]] *= mw / iw
        bboxes[:, [1, 3]] *= mh / ih
        masks = crop_mask_roi_vectorized(masks, bboxes)
    if upsample:
        masks = fast_resize_masks(masks, (ih, iw))
    if not downsample:
        masks = crop_mask_roi_vectorized(masks, bboxes)
    return masks

def non_max_suppression(prediction, conf_thres=0.25, iou_thres=0.45, max_det=300, nm=32, multi_label=True):
    nc = prediction.shape[2] - nm - 5  
    xc = prediction[..., 4] > conf_thres  
    max_wh = 7680  
    mi = 5 + nc  
    output = []
    for xi, x in enumerate(prediction):  
        x = x[xc[xi]]  
        if not x.shape[0]:
            output.append({"detection_boxes": np.zeros((0, 4)), "mask": np.zeros((0, 32)), "detection_classes": np.zeros((0, 80)), "detection_scores": np.zeros((0, 80))})
            continue
        x[:, 5:] *= x[:, 4:5]
        boxes = xywh2xyxy(x[:, :4])
        mask = x[:, mi:]
        multi_label &= nc > 1
        if not multi_label:
            conf = np.expand_dims(x[:, 5:mi].max(1), 1)
            j = np.expand_dims(x[:, 5:mi].argmax(1), 1).astype(np.float32)
            keep = np.squeeze(conf, 1) > conf_thres
            x = np.concatenate((boxes, conf, j, mask), 1)[keep]
        else:
            i, j = (x[:, 5:mi] > conf_thres).nonzero()
            x = np.concatenate((boxes[i], x[i, 5 + j, None], j[:, None].astype(np.float32), mask[i]), 1)
        x = x[x[:, 4].argsort()[::-1]]
        cls_shift = x[:, 5:6] * max_wh
        boxes = x[:, :4] + cls_shift
        conf = x[:, 4:5]
        preds = np.hstack([boxes.astype(np.float32), conf.astype(np.float32)])
        
        try: keep = cnms(preds, iou_thres)
        except: 
            # Fallback if cython_nms fails
            keep = cv2.dnn.NMSBoxes(boxes.tolist(), conf.tolist(), conf_thres, iou_thres)
            keep = np.array(keep).flatten() if len(keep) > 0 else np.array([])
            
        if keep.shape[0] > max_det: keep = keep[:max_det]
        out = x[keep]
        output.append({"detection_boxes": out[:, :4], "mask": out[:, 6:], "detection_classes": out[:, 5], "detection_scores": out[:, 4]})
    return output

def _yolov8_decoding(raw_boxes, strides, image_dims, reg_max):
    boxes = None
    for box_distribute, stride in zip(raw_boxes, strides):
        shape = [int(x / stride) for x in image_dims]
        grid_x = np.arange(shape[1]) + 0.5
        grid_y = np.arange(shape[0]) + 0.5
        grid_x, grid_y = np.meshgrid(grid_x, grid_y)
        ct_row = grid_y.flatten() * stride
        ct_col = grid_x.flatten() * stride
        center = np.stack((ct_col, ct_row, ct_col, ct_row), axis=1)
        reg_range = np.arange(reg_max + 1)
        box_distribute = np.reshape(box_distribute, (-1, box_distribute.shape[1] * box_distribute.shape[2], 4, reg_max + 1))
        box_distance = _softmax(box_distribute)
        box_distance = box_distance * np.reshape(reg_range, (1, 1, 1, -1))
        box_distance = np.sum(box_distance, axis=-1) * stride
        box_distance = np.concatenate([box_distance[:, :, :2] * (-1), box_distance[:, :, 2:]], axis=-1)
        decode_box = np.expand_dims(center, axis=0) + box_distance
        xmin, ymin, xmax, ymax = decode_box[:, :, 0], decode_box[:, :, 1], decode_box[:, :, 2], decode_box[:, :, 3]
        xywh_box = np.transpose([(xmin + xmax) / 2, (ymin + ymax) / 2, xmax - xmin, ymax - ymin], [1, 2, 0])
        boxes = xywh_box if boxes is None else np.concatenate([boxes, xywh_box], axis=1)
    return boxes

def yolov8_seg_postprocess(endnodes, **kwargs):
    """
    🚀 HAILO V8 SEGMENTATION LOGIC
    """
    num_classes = kwargs["classes"]
    strides = kwargs["anchors"]["strides"][::-1]
    image_dims = tuple(kwargs["input_shape"])
    reg_max = kwargs["anchors"]["regression_length"]
    
    raw_boxes = endnodes[:7:3]
    scores = np.concatenate([np.reshape(s, (-1, s.shape[1] * s.shape[2], num_classes)) for s in endnodes[1:8:3]], axis=1)
    coeffs = np.concatenate([np.reshape(c, (-1, c.shape[1] * c.shape[2], endnodes[9].shape[-1])) for c in endnodes[2:9:3]], axis=1)
    
    decoded_boxes = _yolov8_decoding(raw_boxes, strides, image_dims, reg_max)
    
    fake_objectness = np.ones((scores.shape[0], scores.shape[1], 1))
    scores_obj = np.concatenate([fake_objectness, scores], axis=-1)
    
    predictions = np.concatenate([decoded_boxes, scores_obj, coeffs], axis=2)
    nms_res = non_max_suppression(predictions, conf_thres=kwargs["score_threshold"], iou_thres=kwargs["nms_iou_thresh"], multi_label=True)

    outputs = []
    proto_data = endnodes[9]
    batch_size = proto_data.shape[0]
    
    for b in range(batch_size):
        protos = proto_data[b].astype(np.float32, copy=False)
        masks_in = nms_res[b]["mask"].astype(np.float32, copy=False)
        
        # 🚀 MAGIC: Generate the pixel-perfect masks!
        masks = process_mask_optimized(protos, masks_in, nms_res[b]["detection_boxes"], image_dims)
        
        output = {
            "detection_boxes": np.array(nms_res[b]["detection_boxes"]) / np.tile(image_dims, 2),
            "mask": masks,
            "detection_scores": np.array(nms_res[b]["detection_scores"]),
            "detection_classes": np.array(nms_res[b]["detection_classes"]).astype(int)
        }
        outputs.append(output)
    return outputs

def decode_and_postprocess(raw_detections, config_data, arch_key):
    arch_cfg = config_data[arch_key]
    layers = arch_cfg["layers"]
    mask_channels = arch_cfg["mask_channels"]
    raw_detections_keys = list(raw_detections.keys())
    layer_from_shape = {raw_detections[key].shape: key for key in raw_detections_keys}

    def resolve_shape(layer):
        b, h, w, c_tag = layer
        if isinstance(c_tag, str):
            if c_tag == "mask_channels": c = mask_channels
            elif c_tag == "detection_output_channels": c = (arch_cfg['anchors']['regression_length'] + 1) * 4
            elif c_tag == "classes": c = arch_cfg["classes"]
            else: raise ValueError(f"Unsupported channel tag: {c_tag}")
        else: c = c_tag
        return (b, h, w, c)

    endnodes = [raw_detections[layer_from_shape[resolve_shape(layer)]] for layer in layers]
    return yolov8_seg_postprocess(endnodes, **arch_cfg)[0]

# --- THE MAIN ENTRY POINT ---
def inference_result_handler(original_frame, infer_results, labels, config_data, tracker=None, vio_data=None, target_yaw=None, target_dist=None, depth_frame=None, state_text="IDLE", get_mask=False, model_type="v8"):
    h, w = original_frame.shape[:2]
    master_mask = np.zeros((h, w), dtype=np.uint8)
    formatted_detections = []
    
    # 1. Decode Results
    decoded = decode_and_postprocess(infer_results, config_data, model_type)
    
    # 🚀 FIX: Handle potential list or dict return types safely
    if isinstance(decoded, list):
        decoded = decoded[0] if len(decoded) > 0 else {}
        
    # 🚀 FIX: Dynamic key finding (Handles 'boxes' vs 'detection_boxes')
    boxes = decoded.get("detection_boxes", decoded.get("boxes", []))
    classes = decoded.get("detection_classes", decoded.get("class_ids", []))
    scores = decoded.get("detection_scores", decoded.get("scores", []))
    masks = decoded.get("mask", decoded.get("masks", None))
    
    if len(boxes) > 0:
        # Scale boxes if they are normalized (0.0 to 1.0)
        boxes = np.array(boxes).copy()
        if boxes.max() <= 1.0:
            boxes[:, [0, 2]] *= w
            boxes[:, [1, 3]] *= h
            
        for idx in range(len(boxes)):
            score = float(scores[idx])
            if score < config_data["visualization_params"].get("score_thres", 0.45): 
                continue
            
            class_id = int(classes[idx])
            xmin, ymin, xmax, ymax = map(int, boxes[idx])
            
            # Prevent out-of-bounds
            xmin, ymin = max(0, xmin), max(0, ymin)
            xmax, ymax = min(w, xmax), min(h, ymax)
            
            formatted_detections.append({
                "class_id": class_id,
                "score": score,
                "bbox": [xmin, ymin, xmax, ymax]
            })
            
            # 2. Mask Generation
            if get_mask and "mask" in decoded and len(decoded["mask"]) > idx:
                mask_2d = decoded["mask"][idx]
                binary_mask = (mask_2d > 0.5).astype(np.uint8)
                    
                if binary_mask.shape[:2] != (h, w):
                    binary_mask = cv2.resize(binary_mask, (w, h), interpolation=cv2.INTER_NEAREST)
                    
                    # Update the Master Mask for the Exploration Engine
                    master_mask = cv2.bitwise_or(master_mask, binary_mask)
                    
                try:
                        # Use your toolbox to get the unique color
                    color = tuple(id_to_color(class_id).tolist())
                except:
                    color = (0, 100, 255) # Fallback orange
                    
                    # Apply color only to the binary mask pixels
                mask_indices = binary_mask > 0
                    
                    # Create a colored version of the frame
                colored_overlay = original_frame.copy()
                colored_overlay[mask_indices] = color
                    
                    # Blend the colored mask over the original frame
                original_frame[:] = cv2.addWeighted(original_frame, 0.6, colored_overlay, 0.4, 0)

    # 3. Draw HUD 
    output_dict = {
        "num_detections": len(formatted_detections),
        "detection_boxes": [d["bbox"] for d in formatted_detections],
        "detection_classes": [d["class_id"] for d in formatted_detections],
        "detection_scores": [d["score"] for d in formatted_detections]
    }
    
    output_frame = draw_detections(output_dict, original_frame, labels, 
                                   vio_data=vio_data, target_yaw=target_yaw, 
                                   target_dist=target_dist, depth_frame=depth_frame, 
                                   state_text=state_text)

    # 🚀 FIX: Final return structure to match exploration loop
    if get_mask:
        return output_frame, master_mask, formatted_detections
    return output_frame, formatted_detections
    l_lim, r_lim = width // 3, 2 * width // 3 
    
    cv2.line(img_out, (l_lim, 0), (l_lim, height), (255, 255, 255), 1)
    cv2.line(img_out, (r_lim, 0), (r_lim, height), (255, 255, 255), 1)

    if vio_data:
        dist_total, yaw, pitch, roll = vio_data
        hud_yaw = yaw % 360
        
        cv2.rectangle(img_out, (0, 0), (width, 70), (0, 0, 0), -1)
        cv2.line(img_out, (center_x, 10), (center_x, 60), (0, 255, 255), 2) 

        pixels_per_degree = width / 90 
        for deg in range(int(hud_yaw - 45), int(hud_yaw + 45)):
            screen_x = center_x + int((deg - hud_yaw) * pixels_per_degree)
            if 0 < screen_x < width:
                if deg % 15 == 0:
                    cv2.line(img_out, (screen_x, 20), (screen_x, 40), (255, 255, 255), 2)
                    cv2.putText(img_out, str(deg % 360), (screen_x - 10, 60), 0, 0.4, (255, 255, 255), 1)

        if target_yaw is not None:
            relative_angle = (target_yaw - hud_yaw + 180) % 360 - 180
            arrow_x = center_x + int(relative_angle * pixels_per_degree)
            if 0 < arrow_x < width:
                in_center = l_lim <= arrow_x <= r_lim
                color = (0, 255, 0) if in_center else (150, 150, 150)
                pts = np.array([[arrow_x, 15], [arrow_x-10, 5], [arrow_x+10, 5]], np.int32)
                cv2.fillPoly(img_out, [pts], color)
                if target_dist is not None:
                    cv2.putText(img_out, f"{target_dist:.2f}m", (arrow_x - 15, 35), 0, 0.5, color, 2)

        overlay = img_out.copy()
        cv2.rectangle(overlay, (0, height-60), (width, height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, img_out, 0.4, 0, img_out)
        dashboard_text = f"MODE: {state_text} | DIST: {dist_total:.2f}m | YAW: {int(yaw)}' | P: {int(pitch)}' | R: {int(roll)}'"
        cv2.putText(img_out, dashboard_text, (20, height-20), 0, 0.6, (255, 255, 255), 2)

    # 5. Object Segmentation Rendering (Inside draw_detections)
    for idx in range(detections["num_detections"]):
        xmin, ymin, xmax, ymax = map(int, detections["detection_boxes"][idx])
        cls_id = int(detections["detection_classes"][idx])
        
        try: color = tuple(id_to_color(cls_id).tolist())
        except: color = (255, 255, 255)
        
        cx, cy = (xmin + xmax) // 2, (ymin + ymax) // 2
        pos = "[C]" if l_lim <= cx <= r_lim else ("[L]" if cx < l_lim else "[R]")
        
        spatial = ""
        if depth_frame is not None:
            coords = calculate_spatial_coords(cx, cy, depth_frame)
            if coords: spatial = f"{coords[1]:.1f}m"
            
        label_text = f"{labels[cls_id]} {pos} {spatial}"
        
        cv2.rectangle(img_out, (xmin, ymin), (xmax, ymax), color, 2)
        cv2.putText(img_out, label_text, (xmin, ymin - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    return img_out

# --- HAILO NATIVE MASK PROCESSING (From your System Instructions) ---
def _sigmoid(x):
    return 1 / (1 + np.exp(-x))

def _softmax(x):
    return np.exp(x) / np.expand_dims(np.sum(np.exp(x), axis=-1), axis=-1)

def xywh2xyxy(x):
    y = np.copy(x)
    y[:, 0] = x[:, 0] - x[:, 2] / 2
    y[:, 1] = x[:, 1] - x[:, 3] / 2
    y[:, 2] = x[:, 0] + x[:, 2] / 2
    y[:, 3] = x[:, 1] + x[:, 3] / 2
    return y

def crop_mask_roi_vectorized(masks, boxes):
    N, H, W = masks.shape
    output = np.zeros_like(masks)
    boxes = np.round(boxes).astype(int)
    boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, W - 1)
    boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, H - 1)
    for i in range(N):
        x1, y1, x2, y2 = boxes[i]
        output[i, y1:y2, x1:x2] = masks[i, y1:y2, x1:x2]
    return output

def fast_resize_masks(masks, out_shape):
    ih, iw = out_shape
    resized = np.empty((masks.shape[0], ih, iw), dtype=np.float32)
    for i in range(masks.shape[0]):
        resized[i] = cv2.resize(masks[i], (iw, ih), interpolation=cv2.INTER_LINEAR)
    return resized

def process_mask_optimized(protos, masks_in, bboxes, shape, upsample=True, downsample=False):
    mh, mw, c = protos.shape
    ih, iw = shape
    protos_flat = protos.reshape(-1, c).T  
    masks = masks_in @ protos_flat  
    masks = expit(masks).reshape(-1, mh, mw)  
    bboxes = bboxes.copy()
    if downsample:
        bboxes[:, [0, 2]] *= mw / iw
        bboxes[:, [1, 3]] *= mh / ih
        masks = crop_mask_roi_vectorized(masks, bboxes)
    if upsample:
        masks = fast_resize_masks(masks, (ih, iw))
    if not downsample:
        masks = crop_mask_roi_vectorized(masks, bboxes)
    return masks

def non_max_suppression(prediction, conf_thres=0.25, iou_thres=0.45, max_det=300, nm=32, multi_label=True):
    nc = prediction.shape[2] - nm - 5  
    xc = prediction[..., 4] > conf_thres  
    max_wh = 7680  
    mi = 5 + nc  
    output = []
    for xi, x in enumerate(prediction):  
        x = x[xc[xi]]  
        if not x.shape[0]:
            output.append({"detection_boxes": np.zeros((0, 4)), "mask": np.zeros((0, 32)), "detection_classes": np.zeros((0, 80)), "detection_scores": np.zeros((0, 80))})
            continue
        x[:, 5:] *= x[:, 4:5]
        boxes = xywh2xyxy(x[:, :4])
        mask = x[:, mi:]
        multi_label &= nc > 1
        if not multi_label:
            conf = np.expand_dims(x[:, 5:mi].max(1), 1)
            j = np.expand_dims(x[:, 5:mi].argmax(1), 1).astype(np.float32)
            keep = np.squeeze(conf, 1) > conf_thres
            x = np.concatenate((boxes, conf, j, mask), 1)[keep]
        else:
            i, j = (x[:, 5:mi] > conf_thres).nonzero()
            x = np.concatenate((boxes[i], x[i, 5 + j, None], j[:, None].astype(np.float32), mask[i]), 1)
        x = x[x[:, 4].argsort()[::-1]]
        cls_shift = x[:, 5:6] * max_wh
        boxes = x[:, :4] + cls_shift
        conf = x[:, 4:5]
        preds = np.hstack([boxes.astype(np.float32), conf.astype(np.float32)])
        
        try: keep = cnms(preds, iou_thres)
        except: 
            # Fallback if cython_nms fails
            keep = cv2.dnn.NMSBoxes(boxes.tolist(), conf.tolist(), conf_thres, iou_thres)
            keep = np.array(keep).flatten() if len(keep) > 0 else np.array([])
            
        if keep.shape[0] > max_det: keep = keep[:max_det]
        out = x[keep]
        output.append({"detection_boxes": out[:, :4], "mask": out[:, 6:], "detection_classes": out[:, 5], "detection_scores": out[:, 4]})
    return output

def _yolov8_decoding(raw_boxes, strides, image_dims, reg_max):
    boxes = None
    for box_distribute, stride in zip(raw_boxes, strides):
        shape = [int(x / stride) for x in image_dims]
        grid_x = np.arange(shape[1]) + 0.5
        grid_y = np.arange(shape[0]) + 0.5
        grid_x, grid_y = np.meshgrid(grid_x, grid_y)
        ct_row = grid_y.flatten() * stride
        ct_col = grid_x.flatten() * stride
        center = np.stack((ct_col, ct_row, ct_col, ct_row), axis=1)
        reg_range = np.arange(reg_max + 1)
        box_distribute = np.reshape(box_distribute, (-1, box_distribute.shape[1] * box_distribute.shape[2], 4, reg_max + 1))
        box_distance = _softmax(box_distribute)
        box_distance = box_distance * np.reshape(reg_range, (1, 1, 1, -1))
        box_distance = np.sum(box_distance, axis=-1) * stride
        box_distance = np.concatenate([box_distance[:, :, :2] * (-1), box_distance[:, :, 2:]], axis=-1)
        decode_box = np.expand_dims(center, axis=0) + box_distance
        xmin, ymin, xmax, ymax = decode_box[:, :, 0], decode_box[:, :, 1], decode_box[:, :, 2], decode_box[:, :, 3]
        xywh_box = np.transpose([(xmin + xmax) / 2, (ymin + ymax) / 2, xmax - xmin, ymax - ymin], [1, 2, 0])
        boxes = xywh_box if boxes is None else np.concatenate([boxes, xywh_box], axis=1)
    return boxes

def yolov8_seg_postprocess(endnodes, **kwargs):
    """
    🚀 HAILO V8 SEGMENTATION LOGIC
    """
    num_classes = kwargs["classes"]
    strides = kwargs["anchors"]["strides"][::-1]
    image_dims = tuple(kwargs["input_shape"])
    reg_max = kwargs["anchors"]["regression_length"]
    
    raw_boxes = endnodes[:7:3]
    scores = np.concatenate([np.reshape(s, (-1, s.shape[1] * s.shape[2], num_classes)) for s in endnodes[1:8:3]], axis=1)
    coeffs = np.concatenate([np.reshape(c, (-1, c.shape[1] * c.shape[2], endnodes[9].shape[-1])) for c in endnodes[2:9:3]], axis=1)
    
    decoded_boxes = _yolov8_decoding(raw_boxes, strides, image_dims, reg_max)
    
    fake_objectness = np.ones((scores.shape[0], scores.shape[1], 1))
    scores_obj = np.concatenate([fake_objectness, scores], axis=-1)
    
    predictions = np.concatenate([decoded_boxes, scores_obj, coeffs], axis=2)
    nms_res = non_max_suppression(predictions, conf_thres=kwargs["score_threshold"], iou_thres=kwargs["nms_iou_thresh"], multi_label=True)

    outputs = []
    proto_data = endnodes[9]
    batch_size = proto_data.shape[0]
    
    for b in range(batch_size):
        protos = proto_data[b].astype(np.float32, copy=False)
        masks_in = nms_res[b]["mask"].astype(np.float32, copy=False)
        
        # 🚀 MAGIC: Generate the pixel-perfect masks!
        masks = process_mask_optimized(protos, masks_in, nms_res[b]["detection_boxes"], image_dims)
        
        output = {
            "detection_boxes": np.array(nms_res[b]["detection_boxes"]) / np.tile(image_dims, 2),
            "mask": masks,
            "detection_scores": np.array(nms_res[b]["detection_scores"]),
            "detection_classes": np.array(nms_res[b]["detection_classes"]).astype(int)
        }
        outputs.append(output)
    return outputs

def decode_and_postprocess(raw_detections, config_data, arch_key):
    arch_cfg = config_data[arch_key]
    layers = arch_cfg["layers"]
    mask_channels = arch_cfg["mask_channels"]
    raw_detections_keys = list(raw_detections.keys())
    layer_from_shape = {raw_detections[key].shape: key for key in raw_detections_keys}

    def resolve_shape(layer):
        b, h, w, c_tag = layer
        if isinstance(c_tag, str):
            if c_tag == "mask_channels": c = mask_channels
            elif c_tag == "detection_output_channels": c = (arch_cfg['anchors']['regression_length'] + 1) * 4
            elif c_tag == "classes": c = arch_cfg["classes"]
            else: raise ValueError(f"Unsupported channel tag: {c_tag}")
        else: c = c_tag
        return (b, h, w, c)

    endnodes = [raw_detections[layer_from_shape[resolve_shape(layer)]] for layer in layers]
    return yolov8_seg_postprocess(endnodes, **arch_cfg)[0]

# --- THE MAIN ENTRY POINT ---
def inference_result_handler(original_frame, infer_results, labels, config_data, tracker=None, vio_data=None, target_yaw=None, target_dist=None, depth_frame=None, state_text="IDLE", get_mask=False, model_type="v8"):
    h, w = original_frame.shape[:2]
    master_mask = np.zeros((h, w), dtype=np.uint8)
    formatted_detections = []
    
    # 🚀 FAST DECODE
    decoded = decode_and_postprocess(infer_results, config_data, model_type)
    
    if isinstance(decoded, dict) and "detection_boxes" in decoded:
        boxes = decoded["detection_boxes"].copy()
        
        if len(boxes) > 0:
            boxes[:, [0, 2]] *= w
            boxes[:, [1, 3]] *= h
            
            # 🚀 VECTORIZED MASK DRAWING (Incredibly Fast)
            # Create a blank canvas for ALL masks to be drawn at once
            color_overlay = np.zeros((h, w, 3), dtype=np.uint8)
            alpha_mask = np.zeros((h, w), dtype=np.uint8)

            for idx in range(len(boxes)):
                score = decoded["detection_scores"][idx]
                if score < config_data["visualization_params"].get("score_thres", 0.45): 
                    continue
                
                class_id = int(decoded["detection_classes"][idx])
                xmin, ymin, xmax, ymax = map(int, boxes[idx])
                
                # Prevent out-of-bounds
                xmin, ymin = max(0, xmin), max(0, ymin)
                xmax, ymax = min(w, xmax), min(h, ymax)
                
                formatted_detections.append({
                    "detection_boxes": [xmin, ymin, xmax, ymax],
                    "detection_classes": class_id,
                    "detection_scores": score
                })
                
                # 🚀 HIGH-SPEED MASK PROCESSING
                if "mask" in decoded and len(decoded["mask"]) > idx:
                    mask_2d = decoded["mask"][idx]
                    mask_thresh = config_data["visualization_params"].get("mask_thresh", 0.5)
                    
                    # 1. Binarize (Fast)
                    binary_mask = (mask_2d > mask_thresh).astype(np.uint8)
                    if binary_mask.shape[:2] != (h, w):
                        binary_mask = cv2.resize(binary_mask, (w, h), interpolation=cv2.INTER_NEAREST)

                    # 2. Smooth Edges (Fixes the blocky 'Minecraft' look)
                    # A small Gaussian blur melts the jagged edges into smooth curves
                    binary_mask = cv2.GaussianBlur(binary_mask * 255, (5, 5), 0)
                    _, binary_mask = cv2.threshold(binary_mask, 127, 1, cv2.THRESH_BINARY)
                    
                    if get_mask: master_mask = cv2.bitwise_or(master_mask, binary_mask)
                    
                    # 3. Apply color to canvas
                    try: color = id_to_color(class_id).tolist()
                    except: color = [0, 100, 255]
                    
                    color_overlay[binary_mask == 1] = color
                    alpha_mask[binary_mask == 1] = 1

            # 🚀 ONE-SHOT ALPHA BLENDING (Fixes the CPU Lag)
            # Instead of blending every object one by one, we blend the entire screen once!
            if np.any(alpha_mask):
                roi = original_frame[alpha_mask == 1]
                original_frame[alpha_mask == 1] = cv2.addWeighted(roi, 0.4, color_overlay[alpha_mask == 1], 0.6, 0)

    # ... (Keep the rest: HUD drawing and return statement)
    output_dict = {"num_detections": len(formatted_detections)}
    if len(formatted_detections) > 0:
        output_dict["detection_boxes"] = [d["detection_boxes"] for d in formatted_detections]
        output_dict["detection_classes"] = [d["detection_classes"] for d in formatted_detections]
        output_dict["detection_scores"] = [d["detection_scores"] for d in formatted_detections]
    else:
        output_dict["detection_boxes"] = []
        output_dict["detection_classes"] = []
        output_dict["detection_scores"] = []

    output_frame = draw_detections(output_dict, original_frame, labels, 
                                   vio_data=vio_data, target_yaw=target_yaw, 
                                   target_dist=target_dist, depth_frame=depth_frame, 
                                   state_text=state_text)

    if get_mask: return output_frame, master_mask
    return output_frame
