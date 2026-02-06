# risk_guard.py
from observer.utils import now_ms

class RiskGuard:
    """
    This guard does NOT place orders.
    It only raises alerts when market / system looks unhealthy.
    """
    def __init__(self, alert_logger):
        self.alert_logger = alert_logger
        self._last_alert_ms = 0

    def alert(self, level: str, code: str, msg: str, extra: dict | None = None, cooldown_ms: int = 3000):
        t = now_ms()
        if t - self._last_alert_ms < cooldown_ms:
            return
        self._last_alert_ms = t
        row = {
            "ts_ms": t,
            "level": level,
            "code": code,
            "msg": msg,
            "extra": "" if extra is None else str(extra),
        }
        self.alert_logger.write(row)
        print(f"[ALERT][{level}][{code}] {msg} {extra if extra else ''}")
