import json
import time
import threading
import websocket

from observer import config
from observer.utils import now_ms
from observer.logger import CSVLogger
from observer.regime import detect_regime
from observer.order_sim import OrderSim
from observer.paths import PathConfig

from engine.state import MarketState
from engine.decision import safety_decision

from health.health import health_score, HealthConfig
from permission.permission import PermissionEngine, PermissionConfig
from risk.risk_guard import RiskGuard


def stream_url() -> str:
    """
    Binance combined streams endpoint.
    Subscribe to: trade + bookTicker for the same symbol.
    """
    sym = config.SYMBOL.lower()
    streams = f"{sym}@trade/{sym}@bookTicker"
    return f"wss://stream.binance.com:9443/stream?streams={streams}"


class MarketObserver:
    """
    Industrial-grade observer loop:
    - Stable path management (root/data/symbol=<SYMBOL>/...)
    - WS ingest (trade + bookTicker)
    - Regime + Permission + Health + Final Decision
    - Paper execution simulator (OrderSim), no real trading
    - CSV logging (single source of truth for debugging/backtesting)
    """

    def __init__(self):
        # ---- Resolve output directory (industrial path layout) ----
        self.paths = PathConfig.from_env(default_subdir="data")
        self.sym_dir = self.paths.symbol_dir(config.SYMBOL)

        print("BOOT CONFIG:")
        print("SYMBOL:", config.SYMBOL)
        print("OUT_DIR:", str(self.sym_dir))
        print("SPREAD_UNSTABLE:", config.SPREAD_UNSTABLE)
        print("LAT_UNSTABLE_MS:", config.LAT_UNSTABLE_MS)
        print("PRINT_EVERY_SEC:", config.PRINT_EVERY_SEC)

        # ---- Shared market state + lock ----
        self.ms = MarketState()
        self._lock = threading.Lock()

        self._ws = None
        self._stop = False
        self._last_msg_ms = None

        # ---- CSV loggers (symbol-scoped) ----
        self.trades_log = CSVLogger(
            str(self.paths.file(config.SYMBOL, config.FILES["trades"])),
            ["exch_ts", "recv_ts", "latency_ms", "price", "qty", "is_buyer_maker"]
        )

        self.bbo_log = CSVLogger(
            str(self.paths.file(config.SYMBOL, config.FILES["bbo"])),
            ["recv_ts", "bid_px", "bid_sz", "ask_px", "ask_sz", "spread", "mid"]
        )

        self.regime_log = CSVLogger(
            str(self.paths.file(config.SYMBOL, config.FILES["regime"])),
            [
                "ts_ms", "regime",
                "spread", "trades_10s", "lat_p95", "mid_delta_10s",
                "perm_state", "can_trade",
                "health", "health_mode", "max_aggr",
                "final_allowed", "final_aggr", "risk_budget", "decision_reason"
            ]
        )

        self.alerts_log = CSVLogger(
            str(self.paths.file(config.SYMBOL, config.FILES["alerts"])),
            ["ts_ms", "level", "code", "msg", "extra"]
        )

        # ---- Paper execution logs ----
        orders_name = config.FILES.get("orders", "orders.csv")
        fills_name = config.FILES.get("fills", "fills.csv")

        self.orders_log = CSVLogger(
            str(self.paths.file(config.SYMBOL, orders_name)),
            ["id", "ts_ms", "side", "px", "qty", "tif_ms", "mode", "budget"]
        )
        self.fills_log = CSVLogger(
            str(self.paths.file(config.SYMBOL, fills_name)),
            ["order_id", "order_ts_ms", "fill_ts_ms", "side", "order_px", "fill_px",
             "qty", "wait_ms", "slippage_bps_vs_mid"]
        )

        # ---- Risk guard (alerts helper) ----
        self.guard = RiskGuard(self.alerts_log)

        # ---- Permission engine (state machine) ----
        self.perm = PermissionEngine(
            cfg=PermissionConfig(
                spread_unstable=config.SPREAD_UNSTABLE,
                lat_spike_ms=config.PERM_LAT_SPIKE_MS,
                lat_spike_consec=config.PERM_LAT_SPIKE_CONSEC,
                unstable_persist_ms=config.PERM_UNSTABLE_PERSIST_MS,
                wide_spread_persist_ms=config.PERM_WIDE_SPREAD_PERSIST_MS,
                cooldown_ms=config.PERM_COOLDOWN_MS,
                probation_ms=config.PERM_PROBATION_MS,
            ),
            alert_logger=self.alerts_log,
            symbol=config.SYMBOL
        )

        # ---- Health scoring ----
        self.hcfg = HealthConfig(
            spread_unstable=config.SPREAD_UNSTABLE,
            lat_unstable_ms=config.LAT_UNSTABLE_MS,
        )

        # ---- Paper execution simulator (NO REAL TRADING) ----
        self.sim = OrderSim(
            orders_logger=self.orders_log,
            fills_logger=self.fills_log,
            base_qty=0.001,   # simulation only
            tif_ms=10_000     # simulation only
        )

    # ============================================================
    # WS callbacks
    # ============================================================

    def _on_open(self, ws):
        print("[WS] OPEN")
        self._last_msg_ms = now_ms()

    def _on_close(self, ws, *args):
        print("[WS] CLOSED")

    def _on_error(self, ws, error):
        print("[WS] ERROR:", error)

    def _on_message(self, ws, message: str):
        """
        Combined stream message:
        {"stream": "...", "data": {...}}
        """
        recv_ts = now_ms()
        self._last_msg_ms = recv_ts

        try:
            msg = json.loads(message)
        except Exception:
            return

        data = msg.get("data", {})
        etype = data.get("e")

        if etype == "trade":
            self._handle_trade(data, recv_ts)
        elif "b" in data and "a" in data:
            self._handle_bbo(data, recv_ts)

    # ============================================================
    # Trade / BBO handlers
    # ============================================================

    def _handle_trade(self, payload: dict, recv_ts: int):
        """
        Trade payload:
        E: event time (ms), p: price, q: qty, m: buyer is maker
        """
        exch_ts = int(payload.get("E"))
        price = float(payload.get("p"))
        qty = float(payload.get("q"))
        is_buyer_maker = bool(payload.get("m"))

        latency = recv_ts - exch_ts

        with self._lock:
            self.ms.trades_10s.append((recv_ts, exch_ts, latency, price, qty, is_buyer_maker))
            self.ms.prune_trades(recv_ts)

        self.trades_log.write({
            "exch_ts": exch_ts,
            "recv_ts": recv_ts,
            "latency_ms": latency,
            "price": price,
            "qty": qty,
            "is_buyer_maker": int(is_buyer_maker)
        })

        # Single-trade latency warning (log only)
        if latency > config.LAT_UNSTABLE_MS:
            self.guard.alert(
                "WARN",
                "LAT_SPIKE",
                f"trade latency spike: {latency}ms",
                {"price": price, "qty": qty}
            )

    def _handle_bbo(self, payload: dict, recv_ts: int):
        """
        bookTicker payload:
        b,B = best bid price, qty
        a,A = best ask price, qty
        """
        bid_px = float(payload.get("b"))
        bid_sz = float(payload.get("B"))
        ask_px = float(payload.get("a"))
        ask_sz = float(payload.get("A"))

        with self._lock:
            self.ms.bid_px = bid_px
            self.ms.bid_sz = bid_sz
            self.ms.ask_px = ask_px
            self.ms.ask_sz = ask_sz
            self.ms.bbo_recv_ts = recv_ts

            spread = self.ms.spread
            mid = self.ms.mid

        self.bbo_log.write({
            "recv_ts": recv_ts,
            "bid_px": bid_px,
            "bid_sz": bid_sz,
            "ask_px": ask_px,
            "ask_sz": ask_sz,
            "spread": "" if spread is None else spread,
            "mid": "" if mid is None else mid
        })

        # Feed simulator to drive fills/cancels
        self.sim.update_bbo(recv_ts, bid_px, ask_px)

    # ============================================================
    # Core periodic loop
    # ============================================================

    def _printer(self):
        """
        Periodic brain loop:
        - snapshot metrics under lock
        - update permission
        - compute health
        - compute final decision
        - log regime + decision
        - place simulated orders
        """
        while not self._stop:
            time.sleep(config.PRINT_EVERY_SEC)

            # Snapshot under lock
            with self._lock:
                regime, metrics = detect_regime(self.ms)
                bid = getattr(self.ms, "bid_px", None)
                ask = getattr(self.ms, "ask_px", None)

            # Permission + health outside lock
            self.perm.update(regime, metrics)
            score, mode, max_aggr, _detail = health_score(metrics, self.hcfg)

            # Final decision
            dec = safety_decision(
                perm_state=self.perm.state,
                can_trade=self.perm.can_trade(),
                health_score=score,
                health_mode=mode,
                health_aggr=max_aggr
            )

            ts = now_ms()

            # Log regime + decision (single source of truth)
            self.regime_log.write({
                "ts_ms": ts,
                "regime": regime,
                "spread": metrics.get("spread"),
                "trades_10s": metrics.get("trades_10s"),
                "lat_p95": metrics.get("lat_p95"),
                "mid_delta_10s": metrics.get("mid_delta_10s"),
                "perm_state": self.perm.state,
                "can_trade": int(self.perm.can_trade()),
                "health": score,
                "health_mode": mode,
                "max_aggr": max_aggr,
                "final_allowed": int(dec.allowed),
                "final_aggr": dec.max_aggr,
                "risk_budget": dec.risk_budget,
                "decision_reason": dec.reason
            })

            print(
                f"[REGIME] {regime} | "
                f"[PERM] {self.perm.state}({int(self.perm.can_trade())}) | "
                f"[HEALTH] {score} {mode} {max_aggr} | "
                f"[DECISION] {int(dec.allowed)} {dec.max_aggr} budget={dec.risk_budget} reason={dec.reason}"
            )

            # Paper order placement (training only)
            self.sim.maybe_place_order(
                final_allowed=dec.allowed,
                final_aggr=dec.max_aggr,
                risk_budget=dec.risk_budget,
                bid=bid,
                ask=ask
            )

    # ============================================================
    # Start / reconnect loop
    # ============================================================

    def start(self):
        url = stream_url()
        print("[BOOT] Connecting:", url)

        self._stop = False
        threading.Thread(target=self._printer, daemon=True).start()

        self._ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )

        while not self._stop:
            try:
                self._ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                print("[WS] reconnect due to:", e)

            print("[WS] Reconnecting in 3s...")
            time.sleep(3)
