import cv2
from backend.services.face_service import recognize_face
from backend.services.log_service import log_event

def run_detection():
    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        locations, names = recognize_face(frame)

        for name in names:
            if name == "Unknown":
                log_event(name, "ALERT")
            else:
                log_event(name, "ENTRY")

        cv2.imshow("Camera", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()