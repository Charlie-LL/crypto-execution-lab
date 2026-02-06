# How Crypto Exchanges Actually Work  

### Microstructure Notes for Execution-Oriented Trading Systems

---

## Introduction

Most retail traders focus on signals.

Institutional trading systems focus on **execution quality**.

Execution is constrained by market microstructure — the mechanics governing how orders interact with liquidity inside an exchange.

This document summarizes the core architecture of centralized crypto exchanges and outlines how these mechanics directly influence trading system design.

The objective is not academic completeness, but **engineering awareness**.

---

## Exchange Architecture

A centralized exchange can be simplified into three primary components:

- Order Book  
- Matching Engine  
- Liquidity Layer  

Understanding these components is foundational for building reliable execution infrastructure.

---

### Order Book — The Topology of Liquidity

The order book is a real-time map of available liquidity.

It contains:

- **Bids** — passive buy orders  
- **Asks** — passive sell orders  

The difference between the best ask and best bid defines the **spread**, representing the immediate cost of aggressive execution.

More importantly, the order book reveals:

- Depth of liquidity  
- Structural support and resistance  
- Fragility of price levels  
- Potential market impact  

Execution systems therefore do not react to price alone — they react to **liquidity topology**.

Price is only the visible outcome of liquidity interactions.

---

### Matching Engine — Deterministic Trade Resolution

The matching engine pairs buyers and sellers according to deterministic rules.

Most centralized exchanges implement **price-time priority**:

1. Better prices execute first  
2. For identical prices, earlier orders execute before later ones  

This rule transforms time into an economic advantage.

Milliseconds — sometimes microseconds — directly influence fill probability.

Speed is not vanity infrastructure.  
It is positional leverage inside the queue.

---

### Liquidity as a Hard Constraint

For institutional execution systems, liquidity is not a background variable.

It is a hard constraint.

Before entering a position, a system must implicitly answer:

> *Can this size be executed without destabilizing the market?*

Execution quality is therefore largely determined by how intelligently a system interacts with available liquidity.

Ignoring liquidity is equivalent to ignoring impact.

---

## Maker vs Taker — The Core Execution Tradeoff

Execution is a continuous optimization between **spread capture** and **immediacy**.

---

### Maker — Providing Liquidity

Maker orders rest in the order book and wait to be matched.

Advantages:

- Capture the bid–ask spread  
- Lower transaction fees (often rebates)  
- Minimal instantaneous price impact  

However, passive execution carries structural risks.

**Fill Risk**  
Orders may remain unexecuted during fast-moving markets.

**Queue Risk**  
Orders at the same price execute sequentially.  
Queue position therefore becomes economically meaningful.

**Adverse Selection**  
If a passive order is filled immediately before price moves against it, the fill itself contains negative information.

Informed flow tends to consume stale liquidity first.

---

### Taker — Consuming Liquidity

Taker orders prioritize certainty over price.

Advantages:

- Immediate execution  
- Faster inventory control  
- Reliable risk reduction during unstable regimes  

Costs include:

- Paying the spread  
- Higher fees  
- Slippage when liquidity is thin  

Aggressive execution is therefore not simply expensive — it is often **risk minimizing**.

---

### Execution Framing

Professional systems do not treat maker and taker as static preferences.

They treat them as **state-dependent execution modes**.

> Maker earns microstructure edge.  
> Taker buys time.

---

## Why Latency Matters

Latency directly determines **queue priority**.

> Queue position is a hidden asset.

Consider a price level offering 100 BTC of liquidity.

If an order is placed behind 80 BTC in the queue, the first 80 BTC of aggressive flow must execute before that order participates.

A slower system is structurally subordinated — regardless of signal quality.

---

### Latency Degrades Decision Quality

Execution decisions are only as reliable as the data they depend on.

Elevated latency introduces:

**Signal Staleness**  
Orders are generated from an outdated view of the order book.

**Slippage Amplification**  
Thin liquidity levels may disappear before aggressive orders arrive.

**Delayed Risk Response**  
During volatility shocks, slower systems typically exit later — and at worse prices.

Speed is not about winning a race.

It is about **avoiding predictable losses**.

---

## Implications for Trading System Design

Understanding microstructure forces a shift from strategy-centric thinking to infrastructure-centric design.

Execution systems should be structured as layered decision engines rather than monolithic scripts.

---

### 1. Market Perception Layer

Real-time streams — trades, spreads, and book updates — form the perception layer.

The objective is not data collection.

It is liquidity awareness.

Key signals include:

- Spread stability  
- Order book thinning  
- Trade aggressor imbalance  
- Short-term volatility expansion  

Price alone is insufficient.

---

### 2. State Representation

Continuous market noise must be translated into discrete states to stabilize behavior.

Example regime mapping:

```
NORMAL  
SPREAD_UNSTABLE  
VOLATILITY_SPIKE  
DATA_DEGRADED  
RISK_OFF  
```

State machines prevent execution from reacting impulsively to transient noise and make system behavior auditable.

---

### 3. Pre-Trade Risk Gate

Risk control is most effective when enforced **before orders reach the market**.

Examples include:

- Disabling aggressive orders during spread expansion  
- Blocking trading when data integrity is compromised  
- Preventing inventory growth during volatility shocks  

Risk should function as a gate — not merely a post-trade diagnostic.

---

### 4. State-Dependent Execution

Execution mode selection must adapt to market conditions.

| Market State | Preferred Behavior |
|------------|------------------|
| Stable liquidity | Lean maker |
| Fragile book | Reduce participation |
| Volatility spike | Favor taker to de-risk |
| Data degradation | Trigger kill switch |

Execution becomes a controlled interaction with liquidity rather than a blind reaction to signals.

---

## Closing Thought

Strategy determines direction.

Microstructure determines survival.

A trading system that ignores liquidity mechanics is not merely incomplete — it is fragile by design.
