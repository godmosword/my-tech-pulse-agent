#!/usr/bin/env python3
"""Export config/portfolio.yaml → dashboard/lib/portfolio-data.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sources.portfolio import Portfolio  # noqa: E402

OUT = ROOT / "dashboard" / "lib" / "portfolio-data.json"


def main() -> int:
    pf = Portfolio.load()
    payload = {
        "base_currency": pf.base_currency,
        "as_of": pf.as_of,
        "positions": [
            {
                "ticker": p.ticker,
                "shares": p.shares,
                "avg_cost": p.avg_cost,
            }
            for p in pf.positions
        ],
        "target_allocation": pf.target_allocation,
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(pf.positions)} positions to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
