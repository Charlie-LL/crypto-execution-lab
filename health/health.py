# health/health.py
from dataclasses import dataclass


@dataclass
class HealthConfig:
    # Hard thresholds (aligned with config / permission)
    spread_unstable: float = 0.5
    lat_unstable_ms: int = 2500

    # "Good" anchors for scoring (not hard thresholds)
    spread_good: float = 0.03
    lat_good_ms: int = 800
    trades_10s_good: int = 1200
    mid_delta_10s_good: float = 25.0

    # Hard-red sensitivity knobs
    hard_red_spread_ratio: float = 0.9   # >= 0.9 * spread_unstable => hard red
    hard_red_lat_ratio: float = 0.9      # >= 0.9 * lat_unstable_ms => hard red
    hard_red_mid_mult: float = 3.0       # >= 3x mid_delta_10s_good => hard red


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def health_score(metrics: dict, cfg: HealthConfig) -> tuple[int, str, str, dict]:
    """
    Compute execution health score from metrics.

    Inputs (metrics):
      - spread
      - lat_p95
      - trades_10s
      - mid_delta_10s

    Outputs:
      - score: int in [0, 100]
      - mode: GREEN / YELLOW / RED
      - max_aggr: LIMIT_OK / PASSIVE_ONLY / NO_TRADE
      - detail: component scores
    """
    spread = metrics.get("spread")
    lat_p95 = metrics.get("lat_p95")
    trades_10s = metrics.get("trades_10s", 0) or 0
    mid_d = metrics.get("mid_delta_10s")

    # ---------- Hard risk gating (make RED rare but reliable) ----------
    hard_red = False

    if spread is not None and cfg.spread_unstable > 0:
        if spread >= cfg.spread_unstable * cfg.hard_red_spread_ratio:
            hard_red = True

    if lat_p95 is not None and cfg.lat_unstable_ms > 0:
        if lat_p95 >= cfg.lat_unstable_ms * cfg.hard_red_lat_ratio:
            hard_red = True

    if mid_d is not None and cfg.mid_delta_10s_good > 0:
        if abs(mid_d) >= cfg.mid_delta_10s_good * cfg.hard_red_mid_mult:
            hard_red = True

    # ---------- Component scores (0-100) ----------
    # Spread score
    if spread is None:
        s_spread = 50.0
    else:
        if spread >= cfg.spread_unstable:
            s_spread = 5.0
        else:
            ratio = spread / max(cfg.spread_good, 1e-9)
            s_spread = 100.0 - 25.0 * (ratio - 1.0)
            s_spread = _clamp(s_spread, 10.0, 100.0)

    # Latency score
    if lat_p95 is None:
        s_lat = 60.0
    else:
        if lat_p95 >= cfg.lat_unstable_ms:
            s_lat = 5.0
        else:
            ratio = lat_p95 / max(cfg.lat_good_ms, 1)
            s_lat = 100.0 - 35.0 * (ratio - 1.0)
            s_lat = _clamp(s_lat, 10.0, 100.0)

    # Flow score (v1.1: do not punish high flow; punish low flow)
    if trades_10s <= 0:
        s_flow = 30.0
    else:
        if trades_10s >= cfg.trades_10s_good:
            s_flow = 100.0
        else:
            ratio = trades_10s / max(cfg.trades_10s_good, 1)
            s_flow = 40.0 + 60.0 * ratio
            s_flow = _clamp(s_flow, 10.0, 100.0)

    # Move score
    if mid_d is None:
        s_move = 70.0
    else:
        dev = abs(mid_d) / max(cfg.mid_delta_10s_good, 1e-9)
        s_move = 100.0 - 60.0 * (dev - 1.0)
        s_move = _clamp(s_move, 10.0, 100.0)

    # Weighted score (spread/lat are more important)
    score = 0.35 * s_spread + 0.35 * s_lat + 0.15 * s_flow + 0.15 * s_move
    score_i = int(round(_clamp(score, 0.0, 100.0)))

    # ---------- Mode mapping ----------
    # If hard_red => NO_TRADE (regardless of score)
    if hard_red:
        mode = "RED"
        max_aggr = "NO_TRADE"
    else:
        # GREEN should mean "safe to be more aggressive"
        # YELLOW is the default "trade but conservative"
        if score_i >= 75:
            mode = "GREEN"
            max_aggr = "LIMIT_OK"
        elif score_i >= 45:
            mode = "YELLOW"
            max_aggr = "PASSIVE_ONLY"
        else:
            # low score but no hard red => still YELLOW (conservative),
            # avoid too many REDs due to score noise
            mode = "YELLOW"
            max_aggr = "PASSIVE_ONLY"

    detail = {
        "s_spread": int(round(s_spread)),
        "s_lat": int(round(s_lat)),
        "s_flow": int(round(s_flow)),
        "s_move": int(round(s_move)),
        "hard_red": int(hard_red),
    }
    return score_i, mode, max_aggr, detail
