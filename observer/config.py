# observer/config.py

# ==============================
# Market / WS
# ==============================
SYMBOL = "ethbtc"  # Use lowercase (stream builder will also .lower())
WS_BASE = "wss://stream.binance.com:9443/ws"

# ==============================
# Output files (filenames only)
# NOTE: Directories are handled by observer/paths.py (symbol scoped)
# ==============================
FILES = {
    "trades": "trades.csv",
    "bbo": "bbo.csv",
    "regime": "regime.csv",
    "alerts": "alerts.csv",
    "orders": "orders.csv",
    "fills": "fills.csv",
}

# ==============================
# Observer cadence
# ==============================
PRINT_EVERY_SEC = 10

# ==============================
# Regime detection (observer/regime.py)
# ==============================
# UNSTABLE triggers (hard conditions)
SPREAD_UNSTABLE = 0.5           # Absolute spread; OK for majors. (For alts use bps later.)
LAT_UNSTABLE_MS = 2500          # p95 latency threshold (ms)

# FAST triggers (soft market-speed conditions)
FAST_TRADES_PER_10S = 120       # If trades_10s >= this -> FAST

# FAST_MID_DELTA_10S MUST MATCH your MarketState.mid_delta_10s() unit.
# - If mid_delta_10s() returns absolute price change: set like 25.0 for BTC, 0.00005 for ETHBTC, etc.
# - If mid_delta_10s() returns returns/ratio: set like 0.002 for 20 bps (0.2%).
FAST_MID_DELTA_10S = 0.00005

# ==============================
# Permission Engine (permission/permission.py)
# ==============================
PERM_UNSTABLE_PERSIST_MS = 3000
PERM_WIDE_SPREAD_PERSIST_MS = 1500

PERM_LAT_SPIKE_MS = LAT_UNSTABLE_MS
PERM_LAT_SPIKE_CONSEC = 2

PERM_COOLDOWN_MS = 60_000
PERM_PROBATION_MS = 30_000
