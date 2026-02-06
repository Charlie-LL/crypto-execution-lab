# decision.py
from dataclasses import dataclass

@dataclass
class Decision:
    allowed: bool
    max_aggr: str          # NO_TRADE / PASSIVE_ONLY / LIMIT_OK
    risk_budget: float     # 0.0 - 1.0
    reason: str

def safety_decision(perm_state: str, can_trade: bool,
                    health_score: int, health_mode: str, health_aggr: str) -> Decision:
    """
    Combine Permission + Health into ONE final decision.
    Priority: Permission overrides everything.
    """

    # 1) Permission hard override
    if not can_trade or perm_state in ("BLOCKED", "COOLDOWN"):
        return Decision(
            allowed=False,
            max_aggr="NO_TRADE",
            risk_budget=0.0,
            reason=f"permission={perm_state}"
        )

    # 2) Probation is allowed but conservative
    if perm_state == "PROBATION":
        # even if health is GREEN, cap aggressiveness
        max_aggr = "PASSIVE_ONLY" if health_aggr != "NO_TRADE" else "NO_TRADE"
        budget = 0.25 if max_aggr != "NO_TRADE" else 0.0
        return Decision(
            allowed=(max_aggr != "NO_TRADE"),
            max_aggr=max_aggr,
            risk_budget=budget,
            reason=f"probation + health={health_mode}"
        )

    # 3) ALLOW state: use health to set aggressiveness & budget
    if health_aggr == "NO_TRADE" or health_mode == "RED":
        return Decision(False, "NO_TRADE", 0.0, "health=RED")

    if health_mode == "YELLOW":
        # conservative budget mapping
        # 50->0.25, 75->0.55
        b = 0.25 + (max(50, min(75, health_score)) - 50) * (0.30 / 25.0)
        return Decision(True, "PASSIVE_ONLY", round(b, 3), f"health=YELLOW score={health_score}")

    # GREEN
    # 75->0.60, 95->1.00
    b = 0.60 + (max(75, min(95, health_score)) - 75) * (0.40 / 20.0)
    return Decision(True, "LIMIT_OK", round(b, 3), f"health=GREEN score={health_score}")
