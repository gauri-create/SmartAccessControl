from flask import Flask
from backend.config import Config
from backend.extensions import db, socketio

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    socketio.init_app(app)

    from backend.routes.dashboard import dashboard_bp
    from backend.routes.camera import camera_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(camera_bp)

    return app