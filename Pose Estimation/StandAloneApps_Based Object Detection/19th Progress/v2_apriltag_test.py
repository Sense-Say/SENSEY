import cv2
import depthai as dai
import os

# Suppress the QT Wayland warning, force XCB for Pi 5 compatibility 
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["DISPLAY"] = ":0"

def get_apriltag_pipeline():
    pipeline = dai.Pipeline()

    # 1. Left Mono Camera - Specifically capped for OAK-D Lite (OV7251)
    mono = pipeline.create(dai.node.MonoCamera)
    mono.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    mono.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
    
    # 2. AprilTag Node (Native on the VPU)
    april = pipeline.create(dai.node.AprilTag)
    april.initialConfig.setFamily(dai.AprilTagConfig.Family.TAG_36H11)
    
    # 3. Outputs
    xout_april = pipeline.create(dai.node.XLinkOut)
    xout_april.setStreamName("april")
    xout_frame = pipeline.create(dai.node.XLinkOut)
    xout_frame.setStreamName("video")

    # 4. Data Routing
    mono.out.link(april.inputImage)
    mono.out.link(xout_frame.input)
    april.out.link(xout_april.input)

    return pipeline

def main():
    print("⏳ Starting DepthAI v2 AprilTag Test...")
    with dai.Device(get_apriltag_pipeline()) as device:
        
        # Access hardware queues
        q_video = device.getOutputQueue(name="video", maxSize=4, blocking=False)
        q_april = device.getOutputQueue(name="april", maxSize=4, blocking=False)

        print("✅ System Live! Point camera at an AprilTag (Family: 36h11). Press 'Q' to quit.")

        while True:
            # 1. Pull the camera feed 
            frame_data = q_video.tryGet()
            frame = frame_data.getCvFrame() if frame_data is not None else None

            # 2. Pull AprilTag metadata packet
            april_data = q_april.tryGet()
            
            # Extract tags safely
            if april_data is not None:
                # 🚀 API EXACT CALL: .aprilTags (Capital T)
                for tag in april_data.aprilTags: 
                    tag_id = tag.id
                    print(f"🎯 DETECTED TAG ID: [{tag_id}] -> Trigger Ready")

                    if frame is not None:
                        # Draw tracking constraints directly mapped to hardware bounding box detection
                        pt1 = (int(tag.topLeft.x), int(tag.topLeft.y))
                        pt2 = (int(tag.topRight.x), int(tag.topRight.y))
                        pt3 = (int(tag.bottomRight.x), int(tag.bottomRight.y))
                        pt4 = (int(tag.bottomLeft.x), int(tag.bottomLeft.y))
                        
                        # Box overlay 
                        cv2.line(frame, pt1, pt2, (0, 255, 0), 2)
                        cv2.line(frame, pt2, pt3, (0, 255, 0), 2)
                        cv2.line(frame, pt3, pt4, (0, 255, 0), 2)
                        cv2.line(frame, pt4, pt1, (0, 255, 0), 2)
                        cv2.putText(frame, f"ID: {tag_id}", pt1, cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)

            # Render loop constraint
            if frame is not None:
                cv2.imshow("SENSEY Native AprilTag Scan", frame)
            
            if cv2.waitKey(1) == ord('q'):
                break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()