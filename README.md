⚠️ Early-stage execution infrastructure under active development.

Market Data
    ↓
State Engine
    ↓
Regime Detection
    ↓
Permission Gate
    ↓
Health Model
    ↓
Decision Layer
    ↓
Execution Engine


# Crypto Execution Lab

Execution-first trading infrastructure designed to study system behavior under live market microstructure — without deploying capital.

This repository focuses on one question:

**How should a trading system behave before it is allowed to trade?**

Prediction is treated as a downstream concern.  
Execution stability is treated as a prerequisite.

---

## System Overview

The architecture transforms raw market data into constrained execution decisions through layered interpretation:

market data → state → regime → permission → health → decision → paper execution

Each layer exists to reduce uncertainty before interacting with liquidity.

The objective is not feature accumulation, but behavioral determinism.

---

## Core Components

**Market Observer**
- Real-time trade and bookTicker ingestion
- Rolling microstructure metrics
- Structured event logging

**Regime Engine**
- Classifies structural market conditions  
  (NORMAL / FAST / UNSTABLE)
- Detects shifts in liquidity and trading intensity rather than forecasting price

**Permission Engine**
- Stateful execution gate
- Cooldown and probation mechanics
- Prevents participation during structurally unstable periods

**Health Model**
- Multi-factor execution safety scoring
- Produces bounded aggressiveness:
  - GREEN → controlled liquidity taking permitted  
  - YELLOW → passive interaction preferred  
  - RED → no participation  

**Decision Layer**
- Converts system state into explicit execution constraints:
  - trade eligibility  
  - aggressiveness ceiling  
  - risk budget  

**Paper Execution Engine**
- Simulated order placement driven by live BBO
- Measures fill behavior, slippage, and execution latency
- Validates infrastructure before capital exposure

**Observability**
- Full lifecycle logging across all layers  
- Designed for replay, diagnosis, and behavioral audit

A system that cannot explain its actions is considered operationally unsafe.

---

## Design Principles

**Determinism over reactivity**  
Improvised behavior is a primary source of execution risk.

**Constraints precede capital**  
Optionality collapses once orders meet liquidity.

**State reduces ambiguity**  
Explicit system state compresses market complexity into actionable structure.

**Execution is an infrastructure problem**  
Strategy defines intent. Infrastructure governs survivability.

**Liquidity is the operating environment**  
Price is a secondary artifact.

---

## Repository Structure
observer/ market ingestion, regime detection, logging
engine/ state modeling and decision logic
permission/ execution gating state machine
health/ execution safety scoring
risk/ guardrails and alerts
execution/ paper order engine


The system is intentionally modular to allow execution behavior to evolve independently from strategy research.

---

## Project Trajectory

The architecture is evolving toward production-grade properties:

- predictable behavior under stress  
- explicit execution boundaries  
- constrained liquidity interaction  
- internal transparency  
- failure-aware design  

Progress is evaluated by behavioral stability rather than feature breadth.

---

## Scope

This repository is an execution research environment.

It does **not** place live trades.
