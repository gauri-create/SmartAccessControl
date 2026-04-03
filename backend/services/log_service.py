from backend.models.log import Log
from backend.extensions import db

def log_event(name, status):
    log = Log(name=name, status=status)
    db.session.add(log)
    db.session.commit()