#!/usr/bin/env python3
"""Assemble the position-aware decision brief into a dashboard artifact.

Reads recent delivered memory items (with their P1 portfolio_impact), the
portfolio (thesis/watch), upcoming catalysts, the Phase-0 evidence level, and any
graded decision records, then writes backtest/results/invest_brief.json. Posture
and its cross-run cooldown are resolved here (see scoring.invest_brief), so the
dashboard renders one authoritative brief.

Run after the pipeline (it reads dashboard/data/memory_items.json).

Usage:
  python scripts/build_invest_brief.py --dry-run
  python scripts/build_invest_brief.py
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv()

from scoring.invest_brief import build_invest_brief, load_prev_alerts  # noqa: E402
from sources.catalyst_calendar import upcoming_catalysts  # noqa: E402
from sources.portfolio import Portfolio  # noqa: E402

logger = logging.getLogger(__name__)

RESULTS = ROOT / "backtest" / "results"
OUT = RESULTS / "invest_brief.json"
LOOKBACK_DAYS = 3


def _evidence_level() -> str:
    path = RESULTS / "track_record.json"
    if not path.is_file():
        return "insufficient"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        overall = (
            data.get("track_record", {}).get("by_horizon", {}).get("5", {}).get("overall")
        )
        return str((overall or {}).get("evidence_level") or "insufficient")
    except (json.JSONDecodeError, OSError, AttributeError):
        return "insufficient"


def _graded_records() -> list[dict]:
    path = RESULTS / "graded_records.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _recent_items() -> list[dict]:
    """Best-effort read of recent items + their portfolio_impact from JSON."""
    from scoring.json_io import memory_items_path, parse_iso, read_json_list  # noqa: PLC0415

    since = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    try:
        rows = read_json_list(memory_items_path())
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory_items.json unavailable, brief omits material items: %s", exc)
        return []

    items: list[dict] = []
    for data in rows:
        delivered = parse_iso(data.get("delivered_at"))
        if delivered is not None and delivered < since:
            continue
        impact = data.get("portfolio_impact") or {}
        if not impact:
            continue
        affected = impact.get("affected_positions") or []
        market = data.get("market_context") or {}
        items.append(
            {
                "id": data.get("item_id") or data.get("id") or "",
                "title": data.get("zh_title") or data.get("title") or data.get("entity") or "",
                "impact_score": impact.get("score") or 0.0,
                "affected_tickers": [a.get("ticker") for a in affected if a.get("ticker")],
                "affected_kinds": [a.get("kind") for a in affected if a.get("kind")],
                "market_flags": market.get("flags") or [],
            }
        )
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    portfolio = Portfolio.load()
    positions = [
        (
            p.ticker,
            (p.shares or 0.0) * (p.avg_cost or 0.0),
            p.thesis,
            p.watch,
        )
        for p in portfolio.positions
    ]
    catalysts = upcoming_catalysts(
        as_of=date.today(),
        window_days=14,
        tickers={p.ticker for p in portfolio.positions},
    )

    brief = build_invest_brief(
        items=_recent_items(),
        positions=positions,
        catalysts=catalysts,
        graded_records=_graded_records(),
        evidence_level=_evidence_level(),
        prev_alerts=load_prev_alerts(args.out),
        as_of=date.today(),
    )

    payload = brief.model_dump()
    if args.dry_run:
        logger.info("dry-run brief: %s", json.dumps(payload, ensure_ascii=False)[:600])
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    try:
        from delivery.invest_alert import notify_invest_brief  # noqa: PLC0415

        notify_invest_brief(brief, as_of=date.today())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Invest alert skipped: %s", exc)
    logger.info(
        "Wrote %s (material=%d, flags=%d, catalysts=%d)",
        args.out,
        len(brief.material_items),
        len(brief.portfolio_pulse.risk_flags),
        len(brief.catalyst_watch),
    )


if __name__ == "__main__":
    main()
