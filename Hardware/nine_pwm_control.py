# Libraries
import cv2
import serial
import time

# Detector
face_cascade = cv2.CascadeClassifier(
    r'C:\Users\Ian Clyde\mp-env\Lib\site-packages\cv2\data\haarcascade_frontalface_default.xml'
)

# Webcam start
cap = cv2.VideoCapture(0)

# Arduino Setup
arduino = serial.Serial(port='COM3', baudrate=9600, timeout=1)
time.sleep(2)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Flip horizontally
    frame = cv2.flip(frame, 1)

    height, width, _ = frame.shape
    third_w = width // 3
    third_h = height // 3

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
    )

    region = 0
    brightness = 0

    if len(faces) > 0:
        (x, y, w, h) = faces[0]

        # Determine REGION (1–9)
        cx = x + w // 2
        cy = y + h // 2

        # Column
        if cx < third_w:
            col = 1
        elif cx < 2 * third_w:
            col = 2
        else:
            col = 3

        # Row
        if cy < third_h:
            row = 1
        elif cy < 2 * third_h:
            row = 2
        else:
            row = 3

        region = (row - 1) * 3 + col

        # Determine BRIGHTNESS 0–255
        max_height = third_h
        val = int((h / max_height) * 255)

        if val > 255:
            val = 255
        if val < 0:
            val = 0

        brightness = val

    # -----------------------------------
    # SEND TO ARDUINO (important fix)
    # -----------------------------------
    send_str = f"{region},{brightness}\n"
    arduino.write(send_str.encode())   # ALWAYS include \n
    # -----------------------------------

    # Draw rectangles
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

    # Draw rule of thirds
    cv2.line(frame, (third_w, 0), (third_w, height), (0, 255, 0), 1)
    cv2.line(frame, (2 * third_w, 0), (2 * third_w, height), (0, 255, 0), 1)
    cv2.line(frame, (0, third_h), (width, third_h), (0, 255, 0), 1)
    cv2.line(frame, (0, 2 * third_h), (width, 2 * third_h), (0, 255, 0), 1)

    cv2.imshow("Real-Time Face Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
arduino.close()
