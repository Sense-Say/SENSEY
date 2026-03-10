import numpy as np
from collections import Counter

class StudentActionMonitor:
    def __init__(self):
        # --- PHYSICAL THRESHOLDS (Millimeters) ---
        self.GROUND_HAND_RAISE = 1380  
        self.GROUND_STANDING   = 1250  
        self.GROUND_DESK_LEVEL = 850   
        self.HUDDLE_THRESHOLD  = 450   
        self.PRAYING_THRESHOLD = 150   # Hands touching
        self.ANTHEM_PROXIMITY  = 160   # Hand near chest center
        self.ANTHEM_HAND_GAP   = 250   # 🚀 Separation required to NOT be 'Praying'
        
        # --- OATH MARGINS ---
        self.OATH_V_MARGIN = 1.0 # tan(45)
        self.OATH_H_MARGIN = 0.58 # tan(30)
        
        self.history = {} 
        self.buffer_size = 20
        self.min_evidence = 14 

    def get_classroom_actions(self, students_data):
        current_frame_results = []
        
        for student in students_data:
            s_id = str(student['id'])
            kp = student['keypoints'] # [x, y, z, conf, ground_h]
            
            # --- 1. RAISING HAND ---
            is_raising = kp[9][4] > self.GROUND_HAND_RAISE or kp[10][4] > self.GROUND_HAND_RAISE
            
            # --- 2. STANDING ---
            is_standing = (kp[5][4] + kp[6][4]) / 2 > self.GROUND_STANDING

            # --- 3. PATRIOTIC OATH ---
            is_oath = False
            if kp[8][3] > 0.4 and kp[10][3] > 0.4:
                dx_shl_elb = abs(kp[8][0] - kp[6][0])
                dy_shl_elb = abs(kp[8][1] - kp[6][1])
                elbow_valid = dy_shl_elb <= (dx_shl_elb * self.OATH_V_MARGIN) or dy_shl_elb < 50
                dy_elb_wri = abs(kp[10][1] - kp[8][1])
                dx_elb_wri = abs(kp[10][0] - kp[8][0])
                wrist_valid = dx_elb_wri <= (dy_elb_wri * self.OATH_H_MARGIN)
                if elbow_valid and wrist_valid and kp[10][1] < kp[8][1]:
                    is_oath = True

            # --- 🚀 4. PRAYING (Check before Anthem) ---
            is_praying = False
            dist_wrists = 9999
            if kp[9][3] > 0.4 and kp[10][3] > 0.4:
                w_l = np.array([kp[9][0], kp[9][1], kp[9][2]])
                w_r = np.array([kp[10][0], kp[10][1], kp[10][2]])
                dist_wrists = np.linalg.norm(w_l - w_r)
                if dist_wrists < self.PRAYING_THRESHOLD:
                    is_praying = True

            # --- 🚀 5. NATIONAL ANTHEM (With Praying Exclusion) ---
            is_anthem = False
            if not is_praying and all(kp[j][3] > 0.4 for j in [5, 6, 9, 10]):
                pts = [np.array([kp[5][0],kp[5][1],kp[5][2]]), np.array([kp[6][0],kp[6][1],kp[6][2]]),
                       np.array([kp[9][0],kp[9][1],kp[9][2]]), np.array([kp[10][0],kp[10][1],kp[10][2]])]
                geom_center = np.mean(pts, axis=0)
                r_wrist = np.array([kp[10][0], kp[10][1], kp[10][2]])
                
                # Condition: Right wrist near center AND Left wrist is NOT near the right wrist
                if np.linalg.norm(r_wrist - geom_center) < self.ANTHEM_PROXIMITY:
                    if dist_wrists > self.ANTHEM_HAND_GAP:
                        is_anthem = True

            # --- 6. HEAD ON DESK ---
            is_head_down = kp[0][4] < self.GROUND_DESK_LEVEL and kp[0][2] > 0

            # --- 7. LOOKING AWAY ---
            is_looking_away = False
            if kp[5][3] > 0.4 and kp[6][3] > 0.4:
                l_b, r_b = min(kp[5][0], kp[6][0]), max(kp[5][0], kp[6][0])
                if kp[0][0] < l_b or kp[0][0] > r_b: is_looking_away = True

            # --- PRIORITY TREE ---
            if is_raising:        raw_act = "RAISING HAND"
            elif is_standing:     raw_act = "OUT OF SEAT"
            elif is_oath:         raw_act = "PATRIOTIC OATH"
            elif is_anthem:       raw_act = "NATIONAL ANTHEM"
            elif is_praying:      raw_act = "PRAYING"
            elif is_head_down:    raw_act = "HEAD ON DESK"
            elif is_looking_away: raw_act = "LOOKING AWAY"
            else:                 raw_act = "ATTENTIVE"

            if s_id not in self.history: self.history[s_id] = []
            self.history[s_id].append(raw_act)
            if len(self.history[s_id]) > self.buffer_size: self.history[s_id].pop(0)
            
            if len(self.history[s_id]) < 5: final_action = raw_act
            else:
                counts = Counter(self.history[s_id])
                most_common, freq = counts.most_common(1)[0]
                final_action = most_common if freq >= self.min_evidence else "ATTENTIVE"

            color_map = {
                "RAISING HAND": (0, 0, 180), "OUT OF SEAT": (0, 100, 200),
                "PATRIOTIC OATH": (180, 0, 180), "NATIONAL ANTHEM": (200, 100, 0), 
                "PRAYING": (130, 125, 0), "HEAD ON DESK": (0, 180, 180),
                "LOOKING AWAY": (150, 150, 0), "ATTENTIVE": (0, 120, 0)
            }
            
            student['action'] = final_action
            student['color'] = color_map.get(final_action, (0, 120, 0))
            current_frame_results.append(student)
            
        return current_frame_results