# execution/order_engine.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any

from observer.utils import now_ms
from execution.order_state import WorkingOrder, OrderStatus, ExecDecision
from execution.policy import ExecutionPolicy, PolicyConfig


@dataclass
class ExecAction:
    """
    Execution action event for audit/replay.
    """
    ts_ms: int
    action: str               # PLACE / CANCEL / REPRICE / FILL / EXPIRE
    order_id: int
    side: str
    px_old: Optional[float]
    px_new: Optional[float]
    qty: float
    reason: str
    extra: Optional[Dict[str, Any]] = None


class SingleOrderEngine:
    """
    Industrial v1 paper order engine:
    - Single working order at any time
    - Order lifecycle management
    - TTL expiry
    - Repricing based on policy
    - Fill simulation driven by live BBO
    """

    def __init__(self, actions_logger, fills_logger,orders_logger=None,metrics=None, base_qty: float = 0.001, cfg: Optional[PolicyConfig] = None):
        self._next_side = "BUY"
        self.actions_logger = actions_logger
        self.fills_logger = fills_logger
        self.metrics = metrics
        self.orders_logger = orders_logger

        self.base_qty = base_qty
        self.policy = ExecutionPolicy(cfg or PolicyConfig())

        self._next_id = 1
        self.wo: Optional[WorkingOrder] = None

        self._last_mid: Optional[float] = None

        # Cache latest BBO
        self._bid: Optional[float] = None
        self._ask: Optional[float] = None
        self._bbo_ts: Optional[int] = None

        self.min_fill_latency_ms = 200        # realistic paper matching delay
        self.max_reprices_per_order = 5       # cancel after too many reprices
        self._reprice_count = 0

    # -----------------------------
    # External hooks
    # -----------------------------

    def on_bbo(self, ts_ms: int, bid: float, ask: float) -> None:
        """
        Called on every BBO update.
        Drives:
          - expiry
          - fills
          - repricing decisions (if order is LIVE)
        """
        self._bid, self._ask, self._bbo_ts = bid, ask, ts_ms
        self._last_mid = (bid + ask) / 2.0

        if self.wo is None:
            return

        # Expire
        if self.wo.status in (OrderStatus.NEW, OrderStatus.LIVE):
            if ts_ms - self.wo.ts_ms >= self.wo.tif_ms:
                self._expire(ts_ms, reason="ttl_expired")
                return

        # Fill simulation
        if self.wo.status in (OrderStatus.NEW, OrderStatus.LIVE):
            if self._is_fillable(self.wo, bid, ask, ts_ms):
                self._fill(ts_ms, bid, ask, reason="bbo_cross")
                return

        # Reprice if still alive
        if self.wo is not None and self.wo.status in (OrderStatus.NEW, OrderStatus.LIVE):
            # Optional stale cancel protection
            if self.policy.should_cancel_on_cross(self.wo.side, self.wo.px, bid, ask):
                self._cancel(ts_ms, reason="stale_cross")
                return

            if self.policy.should_reprice(self.wo.side, self.wo.mode, self.wo.px, bid, ask):
                new_px = self.policy.target_price(self.wo.side, self.wo.mode, bid, ask)
                self._reprice(ts_ms, new_px, reason="best_price_changed")

    def on_decision(self, dec: ExecDecision, ts_ms: int) -> None:
        """
        Called on every decision tick (e.g., PRINT_EVERY_SEC).
        Decides whether to:
          - cancel existing order
          - place a new order
        """
        # If we cannot trade, kill any working order
        if (not dec.allowed) or dec.max_aggr == "NO_TRADE" or dec.risk_budget <= 0:
            if self.wo is not None and self.wo.status in (OrderStatus.NEW, OrderStatus.LIVE):
                self._cancel(ts_ms, reason="decision_disallow")
            return

        # Need BBO to price orders
        if self._bid is None or self._ask is None:
            return

        # If there is an order, check if mode/budget changed materially
        if self.wo is not None and self.wo.status in (OrderStatus.NEW, OrderStatus.LIVE):
            if self.wo.mode != dec.max_aggr:
                self._cancel(ts_ms, reason="aggr_changed")
            else:
                # If budget changed a lot, you may cancel/replace (v1: simple threshold)
                if abs(self.wo.budget - dec.risk_budget) >= 0.25:
                    self._cancel(ts_ms, reason="budget_changed")

        # If no live order after possible cancel, place a new one
        if self.wo is None:
            side = self._choose_side_training()
            qty = self.base_qty * max(0.2, min(1.0, dec.risk_budget))
            px = self.policy.target_price(side, dec.max_aggr, self._bid, self._ask)
            self._place(ts_ms, side=side, px=px, qty=qty, mode=dec.max_aggr, budget=dec.risk_budget)

    # -----------------------------
    # Internal actions
    # -----------------------------

    def _place(self, ts_ms: int, side: str, px: float, qty: float, mode: str, budget: float) -> None:
        oid = self._next_id
        self._next_id += 1

        self.wo = WorkingOrder(
            id=oid,
            ts_ms=ts_ms,
            side=side,
            px=float(px),
            qty=float(qty),
            tif_ms=self.policy.cfg.ttl_ms,
            mode=mode,
            budget=float(budget),
            status=OrderStatus.LIVE
        )

        self._log_action(ts_ms, "PLACE", oid, side, None, px, qty, reason="new_order")

        if self.orders_logger is not None:
            self.orders_logger.write({
                "id": oid,
                "ts_ms": ts_ms,
                "side": side,
                "px": float(px),
                "qty": float(qty),
                "tif_ms": int(self.policy.cfg.ttl_ms),
                "mode": mode,
                "budget": float(budget),
            })

        if self.metrics is not None:
            self.metrics.on_place()
        
        self._reprice_count = 0

        

    def _cancel(self, ts_ms: int, reason: str) -> None:
        if self.wo is None:
            return
        oid = self.wo.id
        side = self.wo.side
        px = self.wo.px
        qty = self.wo.qty

        self.wo.status = OrderStatus.CANCELED
        self._log_action(ts_ms, "CANCEL", oid, side, px, None, qty, reason=reason)
        self.wo = None

        if self.metrics is not None:
            self.metrics.on_cancel()

    def _expire(self, ts_ms: int, reason: str) -> None:
        if self.wo is None:
            return
        oid = self.wo.id
        side = self.wo.side
        px = self.wo.px
        qty = self.wo.qty

        self.wo.status = OrderStatus.EXPIRED
        self._log_action(ts_ms, "EXPIRE", oid, side, px, None, qty, reason=reason)
        self.wo = None

    def _reprice(self, ts_ms: int, new_px: float, reason: str) -> None:
        if self.wo is None:
            return

        self._reprice_count += 1

        # If repricing too many times, cancel to avoid endless chasing
        if self._reprice_count > self.max_reprices_per_order:
            self._cancel(ts_ms, reason="too_many_reprices")
            return

        oid = self.wo.id
        side = self.wo.side
        old_px = self.wo.px
        qty = self.wo.qty

        self.wo.px = float(new_px)
        self._log_action(ts_ms, "REPRICE", oid, side, old_px, new_px, qty, reason=reason)

    def _fill(self, ts_ms: int, bid: float, ask: float, reason: str) -> None:
        """
        Fill simulation:
        - For BUY: fill at ask when ask <= order_px
        - For SELL: fill at bid when bid >= order_px
        """
        if self.wo is None:
            return

        o = self.wo
        fill_px = ask if o.side == "BUY" else bid
        mid = self._last_mid or ((bid + ask) / 2.0)

        # Slippage vs mid (bps)
        if mid > 0:
            if o.side == "BUY":
                slip = (fill_px - mid) / mid * 10000.0
            else:
                slip = (mid - fill_px) / mid * 10000.0
        else:
            slip = 0.0

        wait_ms = ts_ms - o.ts_ms

        # Log fill action
        self._log_action(ts_ms, "FILL", o.id, o.side, o.px, fill_px, o.qty, reason=reason,
                         extra={"wait_ms": wait_ms, "slippage_bps_vs_mid": slip})

        # Log fills.csv
        self.fills_logger.write({
            "order_id": o.id,
            "order_ts_ms": o.ts_ms,
            "fill_ts_ms": ts_ms,
            "side": o.side,
            "order_px": o.px,
            "fill_px": float(fill_px),
            "qty": o.qty,
            "wait_ms": int(wait_ms),
            "slippage_bps_vs_mid": float(slip),
        })

        o.status = OrderStatus.FILLED
        self.wo = None

        if self.metrics is not None:
            self.metrics.on_fill(fill_px=float(fill_px), mid_px=float(mid), wait_ms=int(wait_ms))

    # -----------------------------
    # Helpers
    # -----------------------------

    def _is_fillable(self, o: WorkingOrder, bid: float, ask: float, ts_ms: int) -> bool:
        """
        Paper fill model with basic microstructure friction:
        - Enforce minimum time before a fill can happen
        - PASSIVE_ONLY behaves like maker (less likely to fill immediately)
        - LIMIT_OK behaves like taker-ish limit (can cross and fill)
        """
        # 1) minimum matching latency
        if ts_ms - o.ts_ms < self.min_fill_latency_ms:
            return False

        # 2) mode-based fill logic
        if o.mode == "PASSIVE_ONLY":
            # Maker-style: require a "cross-through" event to simulate queue + adverse selection risk.
            # BUY: market ask must move down through our bid/price (ask <= px)
            # SELL: market bid must move up through our ask/price (bid >= px)
            if o.side == "BUY":
                return ask <= o.px
            return bid >= o.px

        # LIMIT_OK: allow immediate cross fills (still delayed by min_fill_latency_ms)
        if o.side == "BUY":
            return ask <= o.px
        return bid >= o.px

    def _choose_side_training(self) -> str:
        """
        Training-only: deterministic alternation to avoid sampling alignment bias.
        """
        side = self._next_side
        self._next_side = "SELL" if side == "BUY" else "BUY"
        return side
    
    def _log_action(self, ts_ms: int, action: str, oid: int, side: str,
                    px_old: Optional[float], px_new: Optional[float], qty: float,
                    reason: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self.actions_logger.write({
            "ts_ms": ts_ms,
            "action": action,
            "order_id": oid,
            "side": side,
            "px_old": "" if px_old is None else px_old,
            "px_new": "" if px_new is None else px_new,
            "qty": qty,
            "reason": reason,
            "extra": "" if extra is None else str(extra),
        })
