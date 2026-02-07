import json
import time
import threading
try:
    import websocket
except ModuleNotFoundError:
    websocket = None

from observer import config
from observer.utils import now_ms
from observer.logger import CSVLogger
from observer.regime import detect_regime
from observer.paths import Paths

from engine.state import MarketState
from engine.decision import safety_decision

from permission.permission import PermissionEngine, PermissionConfig
from health.health import health_score, HealthConfig
from risk.risk_guard import RiskGuard

from execution.order_engine import SingleOrderEngine
from execution.order_state import ExecDecision
from execution.metrics_engine import ExecutionMetrics


def stream_url():
    s = f"{config.SYMBOL}@trade/{config.SYMBOL}@bookTicker"
    return f"wss://stream.binance.com:9443/stream?streams={s}"


class MarketObserver:

    def __init__(self):

        # ---------- paths ----------
        self.paths = Paths.from_env(default_subdir="data")


        print("BOOT CONFIG:")
        print("OUT_DIR:", str(self.paths.out_dir))
        print("SPREAD_UNSTABLE:", config.SPREAD_UNSTABLE)
        print("LAT_UNSTABLE_MS:", config.LAT_UNSTABLE_MS)
        print("PRINT_EVERY_SEC:", config.PRINT_EVERY_SEC)

        # ---------- core state ----------
        self.ms = MarketState()
        self._lock = threading.Lock()
        self._stop = False


        # ---------- loggers ----------
        self.trades_log = CSVLogger(
            str(self.paths.file(config.SYMBOL, config.FILES["trades"])),
            ["exch_ts","recv_ts","latency_ms","price","qty","is_buyer_maker"]
        )

        self.bbo_log = CSVLogger(
            str(self.paths.file(config.SYMBOL, config.FILES["bbo"])),
            ["recv_ts","bid_px","bid_sz","ask_px","ask_sz","spread","mid"]
        )

        self.regime_log = CSVLogger(
            str(self.paths.file(config.SYMBOL, config.FILES["regime"])),
            [
                "ts_ms","regime","spread","trades_10s",
                "lat_p95","mid_delta_10s",
                "perm_state","can_trade",
                "health","health_mode","max_aggr",
                "final_allowed","final_aggr","risk_budget","decision_reason"
            ]
        )

        self.alerts_log = CSVLogger(
            str(self.paths.file(config.SYMBOL, config.FILES["alerts"])),
            ["ts_ms","level","code","msg","extra"]
        )

        self.orders_log = CSVLogger(
            str(self.paths.file(config.SYMBOL, config.FILES["orders"])),
            ["id","ts_ms","side","px","qty","tif_ms","mode","budget"]
        )

        self.exec_actions_log = CSVLogger(
            str(self.paths.file(config.SYMBOL, "exec_actions.csv")),
            ["ts_ms","action","order_id","side","px_old","px_new","qty","reason","extra"]
        )

        self.fills_log = CSVLogger(
            str(self.paths.file(config.SYMBOL, "fills.csv")),
            ["order_id","order_ts_ms","fill_ts_ms","side","order_px","fill_px","qty","wait_ms","slippage_bps_vs_mid"]
        )

        self.metrics_log = CSVLogger(
            str(self.paths.file(config.SYMBOL, config.FILES["metrics"])),
            [
                "ts_ms",
                "placed","filled","canceled",
                "fill_rate","cancel_rate",
                "avg_wait_ms","avg_slippage_bps","avg_markout_bps"
            ]
        )

        # ---------- metrics ----------
        self.metrics = ExecutionMetrics(markout_horizon_ms=5000)

        # ---------- risk ----------
        self.guard = RiskGuard(self.alerts_log)

        # ---------- permission ----------
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

        # ---------- health ----------
        self.hcfg = HealthConfig(
            spread_unstable=config.SPREAD_UNSTABLE,
            lat_unstable_ms=config.LAT_UNSTABLE_MS,
        )

        # ---------- execution engine ----------
        self.oe = SingleOrderEngine(
            actions_logger=self.exec_actions_log,
            fills_logger=self.fills_log,
            orders_logger=self.orders_log,
            metrics=self.metrics,
            base_qty=0.001
        )

        self._ws = None
        self._last_msg_ms = None


    # ======================================================
    # TRADE HANDLER
    # ======================================================

    def _handle_trade(self, payload, recv_ts):

        exch_ts = int(payload.get("E"))
        price = float(payload.get("p"))
        qty = float(payload.get("q"))
        is_buyer_maker = bool(payload.get("m"))

        latency = recv_ts - exch_ts

        with self._lock:
            self.ms.trades_10s.append(
                (recv_ts, exch_ts, latency, price, qty, is_buyer_maker)
            )
            self.ms.prune_trades(recv_ts)

        if config.LOG_TRADES:
            self.trades_log.write({
                "exch_ts": exch_ts,
                "recv_ts": recv_ts,
                "latency_ms": latency,
                "price": price,
                "qty": qty,
                "is_buyer_maker": is_buyer_maker
            })

        if latency > config.LAT_UNSTABLE_MS:
            self.guard.alert(
                "WARN",
                "LAT_SPIKE",
                f"trade latency spike: {latency}ms",
                {"price": price}
            )


    # ======================================================
    # BBO HANDLER
    # ======================================================

    def _handle_bbo(self, payload, recv_ts):

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

        if config.LOG_BBO:
            self.bbo_log.write({
                "recv_ts": recv_ts,
                "bid_px": bid_px,
                "bid_sz": bid_sz,
                "ask_px": ask_px,
                "ask_sz": ask_sz,
                "spread": "" if spread is None else spread,
                "mid": "" if mid is None else mid
            })

        # ---- metrics markout tracking ----
        if mid is not None:
            self.metrics.on_mid_update(mid)

        # ---- feed execution engine ----
        self.oe.on_bbo(recv_ts, bid_px, ask_px)


    # ======================================================
    # WS CALLBACKS
    # ======================================================

    def _on_open(self, ws):
        print("[WS] OPEN")
        self._last_msg_ms = now_ms()

    def _on_close(self, ws, *args):
        print("[WS] CLOSED")

    def _on_error(self, ws, error):
        print("[WS] ERROR:", error)

    def _on_message(self, ws, message):

        recv_ts = now_ms()
        self._last_msg_ms = recv_ts

        try:
            msg = json.loads(message)
        except:
            return

        data = msg.get("data", {})
        etype = data.get("e")

        if etype == "trade":
            self._handle_trade(data, recv_ts)

        elif "b" in data and "a" in data:
            self._handle_bbo(data, recv_ts)


    # ======================================================
    # PRINTER (CORE BRAIN LOOP)
    # ======================================================

    def _printer(self):

        while not self._stop:

            time.sleep(config.PRINT_EVERY_SEC)
            ts = now_ms()

            with self._lock:
                regime, metrics = detect_regime(self.ms)

            self.perm.update(regime, metrics)

            score, mode, max_aggr, _ = health_score(metrics, self.hcfg)

            dec = safety_decision(
                perm_state=self.perm.state,
                can_trade=self.perm.can_trade(),
                health_score=score,
                health_mode=mode,
                health_aggr=max_aggr
            )

            # ---- log regime ----
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

            # ---- feed execution engine ----
            ed = ExecDecision(
                allowed=bool(dec.allowed),
                max_aggr=str(dec.max_aggr),
                risk_budget=float(dec.risk_budget)
            )

            self.oe.on_decision(ed, ts_ms=ts)

            # ---- metrics snapshot ----
            m = self.metrics.snapshot()

            print(
                f"[REGIME] {regime} | "
                f"[PERM] {self.perm.state}({int(self.perm.can_trade())}) | "
                f"[HEALTH] {score} {mode} {max_aggr} | "
                f"[DECISION] {int(dec.allowed)} {dec.max_aggr} budget={dec.risk_budget}"
            )

            print("[METRICS]", m)

            self.metrics_log.write({
                "ts_ms": ts,
                **m
            })


    # ======================================================
    # START
    # ======================================================
    def start(self):

        url = stream_url()
        print("[BOOT] Connecting:", url)

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
