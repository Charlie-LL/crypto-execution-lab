# state.py
from dataclasses import dataclass, field
from typing import Optional, Deque
from collections import deque

@dataclass
class MarketState:
    # BBO
    bid_px: Optional[float] = None
    bid_sz: Optional[float] = None
    ask_px: Optional[float] = None
    ask_sz: Optional[float] = None
    bbo_recv_ts: Optional[int] = None

    # recent trades stats (rolling 10s)
    trades_10s: Deque[tuple] = field(default_factory=lambda: deque())  
    # each item: (recv_ts_ms, exch_ts_ms, latency_ms, price, qty, is_buyer_maker)

    # derived / regime
    regime: str = "UNKNOWN"
    last_regime_ts: Optional[int] = None

    @property
    def spread(self) -> Optional[float]:
        if self.bid_px is None or self.ask_px is None:
            return None
        return self.ask_px - self.bid_px

    @property
    def mid(self) -> Optional[float]:
        if self.bid_px is None or self.ask_px is None:
            return None
        return (self.ask_px + self.bid_px) / 2.0

    def prune_trades(self, now_ms: int, window_ms: int = 10_000) -> None:
        while self.trades_10s and (now_ms - self.trades_10s[0][0] > window_ms):
            self.trades_10s.popleft()

    def trades_count_10s(self, now_ms: int) -> int:
        self.prune_trades(now_ms)
        return len(self.trades_10s)

    def latency_p95_10s(self, now_ms: int) -> Optional[float]:
        self.prune_trades(now_ms)
        if not self.trades_10s:
            return None
        lats = sorted(x[2] for x in self.trades_10s)
        idx = int(0.95 * (len(lats) - 1))
        return float(lats[idx])

    def mid_delta_10s(self, now_ms: int) -> Optional[float]:
        # compare earliest mid estimate to latest trade price in 10s window (simple proxy)
        self.prune_trades(now_ms)
        if len(self.trades_10s) < 2:
            return None
        first_px = self.trades_10s[0][3]
        last_px = self.trades_10s[-1][3]
        return float(last_px - first_px)
