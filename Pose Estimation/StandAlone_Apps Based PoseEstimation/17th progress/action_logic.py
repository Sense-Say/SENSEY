import numpy as np
from collections import Counter

class StudentActionMonitor:
    def __init__(self):
        # --- Thresholds (Millimeters) ---
        self.HUDDLE_THRESHOLD  = 450   
        self.PRAYING_DEPTH_LIMIT = 120   # Max depth (Z) separation between wrists in mm (12cm)
        self.posture_history = {}        # Dedicated Posture Hysteresis Buffer

    def get_angle(self, p1, p2, p3):
        """Calculates the 2D angle (in degrees) of joint p1-p2-p3, where p2 is the vertex (Knee)."""
        p1_x, p1_y = float(p1[0]), float(p1[1])
        p2_x, p2_y = float(p2[0]), float(p2[1])
        p3_x, p3_y = float(p3[0]), float(p3[1])

        v1 = np.array([p1_x - p2_x, p1_y - p2_y])
        v2 = np.array([p3_x - p2_x, p3_y - p2_y])
        
        n1 = np.linalg.norm(v1)
        n2 = np.linalg.norm(v2)
        if n1 == 0 or n2 == 0:
            return 180.0 
        
        cos_theta = np.dot(v1, v2) / (n1 * n2)
        return np.degrees(np.arccos(np.clip(cos_theta, -1.0, 1.0)))

    def get_classroom_actions(self, students_data):
        current_frame_results = []
        
        for student in students_data:
            s_id = str(student['id'])
            kp = student['keypoints'] # [x, y, z, conf, ground_h]
            
            # --- 🚀 STEP 1: CALCULATE DYNAMIC BODY SCALE ---
            shl_w_raw = abs(float(kp[5][0]) - float(kp[6][0])) if (float(kp[5][3]) > 0.4 and float(kp[6][3]) > 0.4) else 0
            torso_h_raw = abs((float(kp[5][1]) + float(kp[6][1]))/2 - (float(kp[11][1]) + float(kp[12][1]))/2) if (float(kp[5][3]) > 0.4 and float(kp[6][3]) > 0.4 and float(kp[11][3]) > 0.4 and float(kp[12][3]) > 0.4) else 0
            
            if torso_h_raw > 50:
                body_scale = torso_h_raw
            elif shl_w_raw > 30:
                body_scale = shl_w_raw * 1.4
            else:
                eye_dist = abs(float(kp[1][0]) - float(kp[2][0])) if (float(kp[1][3]) > 0.4 and float(kp[2][3]) > 0.4) else 15
                body_scale = eye_dist * 4.0

            eye_y = (float(kp[1][1]) + float(kp[2][1])) / 2 if (float(kp[1][3]) > 0.4 and float(kp[2][3]) > 0.4) else float(kp[0][1])
            nose_x = float(kp[0][0])
            
            # --- 🚀 STEP 2: EXTRACT HORIZONTAL BODY PLANES ---
            shl_y = None
            shl_w = 0
            if float(kp[5][3]) > 0.4 and float(kp[6][3]) > 0.4:
                shl_y = (float(kp[5][1]) + float(kp[6][1])) / 2
                shl_w = abs(float(kp[5][0]) - float(kp[6][0]))
            elif float(kp[5][3]) > 0.4:
                shl_y = float(kp[5][1])
                shl_w = body_scale * 0.7 
            elif float(kp[6][3]) > 0.4:
                shl_y = float(kp[6][1])
                shl_w = body_scale * 0.7 
                
            hip_y = None
            if float(kp[11][3]) > 0.4 and float(kp[12][3]) > 0.4:
                hip_y = (float(kp[11][1]) + float(kp[12][1])) / 2
            elif float(kp[11][3]) > 0.4:
                hip_y = float(kp[11][1])
            elif float(kp[12][3]) > 0.4:
                hip_y = float(kp[12][1])

            knee_y = None
            if float(kp[13][3]) > 0.4 and float(kp[14][3]) > 0.4:
                knee_y = (float(kp[13][1]) + float(kp[14][1])) / 2
            elif float(kp[13][3]) > 0.4:
                knee_y = float(kp[13][1])
            elif float(kp[14][3]) > 0.4:
                knee_y = float(kp[14][1])

            ankle_y = None
            if float(kp[15][3]) > 0.4 and float(kp[16][3]) > 0.4:
                ankle_y = (float(kp[15][1]) + float(kp[16][1])) / 2
            elif float(kp[15][3]) > 0.4:
                ankle_y = float(kp[15][1])
            elif float(kp[16][3]) > 0.4:
                ankle_y = float(kp[16][1])

            # Calculate Vertical Distances safely
            torso_h = (hip_y - shl_y) if (hip_y is not None and shl_y is not None) else None
            thigh_h = (knee_y - hip_y) if (knee_y is not None and hip_y is not None) else None
            shin_h = (ankle_y - knee_y) if (ankle_y is not None and knee_y is not None) else None
            leg_h = (ankle_y - hip_y) if (ankle_y is not None and hip_y is not None) else None

            # --- 🚀 RULE 1: RAISING HAND ---
            is_raising = False
            if float(kp[9][3]) > 0.4: 
                shl_ref = float(kp[5][1]) if float(kp[5][3]) > 0.4 else eye_y
                if float(kp[9][1]) < shl_ref - (0.2 * body_scale) and float(kp[9][1]) < eye_y:
                    is_raising = True
            if float(kp[10][3]) > 0.4: 
                shl_ref = float(kp[6][1]) if float(kp[6][3]) > 0.4 else eye_y
                if float(kp[10][1]) < shl_ref - (0.2 * body_scale) and float(kp[10][1]) < eye_y:
                    is_raising = True
            
            # --- 🚀 RULE 2: STANDING POSTURE ENGINE ---
            
            # A. Explicit Sitting Overrides (Foreshortening Proof)
            is_definitely_sitting = False
            
            # 1. Thigh Foreshortening (Facing camera): Thigh Y is much shorter than Shin Y.
            if thigh_h is not None and shin_h is not None and shin_h > 10:
                if (thigh_h / shin_h) < 0.85:
                    is_definitely_sitting = True
            
            # 2. Thigh-to-Torso Foreshortening (Feet hidden): Thigh Y is tiny compared to Torso Y.
            if thigh_h is not None and torso_h is not None and torso_h > 10:
                if (thigh_h / torso_h) < 0.45:
                    is_definitely_sitting = True

            # 3. Bent Knee Angles (Sideways/Profile sitting)
            left_angle = self.get_angle(kp[11], kp[13], kp[15]) if (float(kp[11][3])>0.4 and float(kp[13][3])>0.4 and float(kp[15][3])>0.4) else 180.0
            right_angle = self.get_angle(kp[12], kp[14], kp[16]) if (float(kp[12][3])>0.4 and float(kp[14][3])>0.4 and float(kp[16][3])>0.4) else 180.0
            if (left_angle < 135.0 and left_angle > 0) or (right_angle < 135.0 and right_angle > 0):
                is_definitely_sitting = True

            # B. Evaluate Standing (Only if not explicitly sitting)
            is_standing = False
            
            if not is_definitely_sitting:
                
                # Core Aspect Ratio Check
                core_indices = [0, 1, 2, 3, 4, 5, 6, 11, 12, 13, 14, 15, 16]
                core_kps = [kp[j] for j in core_indices if float(kp[j][3]) > 0.4]
                
                core_ratio = 0
                if len(core_kps) >= 3:
                    min_x = min(float(p[0]) for p in core_kps)
                    max_x = max(float(p[0]) for p in core_kps)
                    min_y = min(float(p[1]) for p in core_kps)
                    max_y = max(float(p[1]) for p in core_kps)
                    
                    core_h = max_y - min_y
                    core_w = max_x - min_x if (max_x - min_x) > 0 else 1
                    core_ratio = core_h / core_w

                if core_ratio > 2.5:
                    is_standing = True
                else:
                    if leg_h is not None and torso_h is not None and torso_h > 10:
                        # TIER 1: Full Legs Visible
                        if (leg_h / torso_h) > 1.15:
                            is_standing = True
                    
                    elif thigh_h is not None and torso_h is not None and torso_h > 10:
                        # TIER 2: Half Legs Visible
                        if (thigh_h / torso_h) > 0.65:
                            is_standing = True
                    
                    else:
                        # TIER 3: Legs Occluded
                        if torso_h is not None and shl_w > 10:
                            if (torso_h / shl_w) > 1.45:
                                is_standing = True
                        if shl_y is not None:
                            if shl_y < 350:
                                is_standing = True

            # 🚀 C. SUPREME HORIZON VETO (Anti-Hallucination & Camera Calibrator)
            # If a student is relatively close to the 1.2m camera (shoulder width > 160px), 
            # their shoulders MUST be in the top half of the screen if they are standing.
            # If their shoulders are below Y=450, they are physically sitting down, 
            # and we instantly override any hallucinated hips at the bottom of the screen.
            if shl_w > 160 and shl_y is not None:
                if shl_y > 450:
                    is_standing = False

            # --- 🚀 RULE 3: PRAYING ---
            is_praying = False
            if float(kp[9][3]) > 0.4 and float(kp[10][3]) > 0.4:
                pixel_dist = abs(float(kp[9][0]) - float(kp[10][0]))
                normalized_wrist_dist = pixel_dist / body_scale
                
                z_l = float(kp[9][2])
                z_r = float(kp[10][2])
                depth_diff = abs(z_l - z_r) if (z_l > 0 and z_r > 0) else 0
                
                mid_wrist_x = (float(kp[9][0]) + float(kp[10][0])) / 2
                midline_alignment = abs(mid_wrist_x - nose_x) / body_scale
                
                is_wrists_crossed = False
                if float(kp[5][3]) > 0.4 and float(kp[6][3]) > 0.4:
                    facing_forward = float(kp[5][0]) > float(kp[6][0])
                    if facing_forward and (float(kp[9][0]) < float(kp[10][0])):
                        is_wrists_crossed = True
                    elif not facing_forward and (float(kp[9][0]) > float(kp[10][0])):
                        is_wrists_crossed = True

                is_chest_crossed = False
                if float(kp[5][3]) > 0.4 and float(kp[6][3]) > 0.4:
                    dist_l_wrist_r_shl = np.linalg.norm(np.array([float(kp[9][0]), float(kp[9][1])]) - np.array([float(kp[6][0]), float(kp[6][1])])) / body_scale
                    dist_r_wrist_l_shl = np.linalg.norm(np.array([float(kp[10][0]), float(kp[10][1])]) - np.array([float(kp[5][0]), float(kp[5][1])])) / body_scale
                    if dist_l_wrist_r_shl < 0.24 and dist_r_wrist_l_shl < 0.24:
                        is_chest_crossed = True

                if not is_wrists_crossed and not is_chest_crossed and depth_diff < self.PRAYING_DEPTH_LIMIT:
                    
                    chest_y_level = shl_y + (0.42 * torso_h) if (shl_y is not None and torso_h is not None) else (eye_y + (0.45 * body_scale))

                    # TRIGGER A: Loose Traditional Clasp 
                    if normalized_wrist_dist < 0.28 and midline_alignment < 0.22:
                        if float(kp[9][1]) < chest_y_level and float(kp[10][1]) < chest_y_level:
                            is_praying = True
                            
                    # TRIGGER B: Bowed Head + Desk Folded Hands
                    shl_y_ref = shl_y if shl_y is not None else eye_y
                    nose_to_shl_y = shl_y_ref - float(kp[0][1])
                    head_is_bowed = nose_to_shl_y < (0.15 * body_scale) 
                    
                    if head_is_bowed and normalized_wrist_dist < 0.28:
                        is_praying = True
                        
                    # TRIGGER C: Hands Covering Eyes/Face
                    hands_on_face = (abs(float(kp[9][1]) - float(kp[0][1])) < 0.18 * body_scale) and (abs(float(kp[10][1]) - float(kp[0][1])) < 0.18 * body_scale)
                    if hands_on_face and normalized_wrist_dist < 0.32:
                        is_praying = True

            # --- 🚀 RULE 4: LOOKING AWAY ---
            is_back_turned = False
            is_head_twisted = False
            
            if float(kp[0][3]) < 0.25 and float(kp[1][3]) < 0.25 and float(kp[2][3]) < 0.25:
                if float(kp[5][3]) > 0.4 or float(kp[6][3]) > 0.4:
                    is_back_turned = True
            
            elif float(kp[5][3]) > 0.4 and float(kp[6][3]) > 0.4 and float(kp[0][3]) > 0.4:
                shl_mid_x = (float(kp[5][0]) + float(kp[6][0])) / 2
                shl_w_val = abs(float(kp[5][0]) - float(kp[6][0]))
                
                if shl_w_val > 20:
                    is_facing_camera = False
                    if float(kp[1][3]) > 0.4 and float(kp[2][3]) > 0.4:
                        l_eye_to_nose = abs(float(kp[1][0]) - float(kp[0][0]))
                        r_eye_to_nose = abs(float(kp[2][0]) - float(kp[0][0]))
                        eye_dist = abs(float(kp[1][0]) - float(kp[2][0]))
                        asymmetry = abs(l_eye_to_nose - r_eye_to_nose) / eye_dist if eye_dist > 0 else 1.0
                        if asymmetry < 0.28:
                            is_facing_camera = True
                    
                    if not is_facing_camera:
                        twist_ratio = abs(float(kp[0][0]) - shl_mid_x) / shl_w_val
                        if twist_ratio > 0.36:
                            is_head_twisted = True

            # --- 🚀 STEP 3: POSTURAL HYSTERESIS ---
            raw_posture = "STANDING" if is_standing else "SITTING"
            
            if s_id not in self.posture_history:
                self.posture_history[s_id] = []
            self.posture_history[s_id].append(raw_posture)
            if len(self.posture_history[s_id]) > 10:
                self.posture_history[s_id].pop(0)
                
            posture_counts = Counter(self.posture_history[s_id])
            posture = posture_counts.most_common(1)[0][0]

            # --- 🚀 ACTIONS (INSTANT EVALUATIONS) ---
            if is_raising:          action = "RAISING HAND"
            elif is_praying:        action = "PRAYING"
            elif is_back_turned:    action = "LOOKING AWAY"
            elif is_head_twisted:   action = "LOOKING AWAY"
            else:                   action = "ATTENTIVE"

            color_map = {
                "RAISING HAND": (0, 0, 180),  
                "STANDING": (0, 100, 200),    
                "PRAYING": (200, 200, 200),    
                "LOOKING AWAY": (150, 150, 0), 
                "ATTENTIVE": (0, 120, 0)       
            }
            
            student['posture'] = posture
            student['action'] = action
            
            if action == "ATTENTIVE":
                color_key = "STANDING" if posture == "STANDING" else "ATTENTIVE"
            else:
                color_key = action

            student['color'] = color_map.get(color_key, (0, 120, 0))
            current_frame_results.append(student)
            
        return current_frame_results