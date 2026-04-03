import face_recognition
import pickle
import os

ENCODINGS_PATH = "encodings/encodings.pkl"

def load_encodings():
    if not os.path.exists(ENCODINGS_PATH):
        print("Encodings file not found")
        return [], []
    
    with open(ENCODINGS_PATH, "rb") as f:
        data = pickle.load(f)
    
    return data.get("encodings", []), data.get("names", [])


try:
    known_encodings, known_names = load_encodings()
except:
    print("Encodings file is empty or corrupted")
    known_encodings, known_names = [], []


def recognize_face(frame):
    rgb = frame[:, :, ::-1]

    face_locations = face_recognition.face_locations(rgb)
    face_encodings = face_recognition.face_encodings(rgb, face_locations)

    names = []

    for encoding in face_encodings:
        matches = face_recognition.compare_faces(known_encodings, encoding)
        name = "Unknown"

        if True in matches:
            matched_idx = matches.index(True)
            name = known_names[matched_idx]

        names.append(name)

    return face_locations, names