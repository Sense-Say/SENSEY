import math
import time

class StudentActionMonitor:
    def __init__(self):
        # Stores history: {track_id: {'center': (x, y), 'time': timestamp}}
        self.history = {}
        
        # --- TUNING PARAMETERS ---
        self.WALKING_THRESHOLD = 0.005   # How much they must move to be "Walking"
        self.CONFIDENCE_THRESHOLD = 0.3  # Only trust points with >30% confidence
        
        # COCO Keypoint Map for reference
        self.KP = {
            'nose': 0, 'l_eye': 1, 'r_eye': 2, 'l_ear': 3, 'r_ear': 4,
            'l_shoulder': 5, 'r_shoulder': 6, 'l_elbow': 7, 'r_elbow': 8,
            'l_wrist': 9, 'r_wrist': 10, 'l_hip': 11, 'r_hip': 12,
            'l_knee': 13, 'r_knee': 14, 'l_ankle': 15, 'r_ankle': 16
        }

    def get_action(self, keypoints, track_id, center_point):
        """
        Returns: (Action String, Color Tuple)
        """
        current_time = time.time()
        
        # Helper to get point: returns (x, y, conf)
        def get_p(name):
            idx = self.KP[name]
            if idx < len(keypoints):
                return keypoints[idx]
            return (0, 0, 0)

        # ----------------------------------------------------------------
        # 1. DETECT HAND RAISING
        # ----------------------------------------------------------------
        # Logic: Wrist is vertically ABOVE the Ear (Y value is smaller)
        l_wrist = get_p('l_wrist')
        r_wrist = get_p('r_wrist')
        l_ear = get_p('l_ear')
        r_ear = get_p('r_ear')
        
        is_raising_hand = False

        # Check Left Arm
        if l_wrist[2] > self.CONFIDENCE_THRESHOLD and l_ear[2] > self.CONFIDENCE_THRESHOLD:
            # Remember: Y=0 is top of screen. So "Above" means wrist_y < ear_y
            if l_wrist[1] < l_ear[1]: 
                is_raising_hand = True
        
        # Check Right Arm
        if r_wrist[2] > self.CONFIDENCE_THRESHOLD and r_ear[2] > self.CONFIDENCE_THRESHOLD:
            if r_wrist[1] < r_ear[1]:
                is_raising_hand = True

        if is_raising_hand:
            return "Raising Hand", (0, 0, 255) # Red

        # ----------------------------------------------------------------
        # 2. DETECT WALKING
        # ----------------------------------------------------------------
        # Logic: Compare current center position with position 0.2 seconds ago
        is_walking = False
        
        if track_id in self.history:
            prev_data = self.history[track_id]
            prev_center = prev_data['center']
            prev_time = prev_data['time']
            
            # Calculate distance moved (Euclidean distance)
            dx = center_point[0] - prev_center[0]
            dy = center_point[1] - prev_center[1]
            distance = math.sqrt(dx*dx + dy*dy)
            
            # Check if enough time has passed to calculate speed
            time_diff = current_time - prev_time
            if time_diff > 0.2: # Update status every 200ms
                if distance > self.WALKING_THRESHOLD:
                    is_walking = True
                
                # Update history
                self.history[track_id] = {'center': center_point, 'time': current_time}
            else:
                # If less than 0.2s, keep previous state if it was walking
                # This prevents flickering
                pass 
        else:
            # First time seeing this ID
            self.history[track_id] = {'center': center_point, 'time': current_time}

        if is_walking:
            return "Walking", (255, 0, 0) # Blue

        # ----------------------------------------------------------------
        # 3. DETECT STANDING
        # ----------------------------------------------------------------
        # Default state
        return "Standing", (0, 255, 0) # Green