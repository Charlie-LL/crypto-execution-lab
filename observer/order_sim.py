# order_sim.py
from dataclasses import dataclass
from typing import Optional, List
import random
from observer.utils import now_ms


@dataclass
class SimOrder:
    id: int
    ts_ms: int
    side: str          # BUY / SELL
    px: float
    qty: float
    tif_ms: int
    mode: str          # PASSIVE_ONLY / LIMIT_OK
    budget: float
    status: str = "OPEN"  # OPEN / FILLED / CANCELED

@dataclass
class SimFill:
    order_id: int
    order_ts_ms: int
    fill_ts_ms: int
    side: str
    order_px: float
    fill_px: float
    qty: float
    wait_ms: int
    slippage_bps_vs_mid: float

class OrderSim:
    """
    Paper execution simulator.
    - Places simulated orders based on final decision.
    - Fills are determined from incoming BBO.
    """
    def __init__(self, orders_logger, fills_logger, base_qty: float = 0.001, tif_ms: int = 10_000):
        self.orders_logger = orders_logger
        self.fills_logger = fills_logger
        self.base_qty = base_qty
        self.tif_ms = tif_ms

        self._next_id = 1
        self.open_orders: List[SimOrder] = []

        # for slippage calc
        self._last_mid: Optional[float] = None

    def update_bbo(self, recv_ts: int, bid: float, ask: float):
        mid = (bid + ask) / 2.0
        self._last_mid = mid

        # check fills / cancels
        still_open = []
        for o in self.open_orders:
            if o.status != "OPEN":
                continue

            # cancel if expired
            if recv_ts - o.ts_ms >= o.tif_ms:
                o.status = "CANCELED"
                continue

            # fill logic
            if o.side == "BUY":
                # passive: fill when ask <= order_px; aggressive: order_px is ask, so should fill immediately
                if ask <= o.px:
                    self._fill(o, recv_ts, ask, mid)
                else:
                    still_open.append(o)
            else:
                if bid >= o.px:
                    self._fill(o, recv_ts, bid, mid)
                else:
                    still_open.append(o)

        self.open_orders = still_open

    def maybe_place_order(self, final_allowed: bool, final_aggr: str, risk_budget: float,
                          bid: Optional[float], ask: Optional[float]):
        if not final_allowed:
            return
        if bid is None or ask is None:
            return
        if risk_budget <= 0:
            return

        # training signal: randomly decide to place or not
        if random.random() > 0.5:
            return

        side = "BUY" if random.random() < 0.5 else "SELL"
        qty = self.base_qty * max(0.2, min(1.0, risk_budget))  # clamp scaling

        if final_aggr == "PASSIVE_ONLY":
            px = bid if side == "BUY" else ask
            mode = "PASSIVE_ONLY"
        else:
            # LIMIT_OK
            px = ask if side == "BUY" else bid
            mode = "LIMIT_OK"

        o = SimOrder(
            id=self._next_id,
            ts_ms=now_ms(),
            side=side,
            px=float(px),
            qty=float(qty),
            tif_ms=self.tif_ms,
            mode=mode,
            budget=float(risk_budget)
        )
        self._next_id += 1
        self.open_orders.append(o)

        self.orders_logger.write({
            "id": o.id,
            "ts_ms": o.ts_ms,
            "side": o.side,
            "px": o.px,
            "qty": o.qty,
            "tif_ms": o.tif_ms,
            "mode": o.mode,
            "budget": o.budget
        })

    def _fill(self, o: SimOrder, fill_ts: int, fill_px: float, mid: float):
        o.status = "FILLED"
        wait = fill_ts - o.ts_ms

        # slippage vs mid
        if mid > 0:
            if o.side == "BUY":
                slip = (fill_px - mid) / mid * 10000.0
            else:
                slip = (mid - fill_px) / mid * 10000.0
        else:
            slip = 0.0

        self.fills_logger.write({
            "order_id": o.id,
            "order_ts_ms": o.ts_ms,
            "fill_ts_ms": fill_ts,
            "side": o.side,
            "order_px": o.px,
            "fill_px": float(fill_px),
            "qty": o.qty,
            "wait_ms": wait,
            "slippage_bps_vs_mid": slip
        })
