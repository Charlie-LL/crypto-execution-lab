# observer/paths.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os


def project_root() -> Path:
    """Resolve repo root: <root>/observer/paths.py -> parents[1] is <root>."""
    return Path(__file__).resolve().parents[1]


def ensure_dir(p: Path) -> Path:
    """Create directory if missing."""
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass(frozen=True)
class Paths:
    """
    Filesystem layout helper.
    Uses QUANT_OUT_DIR env var if provided, otherwise defaults to <repo>/data.
    """
    out_dir: Path

    @staticmethod
    def from_env(default_subdir: str = "data") -> "Paths":
        root = project_root()
        env_out = os.getenv("QUANT_OUT_DIR", "").strip()
        out = Path(env_out).expanduser() if env_out else (root / default_subdir)
        out = ensure_dir(out)
        return Paths(out_dir=out)

    def symbol_dir(self, symbol: str) -> Path:
        d = self.out_dir / f"symbol={symbol.lower()}"
        return ensure_dir(d)

    def file(self, symbol: str, filename: str) -> Path:
        return self.symbol_dir(symbol) / filename
