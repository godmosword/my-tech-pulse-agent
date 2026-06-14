"""Read-only coverage audit for config/earnings_watchlist.yaml.

Reports per-tier counts, duplicate/conflict tickers, tag distribution, and —
when an observed-ticker source is supplied — candidate tickers that appear in
real data but are missing from the watchlist. Never invents tickers and never
mutates the watchlist; output is for human review only.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import yaml

from sources.watchlist import WATCHLIST_PATH


def load_raw_entries(path: Path = WATCHLIST_PATH) -> list[dict[str, Any]]:
    """Load watchlist entries preserving duplicates (unlike EarningsWatchlist)."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    out: list[dict[str, Any]] = []
    for row in data.get("entries") or []:
        ticker = str(row.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        out.append(
            {
                "ticker": ticker,
                "tier": int(row.get("tier", 99)),
                "tags": [str(t) for t in (row.get("tags") or [])],
            }
        )
    return out


def find_duplicates(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Classify duplicate tickers into same-tier repeats vs cross-tier conflicts."""
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        by_ticker.setdefault(e["ticker"], []).append(e)

    same_tier: list[dict[str, Any]] = []
    tier_conflict: list[dict[str, Any]] = []
    for ticker, rows in sorted(by_ticker.items()):
        if len(rows) < 2:
            continue
        tiers = sorted(r["tier"] for r in rows)
        record = {"ticker": ticker, "tiers": tiers}
        if len(set(tiers)) > 1:
            tier_conflict.append(record)
        else:
            same_tier.append(record)
    return {"same_tier": same_tier, "tier_conflict": tier_conflict}


def coverage_report(
    entries: list[dict[str, Any]],
    observed: Iterable[str] | None = None,
    targets: dict[int, int] | None = None,
) -> dict[str, Any]:
    """Build a read-only coverage report. observed/targets are optional inputs."""
    tier_counts = Counter(e["tier"] for e in entries)
    tag_counts = Counter(tag for e in entries for tag in e["tags"])
    wl_tickers = {e["ticker"] for e in entries}

    report: dict[str, Any] = {
        "total": len(entries),
        "unique_tickers": len(wl_tickers),
        "tier_counts": dict(sorted(tier_counts.items())),
        "tag_counts": dict(sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "duplicates": find_duplicates(entries),
        "out_of_range_tiers": sorted({t for t in tier_counts if not 1 <= t <= 5}),
    }

    if targets:
        gaps: dict[int, dict[str, int]] = {}
        for tier, target in targets.items():
            tier_i = int(tier)
            current = tier_counts.get(tier_i, 0)
            gaps[tier_i] = {
                "target": int(target),
                "current": current,
                "gap": max(0, int(target) - current),
            }
        report["tier_gaps"] = dict(sorted(gaps.items()))

    if observed is not None:
        candidates = sorted({str(t).strip().upper() for t in observed if str(t).strip()} - wl_tickers)
        report["candidates"] = candidates
        report["candidate_count"] = len(candidates)

    return report


def load_observed(path: Path) -> list[str]:
    """Load observed tickers from CSV (ticker/symbol column) or JSON.

    JSON accepts: ["NVDA", ...], [{"ticker": "NVDA"}, ...], or {"items": [...]}.
    Raises ValueError with the accepted formats on malformed input.
    """
    text = Path(path).read_text(encoding="utf-8")
    suffix = Path(path).suffix.lower()

    if suffix == ".json":
        data = json.loads(text)
        rows: Iterable[Any]
        if isinstance(data, dict):
            rows = data.get("items", [])
        elif isinstance(data, list):
            rows = data
        else:
            raise ValueError(
                'observed JSON must be ["NVDA"], [{"ticker": "NVDA"}], or {"items": [...]}'
            )
        out: list[str] = []
        for row in rows:
            if isinstance(row, str):
                ticker = row
            elif isinstance(row, dict):
                ticker = str(row.get("ticker") or row.get("symbol") or "")
            else:
                raise ValueError("observed JSON items must be strings or objects with ticker/symbol")
            ticker = ticker.strip().upper()
            if ticker:
                out.append(ticker)
        return out

    # CSV path
    out_csv: list[str] = []
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise ValueError("observed CSV must have a header row with a 'ticker' or 'symbol' column")
    field = next(
        (f for f in reader.fieldnames if f and f.strip().lower() in ("ticker", "symbol")),
        None,
    )
    if field is None:
        raise ValueError("observed CSV must contain a 'ticker' or 'symbol' column")
    for row in reader:
        ticker = str(row.get(field) or "").strip().upper()
        if ticker:
            out_csv.append(ticker)
    return out_csv


def load_targets(path: Path) -> dict[int, int]:
    """Load per-tier targets from JSON: {"3": 10, "5": 10}."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError('targets JSON must be an object like {"3": 10, "5": 10}')
    out: dict[int, int] = {}
    for tier, target in data.items():
        out[int(tier)] = int(target)
    return out


def format_report_md(report: dict[str, Any]) -> str:
    """Render the coverage report as Markdown for human review."""
    lines: list[str] = ["# Watchlist 覆蓋稽核", ""]
    lines.append(f"- 總筆數：{report['total']}（唯一 ticker {report['unique_tickers']}）")

    lines.append("")
    lines.append("## 各 Tier 筆數")
    for tier, count in report["tier_counts"].items():
        lines.append(f"- Tier {tier}: {count}")

    gaps = report.get("tier_gaps")
    if gaps:
        lines.append("")
        lines.append("## Tier 目標缺口")
        for tier, g in gaps.items():
            lines.append(f"- Tier {tier}: {g['current']}/{g['target']}（缺 {g['gap']}）")

    dup = report["duplicates"]
    if dup["tier_conflict"] or dup["same_tier"]:
        lines.append("")
        lines.append("## 重複 / 衝突")
        for d in dup["tier_conflict"]:
            lines.append(f"- ⚠️ 跨 tier 衝突：{d['ticker']} 出現於 tier {d['tiers']}")
        for d in dup["same_tier"]:
            lines.append(f"- 同 tier 重複：{d['ticker']}（tier {d['tiers']}）")

    if report["out_of_range_tiers"]:
        lines.append("")
        lines.append(f"## 異常 tier 值：{report['out_of_range_tiers']}")

    if "candidates" in report:
        lines.append("")
        lines.append(f"## 候選（觀測到但不在 watchlist，共 {report['candidate_count']}）")
        lines.append("> 僅供人工確認，不自動加入。")
        for ticker in report["candidates"]:
            lines.append(f"- {ticker}")

    return "\n".join(lines) + "\n"
