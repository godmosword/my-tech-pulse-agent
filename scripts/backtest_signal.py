#!/usr/bin/env python3
"""CLI: point-in-time signal backtest → CSV, JSON summary, Markdown report."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

from backtest.metrics import evaluate, forward_return
from backtest.replay import replay_universe
from sources.finnhub_provider import FinnhubProvider
from sources.sec_xbrl_fetcher import SecXbrlFetcher
from sources.watchlist import EarningsWatchlist

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "backtest" / "results"

KNOWN_LIMITATIONS = """## 已知限制

- **Point-in-time 近似**：XBRL `companyfacts` 以每筆 entry 的 `filed` 日期截斷；SEC 修正檔（10-Q/A、10-K/A）在 filing 當日可能尚未全部入庫，與真實投研環境仍有落差。
- **無 FMP 歷史 ratios**：回測 v1 不載入 point-in-time 估值/品質比率，`quality` 因子多數為 unavailable。
- **無歷史 consensus**：缺少 filing 當日可得的 analyst estimates，`surprise` 因子在回測中通常 unavailable。
- **market_confirmation 停用**：回測刻意排除使用財報後價格的市場確認因子，避免「用未來價格預測未來報酬」的循環洩漏；主要檢驗基本面動能等因子。
- **決策日**：預設為 SEC `filed` 日後首個有報價的交易日；未建模盤後財報的細部 session 時點。
- **樣本數**：半導體 watchlist × 2022 迄今季度數有限；任何 rating 桶 n<20 僅供參考，非統計顯著。
- **非績效保證**：回測結果不代表未來報酬；live `decision_log.jsonl` 才是上線後真實前向校驗來源。
"""


def _parse_horizons(raw: str) -> tuple[int, ...]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return tuple(int(p) for p in parts)


def _write_records_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row:
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            flat = dict(row)
            if "returns" in flat and isinstance(flat["returns"], dict):
                for rk, rv in flat["returns"].items():
                    flat[rk] = rv
                del flat["returns"]
            if "factor_scores" in flat and isinstance(flat["factor_scores"], dict):
                for fk, fv in flat["factor_scores"].items():
                    flat[f"factor_{fk}"] = fv
                del flat["factor_scores"]
            flat.pop("factors", None)
            w.writerow(flat)


def _render_report_md(summary: dict, *, horizons: tuple[int, ...], n_records: int) -> str:
    lines = [
        "# Signal 回測報告",
        "",
        f"生成日：{date.today().isoformat()}",
        f"樣本數：{n_records} 筆（季 × 標的）",
        "",
        KNOWN_LIMITATIONS.strip(),
        "",
    ]

    warnings = summary.get("sample_warnings") or []
    if warnings:
        lines.append("## ⚠ 樣本不足警告")
        lines.append("")
        lines.append("**樣本不足，回測僅供參考，非未來績效保證。**")
        lines.append("")
        for w in warnings:
            lines.append(
                f"- horizon {w.get('horizon_days')}d · {w.get('rating')} · n={w.get('n')} "
                f"(需 ≥{w.get('min_required')})"
            )
        lines.append("")

    lines.append("## 分組超額報酬（vs SOXX）")
    lines.append("")
    for h in horizons:
        lines.append(f"### {h} 交易日")
        lines.append("")
        lines.append("| 評級 | n | 平均超額% | 勝率 |")
        lines.append("| --- | ---: | ---: | ---: |")
        bucket = (summary.get("by_rating") or {}).get(str(h), {})
        for rating, stats in bucket.items():
            n = stats.get("n", 0)
            flag = " ⚠" if stats.get("insufficient_sample") else ""
            mean_e = stats.get("mean_excess_pct")
            wr = stats.get("win_rate")
            lines.append(
                f"| {rating}{flag} | {n} | "
                f"{mean_e if mean_e is not None else '—'} | "
                f"{wr if wr is not None else '—'} |"
            )
        lines.append("")

    lines.append("## IC（Spearman：score vs 超額報酬）")
    lines.append("")
    lines.append("| Horizon | n | IC |")
    lines.append("| --- | ---: | ---: |")
    for h in horizons:
        ic_block = (summary.get("ic") or {}).get(str(h), {})
        lines.append(
            f"| {h}d | {ic_block.get('n', 0)} | {ic_block.get('spearman', '—')} |"
        )
    lines.append("")

    lines.append("## 分位數價差（top tertile − bottom tertile 超額%）")
    lines.append("")
    lines.append("| Horizon | spread% | n |")
    lines.append("| --- | ---: | ---: |")
    for h in horizons:
        q = (summary.get("quantile_spread") or {}).get(str(h), {})
        lines.append(f"| {h}d | {q.get('spread_pct', '—')} | {q.get('n', 0)} |")
    lines.append("")

    lines.append("## Hit rate（看多且超額>0 / 看空且超額<0）")
    lines.append("")
    for h in horizons:
        hr = (summary.get("hit_rate") or {}).get(str(h), {})
        lines.append(f"- **{h}d**：{hr.get('rate', '—')} (n={hr.get('n', 0)})")
    lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Point-in-time investment signal backtest")
    parser.add_argument("--since", default="2022-01-01", help="Earliest filing date (YYYY-MM-DD)")
    parser.add_argument("--horizons", default="5,20,60", help="Forward return horizons (trading days)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output directory")
    parser.add_argument("--tickers", default="", help="Comma-separated ticker subset")
    parser.add_argument("--dry-run", action="store_true", help="Run 2–3 tickers only")
    parser.add_argument("--bench", default="SOXX", help="Benchmark symbol")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    horizons = _parse_horizons(args.horizons)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    watchlist = EarningsWatchlist.load()
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    elif args.dry_run:
        tickers = ["NVDA", "AMD", "AVGO"]
    else:
        tickers = watchlist.tickers()

    api_key = os.getenv("FINNHUB_API_KEY", "")
    if not api_key:
        logging.error("FINNHUB_API_KEY required for forward returns")
        return 1

    finnhub = FinnhubProvider(api_key)
    xbrl = SecXbrlFetcher()

    logging.info("Replay %d tickers since %s (dry_run=%s)", len(tickers), args.since, args.dry_run)
    records = replay_universe(tickers=tickers, since=args.since, finnhub=finnhub, xbrl=xbrl)

    for row in records:
        decision = row.get("decision_date")
        if not decision:
            continue
        returns: dict[str, float | None] = {}
        for h in horizons:
            fr = forward_return(
                finnhub,
                row["symbol"],
                decision_date=decision,
                horizon_days=h,
                bench=args.bench,
            )
            returns[f"return_{h}d"] = fr.get("return_pct")
            returns[f"bench_return_{h}d"] = fr.get("bench_return_pct")
            returns[f"excess_{h}d"] = fr.get("excess_return_pct")
        row["returns"] = returns

    summary = evaluate(records, horizons=horizons)

    records_path = out_dir / "records.csv"
    summary_path = out_dir / "summary.json"
    report_path = out_dir / "report.md"

    _write_records_csv(records_path, records)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(
        _render_report_md(summary, horizons=horizons, n_records=len(records)),
        encoding="utf-8",
    )

    logging.info("Wrote %s (%d rows)", records_path, len(records))
    logging.info("Wrote %s", summary_path)
    logging.info("Wrote %s", report_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
