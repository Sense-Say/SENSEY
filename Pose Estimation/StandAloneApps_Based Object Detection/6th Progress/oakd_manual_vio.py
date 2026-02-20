import depthai as dai
import numpy as np
import time
import math
import cv2
import os

# Ensure Display works on Pi 5
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"

# --- CONFIGURATION ---
MIN_Z_DELTA = 0.01  # 1 cm
MAX_Z_DELTA = 0.30  # 30 cm per frame

def create_vio_pipeline():
    pipeline = dai.Pipeline()

    # 1. IMU SETUP
    imu = pipeline.create(dai.node.IMU)
    imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 100)
    imu.setBatchReportThreshold(1)
    imu.setMaxBatchReports(10)
    
    imuOut = pipeline.create(dai.node.XLinkOut)
    imuOut.setStreamName("imu")
    imu.out.link(imuOut.input)

    # 2. STEREO CAMERAS
    monoLeft = pipeline.create(dai.node.MonoCamera)
    monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    monoLeft.setBoardSocket(dai.CameraBoardSocket.CAM_B)

    monoRight = pipeline.create(dai.node.MonoCamera)
    monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    monoRight.setBoardSocket(dai.CameraBoardSocket.CAM_C)

    stereo = pipeline.create(dai.node.StereoDepth)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    # Align depth to Left camera so the feature coordinates match perfectly
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_B)
    
    monoLeft.out.link(stereo.left)
    monoRight.out.link(stereo.right)

    depthOut = pipeline.create(dai.node.XLinkOut)
    depthOut.setStreamName("depth")
    stereo.depth.link(depthOut.input)

    # 3. FEATURE TRACKER
    featTracker = pipeline.create(dai.node.FeatureTracker)
    monoLeft.out.link(featTracker.inputImage)
    
    # FIX: Pull video directly from monoLeft instead of passthrough
    vidOut = pipeline.create(dai.node.XLinkOut)
    vidOut.setStreamName("video")
    monoLeft.out.link(vidOut.input)

    featOut = pipeline.create(dai.node.XLinkOut)
    featOut.setStreamName("features")
    featTracker.outputFeatures.link(featOut.input)

    return pipeline

def run_vio():
    print("🚀 Starting Manual VIO (Pedometer) Engine...")

    total_distance_meters = 0.0
    current_yaw_degrees = 0.0
    last_imu_time = None
    feature_history = {}

    with dai.Device(create_vio_pipeline()) as device:
        # IMU can be non-blocking
        q_imu = device.getOutputQueue(name="imu", maxSize=10, blocking=False)
        
        # Visual data MUST be blocking to ensure we get frames
        q_feat = device.getOutputQueue(name="features", maxSize=4, blocking=True)
        q_depth = device.getOutputQueue(name="depth", maxSize=4, blocking=True)
        q_vid = device.getOutputQueue(name="video", maxSize=4, blocking=True)

        print("✅ Sensors Active. Walk forward or turn the camera!")

        while True:
            # --- 1. PROCESS IMU (YAW / HEADING) ---
            # Use tryGet for IMU so it doesn't slow down the video feed
            imuData = q_imu.tryGet()
            if imuData is not None:
                imuPackets = imuData.packets
                for packet in imuPackets:
                    gyro = packet.gyroscope
                    
                    current_time_sec = time.time()
                    
                    if last_imu_time is None:
                        last_imu_time = current_time_sec
                        continue
                    
                    dt = current_time_sec - last_imu_time
                    last_imu_time = current_time_sec
                    
                    yaw_change = gyro.z * (180.0 / math.pi) * dt
                    current_yaw_degrees += yaw_change

            # --- 2. PROCESS FEATURES & DEPTH (DISTANCE) ---
            # Use get() to wait for the frames to arrive
            try:
                featData = q_feat.get()
                depthData = q_depth.get()
                vidData = q_vid.get()
            except RuntimeError:
                continue # Skip if queue fails

            depth_frame = depthData.getFrame()
            # vidData from monoLeft is a 2D array
            raw_frame = vidData.getCvFrame() 
            # Convert Grayscale to BGR so we can draw yellow/green UI elements
            display_frame = cv2.cvtColor(raw_frame, cv2.COLOR_GRAY2BGR)

            tracked_features = featData.trackedFeatures
            frame_distance_deltas = []

            for feature in tracked_features:
                x, y = int(feature.position.x), int(feature.position.y)
                cv2.circle(display_frame, (x, y), 2, (0, 255, 255), -1)

                if 0 <= y < depth_frame.shape[0] and 0 <= x < depth_frame.shape[1]:
                    z_mm = depth_frame[y, x]
                    if z_mm == 0: continue 
                    
                    z_meters = z_mm / 1000.0

                    if feature.id in feature_history:
                        prev_z = feature_history[feature.id]
                        delta_z = prev_z - z_meters
                        
                        # Check if the movement is realistic
                        if MIN_Z_DELTA < abs(delta_z) < MAX_Z_DELTA:
                            # If delta_z is positive, object got closer (we moved forward)
                            frame_distance_deltas.append(delta_z)
                            cv2.line(display_frame, (x, y), (x, y+10), (0, 255, 0), 2)

                    feature_history[feature.id] = z_meters

            # Clean up old features
            current_ids = {f.id for f in tracked_features}
            feature_history = {k: v for k, v in feature_history.items() if k in current_ids}

            # --- 3. ACCUMULATE DISTANCE ---
            if len(frame_distance_deltas) > 0:
                avg_step = sum(frame_distance_deltas) / len(frame_distance_deltas)
                total_distance_meters += avg_step

            # --- 4. DISPLAY RESULTS ---
            display_yaw = current_yaw_degrees % 360
            
            cv2.putText(display_frame, f"Dist: {total_distance_meters:.2f}m", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display_frame, f"Yaw: {display_yaw:.0f} deg", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            cv2.imshow("Manual VIO (OAK-D)", display_frame)

            if cv2.waitKey(1) == ord('q'): break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_vio()