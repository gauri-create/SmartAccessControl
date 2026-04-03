import face_recognition
import os
import pickle

DATASET_PATH = "ml/dataset"
ENCODINGS_PATH = "encodings/encodings.pkl"

known_encodings = []
known_names = []

for person_name in os.listdir(DATASET_PATH):
    person_path = os.path.join(DATASET_PATH, person_name)

    for image_name in os.listdir(person_path):
        image_path = os.path.join(person_path, image_name)

        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)

        if len(encodings) > 0:
            known_encodings.append(encodings[0])
            known_names.append(person_name)

data = {
    "encodings": known_encodings,
    "names": known_names
}

with open(ENCODINGS_PATH, "wb") as f:
    pickle.dump(data, f)

print("Encodings saved successfully")