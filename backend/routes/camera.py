from flask import Blueprint
from backend.services.detection_service import run_detection
import threading

camera_bp = Blueprint("camera", __name__)

@camera_bp.route("/start-camera")
def start_camera():
    thread = threading.Thread(target=run_detection)
    thread.start()
    return "Camera started"