# execution/policy.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PolicyConfig:
    """
    Execution policy parameters.
    Keep these in config later if you want, but start here for clarity.
    """
    ttl_ms: int = 10_000

    # Repricing: if best price moved away from our order, reprice to stay on top.
    # For PASSIVE_ONLY: BUY order should track best_bid; SELL should track best_ask.
    # For LIMIT_OK: BUY tracks best_ask; SELL tracks best_bid.
    reprice_on_best_change: bool = True

    # If the market crosses far beyond our intended price, cancel immediately.
    # This protects from stale orders in fast markets.
    cancel_on_cross: bool = True


class ExecutionPolicy:
    """
    Policy decides:
      - target price for an order given (aggr, side, bid, ask)
      - whether to reprice/cancel based on new BBO
    """

    def __init__(self, cfg: PolicyConfig):
        self.cfg = cfg

    def target_price(self, side: str, aggr: str, bid: float, ask: float) -> float:
        """
        Decide the target limit price based on aggressiveness.
        PASSIVE_ONLY: maker-ish price (BUY->bid, SELL->ask)
        LIMIT_OK:     taker-ish limit (BUY->ask, SELL->bid)
        """
        if aggr == "PASSIVE_ONLY":
            return bid if side == "BUY" else ask
        # LIMIT_OK (or other future modes)
        return ask if side == "BUY" else bid

    def should_reprice(self, side: str, aggr: str, current_px: float, bid: float, ask: float) -> bool:
        """
        Reprice when best price moves away from our order price.
        """
        if not self.cfg.reprice_on_best_change:
            return False

        tgt = self.target_price(side, aggr, bid, ask)
        return tgt != current_px

    def should_cancel_on_cross(self, side: str, current_px: float, bid: float, ask: float) -> bool:
        """
        Cancel if market moved across our order in an unfavorable way (stale risk).
        Example:
          BUY order at 100, but now best_ask << 100 (market dropped) -> cancel to avoid adverse selection.
          SELL order at 100, but now best_bid >> 100 (market pumped) -> cancel.
        """
        if not self.cfg.cancel_on_cross:
            return False

        if side == "BUY":
            # If ask is far below our price, we might have become stale (market moved down).
            return ask < current_px
        else:
            # If bid is far above our price, stale on the upside for sells.
            return bid > current_px
