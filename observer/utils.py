# utils.py
import time

def now_ms() -> int:
    return int(time.time() * 1000)

def now_s() -> int:
    return int(time.time())

def safe_float(x, default=None):
    try:
        return float(x)
    except Exception:
        return default
