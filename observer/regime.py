# observer/regime.py
from observer.utils import now_ms
from observer import config
from engine.state import MarketState


def detect_regime(ms: MarketState) -> tuple[str, dict]:
    """
    Regime detector (v1 heuristic):

    UNSTABLE:
      - spread too wide, or
      - latency p95 too high

    FAST:
      - trade intensity high, or
      - mid moves sufficiently within 10s

    Else:
      NORMAL

    Returns:
      (regime: str, metrics: dict)
    """
    t = now_ms()

    spread = ms.spread
    trades_n = ms.trades_count_10s(t)
    lat_p95 = ms.latency_p95_10s(t)
    mid_d = ms.mid_delta_10s(t)

    # Build metrics once (avoid drift across branches)
    metrics = {
        "spread": spread,
        "trades_10s": trades_n,
        "lat_p95": lat_p95,
        "mid_delta_10s": mid_d,
    }

    # ---------- UNSTABLE (hard) ----------
    if spread is not None and spread > config.SPREAD_UNSTABLE:
        return "UNSTABLE", metrics

    if lat_p95 is not None and lat_p95 > config.LAT_UNSTABLE_MS:
        return "UNSTABLE", metrics

    # ---------- FAST (market speed) ----------
    if trades_n >= config.FAST_TRADES_PER_10S:
        return "FAST", metrics

    if mid_d is not None and abs(mid_d) >= config.FAST_MID_DELTA_10S:
        return "FAST", metrics

    return "NORMAL", metrics
