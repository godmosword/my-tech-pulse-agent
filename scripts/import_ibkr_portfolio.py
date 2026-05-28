#!/usr/bin/env python3
"""Import IBKR Flex Query OpenPositions into config/portfolio.yaml (positions + as_of only)."""

from __future__ import annotations

import argparse
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sources.portfolio import PORTFOLIO_PATH, Portfolio  # noqa: E402

FLEX_BASE = "https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService"
POLL_INTERVAL_SEC = 2.0
POLL_MAX_ATTEMPTS = 30


def _flex_send_request(token: str, query_id: str) -> str:
    url = f"{FLEX_BASE}.SendRequest"
    params = {"t": token, "q": query_id, "v": "3"}
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
    root = ET.fromstring(resp.text)
    status = (root.findtext("Status") or root.findtext(".//Status") or "").strip()
    if status and status.lower() not in ("success", "warn"):
        raise RuntimeError(f"Flex SendRequest failed: status={status!r} body={resp.text[:500]}")
    ref = (root.findtext("ReferenceCode") or root.findtext(".//ReferenceCode") or "").strip()
    if not ref:
        raise RuntimeError(f"Flex SendRequest missing ReferenceCode: {resp.text[:500]}")
    return ref


def _flex_get_statement(token: str, reference_code: str) -> str:
    url = f"{FLEX_BASE}.GetStatement"
    params = {"t": token, "q": reference_code, "v": "3"}
    with httpx.Client(timeout=120.0) as client:
        for attempt in range(POLL_MAX_ATTEMPTS):
            resp = client.get(url, params=params)
            resp.raise_for_status()
            text = resp.text
            if "<Status>Success</Status>" in text or "<FlexStatements" in text:
                if "Statement generation in progress" not in text:
                    return text
            if "Statement generation in progress" in text:
                time.sleep(POLL_INTERVAL_SEC)
                continue
            # Some responses return data without explicit Success wrapper.
            if "<OpenPosition" in text or "<OpenPositions" in text:
                return text
            time.sleep(POLL_INTERVAL_SEC)
    raise RuntimeError("Flex GetStatement timed out waiting for statement")


def parse_open_positions(xml_text: str) -> list[dict]:
    """Parse Flex XML OpenPosition rows into {ticker, shares, avg_cost}."""
    root = ET.fromstring(xml_text)
    rows: list[dict] = []
    for node in root.iter():
        tag = node.tag.split("}")[-1] if "}" in node.tag else node.tag
        if tag != "OpenPosition":
            continue
        symbol = (node.attrib.get("symbol") or node.findtext("symbol") or "").strip().upper()
        if not symbol:
            continue
        pos_raw = node.attrib.get("position") or node.findtext("position")
        if pos_raw is None:
            continue
        try:
            shares = float(pos_raw)
        except ValueError:
            continue
        if shares == 0:
            continue
        cost_raw = node.attrib.get("costBasisPrice") or node.findtext("costBasisPrice")
        avg_cost = None
        if cost_raw not in (None, ""):
            try:
                avg_cost = float(cost_raw)
            except ValueError:
                avg_cost = None
        rows.append({"ticker": symbol, "shares": shares, "avg_cost": avg_cost})
    return _aggregate_positions(rows)


def _aggregate_positions(rows: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for row in rows:
        t = row["ticker"]
        shares = float(row["shares"])
        cost = row.get("avg_cost")
        if t not in merged:
            merged[t] = {"ticker": t, "shares": 0.0, "cost_sum": 0.0, "has_cost": False}
        merged[t]["shares"] += shares
        if cost is not None:
            merged[t]["cost_sum"] += shares * float(cost)
            merged[t]["has_cost"] = True
    out: list[dict] = []
    for t in sorted(merged):
        m = merged[t]
        avg = round(m["cost_sum"] / m["shares"], 4) if m["has_cost"] and m["shares"] else None
        out.append({"ticker": t, "shares": m["shares"], "avg_cost": avg})
    return out


def build_yaml_payload(positions: list[dict], existing: Portfolio) -> dict:
    from datetime import date

    return {
        "base_currency": existing.base_currency or "USD",
        "as_of": date.today().isoformat(),
        "positions": [
            {
                "ticker": p["ticker"],
                "shares": p["shares"],
                **({"avg_cost": p["avg_cost"]} if p.get("avg_cost") is not None else {}),
            }
            for p in positions
        ],
        "target_allocation": existing.target_allocation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Import IBKR Flex OpenPositions → portfolio.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Print YAML only; do not write file")
    parser.add_argument("--output", type=Path, default=PORTFOLIO_PATH)
    args = parser.parse_args()

    token = os.environ.get("IBKR_FLEX_TOKEN", "").strip()
    query_id = os.environ.get("IBKR_FLEX_QUERY_ID", "").strip()
    if not token or not query_id:
        print(
            "Error: set IBKR_FLEX_TOKEN and IBKR_FLEX_QUERY_ID environment variables.",
            file=sys.stderr,
        )
        return 1

    existing = Portfolio.load(args.output)
    try:
        ref = _flex_send_request(token, query_id)
        xml_text = _flex_get_statement(token, ref)
        positions = parse_open_positions(xml_text)
    except Exception as exc:
        print(f"Error: IBKR Flex import failed: {exc}", file=sys.stderr)
        return 1

    if not positions:
        print("Error: no OpenPosition rows parsed from Flex statement.", file=sys.stderr)
        return 1

    payload = build_yaml_payload(positions, existing)
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)

    if args.dry_run:
        print(text)
        return 0

    args.output.write_text(text, encoding="utf-8")
    print(f"Wrote {len(positions)} positions to {args.output} (target_allocation preserved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
