#!/usr/bin/env python3
"""Seed config/company_aliases.yaml from earnings watchlist tickers."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sources.watchlist import EarningsWatchlist  # noqa: E402

OUT = ROOT / "config" / "company_aliases.yaml"

# Common SEC / market names beyond bare tickers.
_EXTRA_NAMES: dict[str, list[str]] = {
    "NVDA": ["NVIDIA", "NVIDIA Corporation"],
    "TSM": ["Taiwan Semiconductor", "TSMC", "Taiwan Semiconductor Manufacturing"],
    "AMD": ["Advanced Micro Devices"],
    "AVGO": ["Broadcom", "Broadcom Inc."],
    "INTC": ["Intel", "Intel Corporation"],
    "MSFT": ["Microsoft", "Microsoft Corporation"],
    "GOOGL": ["Alphabet", "Google"],
    "META": ["Meta", "Meta Platforms"],
    "AMZN": ["Amazon", "Amazon.com"],
    "AAPL": ["Apple", "Apple Inc."],
    "AMAT": ["Applied Materials"],
    "LRCX": ["Lam Research"],
    "KLAC": ["KLA"],
    "MU": ["Micron"],
    "MRVL": ["Marvell"],
    "QCOM": ["Qualcomm"],
}


def main() -> int:
    wl = EarningsWatchlist.load()
    aliases: dict[str, str | None] = {}

    existing: dict[str, str | None] = {}
    if OUT.is_file():
        with open(OUT, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for name, ticker in (data.get("aliases") or {}).items():
            existing[str(name)] = ticker

    aliases.update(existing)

    for ticker in wl.tickers():
        aliases[ticker] = ticker
        for name in _EXTRA_NAMES.get(ticker, []):
            aliases[name] = ticker

    OUT.write_text(
        yaml.safe_dump({"aliases": aliases}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"Wrote {len(aliases)} alias entries to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
