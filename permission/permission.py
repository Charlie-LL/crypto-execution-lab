# permission.py
from dataclasses import dataclass
from typing import Optional
from observer.utils import now_ms

@dataclass
class PermissionConfig:
    # persistence thresholds
    unstable_persist_ms: int = 2000      # UNSTABLE needs to persist >=2s
    wide_spread_persist_ms: int = 500    # spread wide needs to persist >=0.5s
    lat_spike_ms: int = 1200            # latency p95 spike threshold (ms)
    lat_spike_consec: int = 2
   
    # state durations
    cooldown_ms: int = 60_000           # after BLOCKED, must cooldown
    probation_ms: int = 30_000          # must stay NORMAL this long to ALLOW

    # spread threshold
    spread_unstable: float = 0.50       # same meaning as config.SPREAD_UNSTABLE


class PermissionEngine:
    """
    Permission engine is a STATE MACHINE that decides whether trading is allowed.
    It never places orders. It only outputs:
      - current_state
      - can_trade()
      - transition logs
    States:
      ALLOW -> BLOCKED -> COOLDOWN -> PROBATION -> ALLOW
    """

    def __init__(self, cfg: PermissionConfig, alert_logger=None, symbol: str = ""):
        self.cfg = cfg
        self.symbol = symbol

        self.state: str = "ALLOW"  # start permissive; you can start as "BLOCKED" if you prefer
        self.state_since_ms: int = now_ms()

        # persistence trackers
        self._unstable_since_ms: Optional[int] = None
        self._wide_spread_since_ms: Optional[int] = None

        self.alert_logger = alert_logger  # optional CSVLogger for state transitions
        self._lat_spike_count = 0

    def _log(self, level: str, code: str, msg: str, extra: dict | None = None):
        if self.alert_logger is None:
            print(f"[PERM][{level}][{code}] {msg} {extra if extra else ''}")
            return
        row = {
            "ts_ms": now_ms(),
            "level": level,
            "code": code,
            "msg": msg,
            "extra": "" if extra is None else str(extra),
        }
        self.alert_logger.write(row)
        print(f"[PERM][{level}][{code}] {msg} {extra if extra else ''}")

    def can_trade(self) -> bool:
        return self.state == "ALLOW"

    def _set_state(self, new_state: str, reason: str, extra: dict | None = None):
        if new_state == self.state:
            return
        old = self.state
        self.state = new_state
        self.state_since_ms = now_ms()
        self._log("INFO", "PERMISSION_TRANSITION", f"{old} -> {new_state} | {reason}", extra)

    def update(self, regime: str, metrics: dict):
        """
        Called periodically (e.g., every 10s) with:
          regime: NORMAL/FAST/UNSTABLE/UNKNOWN
          metrics: includes spread, lat_p95, etc.
        This function maintains persistence timers and drives transitions.
        """
        t = now_ms()
        spread = metrics.get("spread", None)
        lat_p95 = metrics.get("lat_p95", None)

        # --- update persistence clocks ---
        # UNSTABLE persistence
        if regime == "UNSTABLE":
            if self._unstable_since_ms is None:
                self._unstable_since_ms = t
        else:
            self._unstable_since_ms = None

        # wide spread persistence (based on spread threshold, independent of regime)
        is_wide = (spread is not None and spread > self.cfg.spread_unstable)
        if is_wide:
            if self._wide_spread_since_ms is None:
                self._wide_spread_since_ms = t
        else:
            self._wide_spread_since_ms = None

        # latency spike is "instant" trigger (optional persistence could be added later)
        lat_spike_now = (lat_p95 is not None and lat_p95 > self.cfg.lat_spike_ms)
        if lat_spike_now:
            self._lat_spike_count += 1
        else:
            self._lat_spike_count = 0

        lat_spike = self._lat_spike_count >= self.cfg.lat_spike_consec

        # --- determine BLOCK condition ---
        unstable_persist = (
            self._unstable_since_ms is not None
            and (t - self._unstable_since_ms) >= self.cfg.unstable_persist_ms
        )
        wide_persist = (
            self._wide_spread_since_ms is not None
            and (t - self._wide_spread_since_ms) >= self.cfg.wide_spread_persist_ms
        )

        should_block = unstable_persist or wide_persist or lat_spike

        # --- state machine transitions ---
        if self.state == "ALLOW":
            if should_block:
                reason = "latency_spike" if lat_spike else ("unstable_persist" if unstable_persist else "wide_spread_persist")
                self._set_state("BLOCKED", reason, {"spread": spread, "lat_p95": lat_p95, "regime": regime})

        elif self.state == "BLOCKED":
            # immediately enter cooldown (no debate)
            self._set_state("COOLDOWN", "enter cooldown after block", {"regime": regime})

        elif self.state == "COOLDOWN":
            if (t - self.state_since_ms) >= self.cfg.cooldown_ms:
                self._set_state("PROBATION", "cooldown complete", {"regime": regime})

        elif self.state == "PROBATION":
            safe_regime = (regime in ("NORMAL", "FAST"))

            if safe_regime and not should_block:
                if (t - self.state_since_ms) >= self.cfg.probation_ms:
                    self._set_state("ALLOW", "probation passed", {"spread": spread, "lat_p95": lat_p95, "regime": regime})
            else:
                if should_block:
                    reason = "latency_spike" if lat_spike else ("unstable_persist" if unstable_persist else "wide_spread_persist")
                    self._set_state("BLOCKED", f"probation failed: {reason}", {"spread": spread, "lat_p95": lat_p95, "regime": regime})
                else:
                    # regime UNKNOWN 等：保守起见，重置 probation 计时（这里必须真的重置）
                    self._set_state("PROBATION_RESET", f"reset probation due to regime={regime}", {"regime": regime})
                    self.state = "PROBATION"
                    self.state_since_ms = now_ms()
        else:
            # unknown state -> safe default
            self._set_state("BLOCKED", "unknown state -> safe block", {"state": self.state})
