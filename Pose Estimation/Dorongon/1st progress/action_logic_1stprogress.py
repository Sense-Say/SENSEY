import math
import time

class StudentActionMonitor:
    def __init__(self):
        # Stores history of positions for calculating speed: {track_id: (x, y, time)}
        self.history = {}
        # Thresholds
        self.WALKING_THRESHOLD = 0.002  # Movement speed threshold
        self.CONFIDENCE_THRESHOLD = 0.3

    def get_action(self, keypoints, track_id, center_point):
        """
        Determines if the person is Raising Hand, Standing, or Walking.
        keypoints: List of [x, y, confidence] (17 COCO points)
        track_id: ID of the person
        center_point: (x, y) normalized coordinates of the person's center
        """
        action = "Standing" # Default state

        # COCO Keypoint mapping
        # 0: Nose, 1: LEye, 2: REye, 3: LEar, 4: REar
        # 5: LShoulder, 6: RShoulder, 7: LElbow, 8: RElbow
        # 9: LWrist, 10: RWrist, 11: LHip, 12: RHip
        # 13: LKnee, 14: RKnee, 15: LAnkle, 16: RAnkle
        
        # Helper to get point safely
        def get_p(idx):
            if idx < len(keypoints):
                return keypoints[idx]
            return [0, 0, 0]

        # ---------------------------------------------------------
        # 1. CHECK HAND RAISING (Priority 1)
        # ---------------------------------------------------------
        l_wrist = get_p(9)
        r_wrist = get_p(10)
        l_ear = get_p(3)
        r_ear = get_p(4)
        nose = get_p(0)

        # Note: In images, Y=0 is the top. So "Above" means y_wrist < y_ear
        raising_hand = False
        
        # Check Left Arm
        if l_wrist[2] > self.CONFIDENCE_THRESHOLD and l_ear[2] > self.CONFIDENCE_THRESHOLD:
            if l_wrist[1] < l_ear[1]: # Wrist is higher than ear
                raising_hand = True
        
        # Check Right Arm
        if r_wrist[2] > self.CONFIDENCE_THRESHOLD and r_ear[2] > self.CONFIDENCE_THRESHOLD:
            if r_wrist[1] < r_ear[1]: # Wrist is higher than ear
                raising_hand = True

        if raising_hand:
            return "Raising Hand"

        # ---------------------------------------------------------
        # 2. CHECK WALKING (Priority 2)
        # ---------------------------------------------------------
        is_moving = False
        current_time = time.time()
        
        if track_id in self.history:
            prev_x, prev_y, prev_time = self.history[track_id]
            
            # Calculate distance moved
            dist = math.sqrt((center_point[0] - prev_x)**2 + (center_point[1] - prev_y)**2)
            
            # If moved significantly
            if dist > self.WALKING_THRESHOLD:
                is_moving = True
        
        # Update history
        self.history[track_id] = (center_point[0], center_point[1], current_time)

        if is_moving:
            return "Walking"

        # ---------------------------------------------------------
        # 3. CHECK STANDING (Default)
        # ---------------------------------------------------------
        # If not raising hand and not moving much, we assume standing.
        # (You could add checks here to distinguish Sitting vs Standing 
        # by checking if knees are vertically below hips)
        
        return "Standing"