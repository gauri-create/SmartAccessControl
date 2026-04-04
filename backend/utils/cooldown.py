import time

class CooldownManager:
    def __init__(self, cooldown_seconds=15):
        self.cooldown = cooldown_seconds
        self.last_logged = {}  # (name, event_type) → timestamp

    def can_log(self, name, event_type="GENERAL"):
        now = time.time()
        key = (name, event_type)

        if key in self.last_logged:
            if now - self.last_logged[key] < self.cooldown:
                return False

        self.last_logged[key] = now
        return True