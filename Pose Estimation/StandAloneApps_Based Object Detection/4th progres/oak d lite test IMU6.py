#!/usr/bin/env python3
import depthai as dai
import time
import sys

# 1. Setup the Pipeline (DepthAI 3.0 style)
with dai.Pipeline() as pipeline:
    # 2. Define the IMU node
    imu = pipeline.create(dai.node.IMU)

    # 3. Enable sensors (BMI270)
    imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 400)
    imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 400)

    # 4. Configure Batching
    imu.setBatchReportThreshold(1)
    imu.setMaxBatchReports(10)

    # 5. Create Output Queue directly from the node (New in v3.x)
    # We use maxSize=20 to prevent memory buildup on the RPi 5
    imuQueue = imu.out.createOutputQueue(maxSize=20, blocking=False)

    # 6. Start the Pipeline
    # This automatically connects to the OAK-D Lite
    pipeline.start()
    
    print("DepthAI 3.3.0 Dashboard Active...")
    print("Testing OAK-D Lite BMI270. Press Ctrl+C to stop.\n")
    
    last_print = time.time()

    try:
        while pipeline.isRunning():
            # Get data
            imuData = imuQueue.get()
            
            # DepthAI 3.0 uses the same packet structure as Gen2
            for imuPacket in imuData.packets:
                accel = imuPacket.acceleroMeter
                gyro = imuPacket.gyroscope

                # Throttle terminal output to 20 updates per second
                if time.time() - last_print > 0.05:
                    # \r keeps the dashboard on a single line
                    output = (
                        f"\r[ACCEL m/s^2] X: {accel.x:>6.2f} Y: {accel.y:>6.2f} Z: {accel.z:>6.2f}  |  "
                        f"[GYRO rad/s] X: {gyro.x:>6.2f} Y: {gyro.y:>6.2f} Z: {gyro.z:>6.2f}"
                    )
                    sys.stdout.write(output)
                    sys.stdout.flush()
                    last_print = time.time()
                    
    except KeyboardInterrupt:
        print("\nStopping...")
        
# The 'with' block automatically closes the pipeline and releases the OAK-D
print("Pipeline Closed.")