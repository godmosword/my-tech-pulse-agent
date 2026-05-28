"""Post-earnings price reaction vs benchmark (Finnhub candles, zero LLM cost)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from agents.earnings_v3_models import PriceReaction



def _series_from_candle(candle: dict[str, Any]) -> list[tuple[str, float]]:
    ts_list = candle.get("t") or []
    closes = candle.get("c") or []
    out: list[tuple[str, float]] = []
    for ts, close in zip(ts_list, closes, strict=False):
        try:
            day = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
            out.append((day, float(close)))
        except (TypeError, ValueError, OSError):
            continue
    return sorted(out, key=lambda x: x[0])


def _ret_pct(ref: float | None, later: float | None) -> float | None:
    if ref is None or later is None or ref == 0:
        return None
    return round(((later - ref) / abs(ref)) * 100.0, 2)


def _ref_index(
    series: list[tuple[str, float]],
    earnings_date: str,
    session: str,
) -> tuple[int | None, list[str]]:
    notes: list[str] = []
    dates = [d for d, _ in series]
    if earnings_date not in dates and session in ("post", "unknown"):
        le = [i for i, d in enumerate(dates) if d <= earnings_date]
        if le:
            notes.append(f"ref_close 採 {dates[le[-1]]}（最接近財報日收盤）")
            return le[-1], notes
    if session == "pre":
        prior = [i for i, d in enumerate(dates) if d < earnings_date]
        if prior:
            return prior[-1], notes
        return None, notes
    exact = [i for i, d in enumerate(dates) if d == earnings_date]
    if exact:
        return exact[-1], notes
    le = [i for i, d in enumerate(dates) if d <= earnings_date]
    if le:
        if session == "unknown":
            notes.append("session 未知，採 post 假設（財報日收盤為基準）")
        return le[-1], notes
    return None, notes


def _returns_from_series(
    series: list[tuple[str, float]],
    earnings_date: str,
    session: str,
) -> tuple[float | None, float | None, float | None, list[str]]:
    notes: list[str] = []
    if not series:
        return None, None, None, notes
    ref_idx, ref_notes = _ref_index(series, earnings_date, session)
    notes.extend(ref_notes)
    if ref_idx is None:
        return None, None, None, notes
    ref_close = series[ref_idx][1]
    close_1d = series[ref_idx + 1][1] if ref_idx + 1 < len(series) else None
    close_5d = series[ref_idx + 5][1] if ref_idx + 5 < len(series) else None
    return ref_close, _ret_pct(ref_close, close_1d), _ret_pct(ref_close, close_5d), notes


def _verdict_side(headline_verdict: str | None) -> str | None:
    if headline_verdict == "雙擊":
        return "beat"
    if headline_verdict == "雙殺":
        return "miss"
    return None


def _reaction_label(
    side: str | None,
    excess_1d: float | None,
    *,
    degraded: bool,
) -> str:
    if excess_1d is None:
        return "資料不足"
    if side == "beat":
        return "確認上漲" if excess_1d > 0 else "利多不漲"
    if side == "miss":
        return "利空出盡" if excess_1d > 0 else "確認下跌"
    if degraded:
        return "資料不足"
    if excess_1d > 0 or excess_1d < 0:
        return "中性"
    return "資料不足"


def build_price_reaction(
    finnhub: Any,
    symbol: str,
    *,
    earnings_date: str | None,
    session: str,
    headline_verdict: str | None,
    bench_symbol: str = "SOXX",
) -> PriceReaction:
    notes: list[str] = []
    degraded = False
    session_norm = (session or "unknown").lower()
    if session_norm not in ("pre", "post", "unknown"):
        session_norm = "unknown"

    if not earnings_date:
        return PriceReaction(
            session=session_norm,
            reaction_label="資料不足",
            degraded=True,
            notes=["缺少 earnings_date"],
        )

    ed = earnings_date[:10]
    stock_candle = finnhub.candle(symbol, around=ed) if finnhub else None
    bench_candle = (
        finnhub.candle(bench_symbol, around=ed) if finnhub else None
    )

    ref_close = ret_1d = ret_5d = None
    bench_1d = bench_5d = None

    if stock_candle:
        stock_series = _series_from_candle(stock_candle)
        ref_close, ret_1d, ret_5d, stock_notes = _returns_from_series(
            stock_series, ed, session_norm
        )
        notes.extend(stock_notes)
        if ref_close is None:
            degraded = True
            notes.append("無法取得基準收盤")
    else:
        degraded = True
        notes.append("個股 candle 不可用")

    if bench_candle:
        bench_series = _series_from_candle(bench_candle)
        _, bench_1d, bench_5d, bench_notes = _returns_from_series(
            bench_series, ed, session_norm
        )
        notes.extend([f"SOXX: {n}" for n in bench_notes if n])
    else:
        degraded = True
        notes.append(f"{bench_symbol} candle 不可用")

    excess_1d = (
        round(ret_1d - bench_1d, 2)
        if ret_1d is not None and bench_1d is not None
        else None
    )
    excess_5d = (
        round(ret_5d - bench_5d, 2)
        if ret_5d is not None and bench_5d is not None
        else None
    )

    if stock_candle is None and finnhub:
        q = finnhub.quote(symbol)
        price = _float_or_none(q.get("c") if isinstance(q, dict) else None)
        if price is not None and ref_close is not None:
            ret_5d = _ret_pct(ref_close, price)
            notes.append("candle 缺失，5d 報酬以 quote 現價近似")
            degraded = True
        elif price is not None:
            notes.append("candle 缺失，僅取得 quote 現價，無法計算完整報酬")
            degraded = True

    side = _verdict_side(headline_verdict)
    label = _reaction_label(side, excess_1d, degraded=degraded)

    return PriceReaction(
        earnings_date=ed,
        session=session_norm,
        ref_close=ref_close,
        ret_1d_pct=ret_1d,
        ret_5d_pct=ret_5d,
        bench_symbol=bench_symbol,
        bench_ret_1d_pct=bench_1d,
        bench_ret_5d_pct=bench_5d,
        excess_1d_pct=excess_1d,
        excess_5d_pct=excess_5d,
        reaction_label=label,  # type: ignore[arg-type]
        degraded=degraded,
        notes=notes,
    )


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None