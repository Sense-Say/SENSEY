import numpy as np

class StudentActionMonitor:
    def __init__(self):
        # Configuration Thresholds (in millimeters)
        self.DESK_HEIGHT_THRESHOLD = 850    # Nose below 85cm from floor = Head on Desk
        self.HAND_RAISE_THRESHOLD = 1400    # Wrist above 1.4m from floor = Raising Hand
        self.LEAN_FORWARD_THRESHOLD = 350   # Nose 35cm closer than shoulders = Aggressive Lean
        self.HUDDLE_THRESHOLD = 600         # Two students within 60cm = Talking/Cheating

    def get_classroom_actions(self, students_data):
        """
        Analyzes 3D spatial data for the entire classroom.
        Input: list of {id, box, keypoints: [[x, y, z, conf, ground_h], ...], name}
        """
        results = []
        
        for student in students_data:
            kp = student['keypoints'] # 17 joints
            
            # --- EXTRACT KEY JOINTS (with confidence checks) ---
            # Index: 0=Nose, 5=L_Shldr, 6=R_Shldr, 9=L_Wrist, 10=R_Wrist, 11=L_Hip, 12=R_Hip
            nose_h = kp[0][4]  # Ground Height
            nose_z = kp[0][2]  # Depth
            l_wrist_h = kp[9][4]
            r_wrist_h = kp[10][4]
            avg_shldr_z = (kp[5][2] + kp[6][2]) / 2 if (kp[5][3] > 0.3 and kp[6][3] > 0.3) else 0

            # --- BEHAVIORAL RULES ---
            
            # 1. Hand Raising (Priority 1)
            # Logic: Either wrist is higher than 1.4 meters from the floor
            raising_hand = l_wrist_h > self.HAND_RAISE_THRESHOLD or r_wrist_h > self.HAND_RAISE_THRESHOLD

            # 2. Peer Huddle / Talking (Priority 2)
            # Logic: Calculate 3D distance between this student's nose and every other student's nose
            peer_huddle = False
            if nose_z > 0:
                nose_pos = np.array([kp[0][0], kp[0][1], kp[0][2]]) # X, Y, Z
                for other in students_data:
                    if other['id'] == student['id']: continue
                    o_kp = other['keypoints']
                    if o_kp[0][2] > 0:
                        other_nose_pos = np.array([o_kp[0][0], o_kp[0][1], o_kp[0][2]])
                        # Euclidean Distance in 3D Space
                        dist = np.linalg.norm(nose_pos - other_nose_pos)
                        if 0 < dist < self.HUDDLE_THRESHOLD:
                            peer_huddle = True
                            break

            # 3. Head Down / Sleeping (Priority 3)
            # Logic: Nose is physically near the height of a standard desk (85cm or lower)
            head_down = (nose_h < self.DESK_HEIGHT_THRESHOLD and nose_h > 0)

            # 4. Aggressive Lean Forward (Priority 4)
            # Logic: The head is significantly closer to the teacher than the torso
            agg_lean = (avg_shldr_z - nose_z) > self.LEAN_FORWARD_THRESHOLD if (nose_z > 0 and avg_shldr_z > 0) else False

            # 5. Side Gaze / Looking Away (Priority 5)
            # Logic: Nose X-coordinate is outside the horizontal span of the shoulders
            side_gaze = (kp[0][0] < kp[5][0] or kp[0][0] > kp[6][0]) if all(kp[j][3] > 0.4 for j in [0,5,6]) else False

            # --- DECISION TREE (Prioritizing most important alerts) ---
            if raising_hand:
                action, color = "RAISING HAND", (0, 0, 255) # Red
            elif peer_huddle:
                action, color = "HUDDLE / TALKING", (255, 0, 255) # Purple
            elif head_down:
                action, color = "HEAD ON DESK", (0, 255, 255) # Yellow
            elif agg_lean:
                action, color = "LEANING FORWARD", (255, 165, 0) # Orange
            elif side_gaze:
                action, color = "LOOKING AWAY", (255, 255, 0) # Cyan
            else:
                action, color = "ATTENTIVE", (0, 255, 0) # Green

            student['action'] = action
            student['color'] = color
            results.append(student)
            
        return results