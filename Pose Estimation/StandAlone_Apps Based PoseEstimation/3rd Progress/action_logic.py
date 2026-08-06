import math

class StudentActionMonitor:
    def __init__(self):
        self.CONFIDENCE_THRESHOLD = 0.4 
        
        # COCO Keypoint Mapping
        self.KP = {
            'nose': 0, 'l_eye': 1, 'r_eye': 2, 'l_ear': 3, 'r_ear': 4,
            'l_shoulder': 5, 'r_shoulder': 6, 'l_elbow': 7, 'r_elbow': 8,
            'l_wrist': 9, 'r_wrist': 10, 'l_hip': 11, 'r_hip': 12,
            'l_knee': 13, 'r_knee': 14, 'l_ankle': 15, 'r_ankle': 16
        }

    def get_action(self, keypoints, track_id, center_point):
        """
        Processes 2D Keypoints with Perspective Compensation.
        """
        
        def get_p(name):
            idx = self.KP[name]
            if idx < len(keypoints):
                return keypoints[idx] # [x, y, confidence]
            return [0, 0, 0]

        # Get Keypoints
        nose = get_p('nose')
        l_eye, r_eye = get_p('l_eye'), get_p('r_eye')
        l_sh, r_sh = get_p('l_shoulder'), get_p('r_shoulder')
        l_el, r_el = get_p('l_elbow'), get_p('r_elbow')
        l_wr, r_wr = get_p('l_wrist'), get_p('r_wrist')
        l_hip, r_hip = get_p('l_hip'), get_p('r_hip')

        # --- DYNAMIC RULER (Scale Compensation) ---
        # Distance between nose and shoulder line used as a reference for "Head Size"
        sh_y_avg = (l_sh[1] + r_sh[1]) / 2 if (l_sh[2] > 0.1 and r_sh[2] > 0.1) else nose[1] + 0.1
        head_ref = abs(sh_y_avg - nose[1])
        if head_ref < 0.01: head_ref = 0.05

        # --- BEHAVIOR LOGIC ---

        # 1. CHECK FOR WRISTS POSITION (Higher than eyes)
        l_wrist_up = l_wr[2] > self.CONFIDENCE_THRESHOLD and l_wr[1] < l_eye[1]
        r_wrist_up = r_wr[2] > self.CONFIDENCE_THRESHOLD and r_wr[1] < r_eye[1]

        # NEW RULE: HEADACHE (Both wrists up near eyes/head)
        if l_wrist_up and r_wrist_up:
            return "Extreme Boredom", (0, 125, 125) # Yellow

        # RULE 1: RAISING HAND (Only one wrist up)
        if l_wrist_up or r_wrist_up:
            return "Raising Hand", (0, 0, 255) # Red

        # RULE 5: HEAD DOWN (Nose drops below shoulder line or distance shrinks)
        if nose[2] > self.CONFIDENCE_THRESHOLD and l_sh[2] > self.CONFIDENCE_THRESHOLD:
            # If nose is physically below shoulders OR very close to them
            if nose[1] > sh_y_avg or abs(nose[1] - sh_y_avg) < (head_ref * 0.2):
                return "Head Down/Phone", (100, 100, 100) # Gray

        # RULE 2: SIDE LOOK / CHEATING (Horizontal nose offset)
        sh_width = abs(l_sh[0] - r_sh[0]) if (l_sh[2] > 0.1 and r_sh[2] > 0.1) else 0.1
        if nose[2] > self.CONFIDENCE_THRESHOLD and sh_width > 0.05:
            sh_center_x = (l_sh[0] + r_sh[0]) / 2
            if abs(nose[0] - sh_center_x) > (sh_width * 0.4):
                return "Side Look", (0, 165, 255) # Orange

        # RULE 4: TORSO TWIST (Shoulder height difference)
        if l_sh[2] > self.CONFIDENCE_THRESHOLD and r_sh[2] > self.CONFIDENCE_THRESHOLD:
            if abs(l_sh[1] - r_sh[1]) > (sh_width * 0.3):
                return "Torso Twist", (255, 0, 255) # Purple

        # DEFAULT: ATTENTIVE
        return "Attentive", (0, 255, 0) # Green