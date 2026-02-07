# crypto-execution-lab-v1

crypto-execution-lab is a research-oriented execution infrastructure designed to study how trading systems behave once exposed to real market microstructure.

The objective is not signal generation.  
The objective is execution understanding.

Markets rarely fail because signals are unavailable.  
They fail because interaction with liquidity is poorly understood.

This repository exists to reduce that gap.

---

## Orientation

A trading system is treated here as a controlled machine operating under uncertainty.

Decisions are not isolated outputs of strategy.  
They are consequences of layered interpretation:

# crypto-execution-lab

crypto-execution-lab is a research-oriented execution infrastructure designed to study how trading systems behave once exposed to real market microstructure.

The objective is not signal generation.  
The objective is execution understanding.

Markets rarely fail because signals are unavailable.  
They fail because interaction with liquidity is poorly understood.

This repository exists to reduce that gap.

---

## Orientation

A trading system is treated here as a controlled machine operating under uncertainty.

Decisions are not isolated outputs of strategy.  
They are consequences of layered interpretation:

market perception → state formation → constraint enforcement → execution → measurement

Each layer exists to reduce ambiguity before capital is placed at risk.

Execution, in this context, is less about speed than about behavioral stability.

---

## Design Principles

**State-aware execution**  
Execution decisions should emerge from explicit market state rather than reactive impulses.

**Constraint-first architecture**  
Risk is easier to prevent than to correct. System constraints are applied before orders interact with liquidity.

**Observability over opacity**  
A system that cannot explain its behavior is structurally fragile. Metrics are treated as first-class citizens.

**Liquidity as the operating environment**  
Price is only a surface artifact. Liquidity determines survivability.

**Determinism over improvisation**  
Systems that improvise under stress tend to externalize risk.

---

## System Architecture

The repository follows a layered execution model:

### Observer Layer

Responsible for market ingestion and state construction.

- WebSocket market data
- MarketState modeling
- Regime detection inputs
- Structured logging

### Safety Layer

Constrains execution before orders are allowed to exist.

- Permission engine (state machine)
- Health scoring
- Risk guards
- Decision synthesis

### Execution Layer

Controls the full lifecycle of an order.

- Placement
- Repricing
- Cancellation
- Fill simulation
- Policy-driven aggressiveness

### Metrics Layer

Measures execution quality rather than trading outcome.

- Fill rate  
- Cancel rate  
- Queue wait time  
- Slippage  
- Markout  

The goal is not merely to trade — but to understand *how* trades occur.

---

## Current Scope — Execution Core (v1)

Version 1 focuses on L1-driven execution behavior with passive-first interaction.

**Included capabilities:**

- State-driven execution decisions  
- Permission-based order gating  
- Health-aware aggressiveness  
- Symbol-ready tuning  
- Order lifecycle tracking  
- Markout-based execution quality measurement  

**Intentionally excluded:**

- Alpha generation  
- Strategy optimization  
- Reinforcement learning  
- L2 orderbook modeling  

Complexity is deferred until behavior is understood.

---

## What This Repository Is Not

This is **not**:

- a signal factory  
- a backtesting playground  
- a high-frequency trading system  
- an AI trading experiment  

It is an execution research environment.

---

## Running the System

Output directories can be configured via environment variable:

### PowerShell

```powershell
$env:QUANT_OUT_DIR="D:\execution-data"
python -m observer.run


Each layer exists to reduce ambiguity before capital is placed at risk.

Execution, in this context, is less about speed than about behavioral stability.

---

## Design Principles

**State-aware execution**  
Execution decisions should emerge from explicit market state rather than reactive impulses.

**Constraint-first architecture**  
Risk is easier to prevent than to correct. System constraints are applied before orders interact with liquidity.

**Observability over opacity**  
A system that cannot explain its behavior is structurally fragile. Metrics are treated as first-class citizens.

**Liquidity as the operating environment**  
Price is only a surface artifact. Liquidity determines survivability.

**Determinism over improvisation**  
Systems that improvise under stress tend to externalize risk.

---

## System Architecture

The repository follows a layered execution model:

### Observer Layer
Responsible for market ingestion and state construction.

- WebSocket market data
- MarketState modeling
- Regime detection inputs
- Structured logging

### Safety Layer
Constrains execution before orders are allowed to exist.

- Permission engine (state machine)
- Health scoring
- Risk guards
- Decision synthesis

### Execution Layer
Controls the full lifecycle of an order.

- Placement
- Repricing
- Cancellation
- Fill simulation
- Policy-driven aggressiveness

### Metrics Layer
Measures execution quality rather than trading outcome.

- Fill rate  
- Cancel rate  
- Queue wait time  
- Slippage  
- Markout  

The goal is not merely to trade — but to understand *how* trades occur.

---

## Current Scope — Execution Core (v1)

Version 1 focuses on L1-driven execution behavior with passive-first interaction.

**Included capabilities:**

- State-driven execution decisions  
- Permission-based order gating  
- Health-aware aggressiveness  
- Symbol-ready tuning  
- Order lifecycle tracking  
- Markout-based execution quality measurement  

**Intentionally excluded:**

- Alpha generation  
- Strategy optimization  
- Reinforcement learning  
- L2 orderbook modeling  

Complexity is deferred until behavior is understood.

---

## What This Repository Is Not

This is **not**:

- a signal factory  
- a backtesting playground  
- a high-frequency trading system  
- an AI trading experiment  

It is an execution research environment.

---

## Running the System

Output directories can be configured via environment variable:

### PowerShell
```powershell
$env:QUANT_OUT_DIR="D:\execution-data"
python -m observer.run

### macOS / Linux
```bash
export QUANT_OUT_DIR="/execution-data"
python -m observer.run

```php-template
### Data will be written to:

<OUT_DIR>/symbol=<symbol>/

### Research Workflow

The intended usage pattern is observational:

1.Run the system across markets with different liquidity profiles.

2.Compare execution metrics.

3.Identify behavioral differences.

4.Form hypotheses.

5.Adjust execution parameters.

6.Repeat.

The repository is designed to support long-horizon learning rather than short-term experimentation.

### Design Position

Strategy determines direction.
Infrastructure determines survivability.

In adversarial environments, survivability compounds.

### Status

Execution Core — v1 (Architecture Frozen)

Future evolution will prioritize behavioral research over architectural expansion.
