# execution/order_state.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OrderStatus(str, Enum):
    """Order lifecycle states."""
    NEW = "NEW"
    LIVE = "LIVE"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"


@dataclass
class WorkingOrder:
    """
    Single working order representation (paper).
    """
    id: int
    ts_ms: int
    side: str                 # "BUY" / "SELL"
    px: float
    qty: float
    tif_ms: int               # time-in-force (TTL)
    mode: str                 # "PASSIVE_ONLY" / "LIMIT_OK"
    budget: float
    status: OrderStatus = OrderStatus.NEW

    filled_ts_ms: Optional[int] = None
    filled_px: Optional[float] = None


@dataclass
class ExecDecision:
    """
    Normalized decision inputs for the order engine.
    You can construct this from your engine.decision.safety_decision output.
    """
    allowed: bool
    max_aggr: str             # "PASSIVE_ONLY" / "LIMIT_OK" / "NO_TRADE"
    risk_budget: float        # 0..1 (your current design)
