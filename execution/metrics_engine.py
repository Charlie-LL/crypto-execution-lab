# execution/metrics_engine.py

from collections import deque
from observer.utils import now_ms


class ExecutionMetrics:
    """
    Execution black-box recorder.
    Does NOT influence trading.
    """

    def __init__(self, markout_horizon_ms=5000):

        self.placed = 0
        self.filled = 0
        self.canceled = 0

        self.wait_times = []
        self.slippages = []

        # store fills waiting for markout
        self.pending_markouts = deque()

        self.markouts = []

        self.markout_horizon = markout_horizon_ms


    # ----------------------------
    # EVENTS
    # ----------------------------

    def on_place(self):
        self.placed += 1


    def on_cancel(self):
        self.canceled += 1


    def on_fill(self, fill_px, mid_px, wait_ms):
        self.filled += 1

        self.wait_times.append(wait_ms)

        if mid_px:
            slippage = abs(fill_px - mid_px) / mid_px * 10000
            self.slippages.append(slippage)

        # schedule markout
        self.pending_markouts.append({
            "ts": now_ms(),
            "fill_px": fill_px
        })


    def on_mid_update(self, mid_px):
        """
        Called from BBO updates.
        Checks if any markout matured.
        """

        now = now_ms()

        while self.pending_markouts:

            item = self.pending_markouts[0]

            if now - item["ts"] < self.markout_horizon:
                break

            markout = (mid_px - item["fill_px"]) / item["fill_px"] * 10000

            self.markouts.append(markout)

            self.pending_markouts.popleft()


    # ----------------------------
    # SNAPSHOT
    # ----------------------------

    def snapshot(self):

        fill_rate = self.filled / self.placed if self.placed else 0
        cancel_rate = self.canceled / self.placed if self.placed else 0

        avg_wait = sum(self.wait_times)/len(self.wait_times) if self.wait_times else 0
        avg_slip = sum(self.slippages)/len(self.slippages) if self.slippages else 0
        avg_markout = sum(self.markouts)/len(self.markouts) if self.markouts else 0

        return {
            "placed": self.placed,
            "filled": self.filled,
            "canceled": self.canceled,
            "fill_rate": round(fill_rate,3),
            "cancel_rate": round(cancel_rate,3),
            "avg_wait_ms": int(avg_wait),
            "avg_slippage_bps": round(avg_slip,2),
            "avg_markout_bps": round(avg_markout,2),
        }
