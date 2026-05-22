#!/usr/bin/env python3
"""Export config/earnings_watchlist.yaml → dashboard/lib/earnings-watchlist-data.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sources.watchlist import EarningsWatchlist  # noqa: E402

OUT = ROOT / "dashboard" / "lib" / "earnings-watchlist-data.json"


def main() -> int:
    wl = EarningsWatchlist.load()
    entries = [
        {"ticker": t, "tier": wl.tier(t), "tags": list(wl.tags(t))}
        for t in wl.tickers()
    ]
    OUT.write_text(
        json.dumps({"entries": entries}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(entries)} entries to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
