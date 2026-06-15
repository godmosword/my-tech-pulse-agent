"""P4 — assemble the full position-aware decision brief (pure, testable).

Single source of truth for the four-part brief the dashboard renders:
  1. portfolio pulse — concentration + correlation/supply-chain risk flags
  2. material moves — today's news ranked by portfolio impact, each with an
     authoritative posture (evidence-softened, cooldown-suppressed)
  3. catalyst watch — upcoming events for held names
  4. thesis updates — supporting/contradicting evidence per holding

Posture and its cross-run cooldown live here (not the news pipeline) so the
dashboard renders one authoritative decision rather than a TS re-derivation.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from scoring.portfolio_impact import (
    CLUSTERS_PATH,
    _load_relationship_counterparties,
)
from scoring.posture import decide_posture
from scoring.thesis_tracker import ThesisEvidence, link_thesis_evidence

COOLDOWN_DAYS = 4
MATERIAL_LIMIT = 6
ALERT_POSTURES = frozenset({"review", "risk_up"})


class RiskFlag(BaseModel):
    kind: str
    severity: str
    tickers: list[str]
    message_zh: str


class Holding(BaseModel):
    ticker: str
    weight: float


class PortfolioPulse(BaseModel):
    top_holdings: list[Holding] = Field(default_factory=list)
    concentration_top_pct: float = 0.0
    risk_flags: list[RiskFlag] = Field(default_factory=list)


class BriefItem(BaseModel):
    id: str
    title: str
    impact_score: float
    posture: str
    label_zh: str
    reason_zh: str
    falsification_zh: str
    next_check: str
    affected_tickers: list[str] = Field(default_factory=list)
    market_flags: list[str] = Field(default_factory=list)


class InvestBrief(BaseModel):
    generated_at: str
    evidence_level: str
    portfolio_pulse: PortfolioPulse
    material_items: list[BriefItem] = Field(default_factory=list)
    catalyst_watch: list[dict[str, Any]] = Field(default_factory=list)
    thesis_updates: list[ThesisEvidence] = Field(default_factory=list)
    alerted_tickers: dict[str, str] = Field(default_factory=dict)


def _load_clusters_with_corr() -> list[tuple[list[str], float]]:
    if not CLUSTERS_PATH.is_file():
        return []
    try:
        data = json.loads(CLUSTERS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    out: list[tuple[list[str], float]] = []
    for cl in data.get("clusters") or []:
        members = [str(m).upper() for m in (cl.get("members") or []) if m]
        if len(members) >= 2:
            out.append((members, float(cl.get("avg_intra_corr") or 0.0)))
    return out


def _portfolio_pulse(positions: list[tuple[str, float, str, list[str]]]) -> PortfolioPulse:
    total = sum(v for _, v, _, _ in positions if v > 0)
    held = {t.upper() for t, v, _, _ in positions if v > 0}
    holdings = (
        sorted(
            (Holding(ticker=t.upper(), weight=round(v / total, 4)) for t, v, _, _ in positions if v > 0),
            key=lambda h: -h.weight,
        )
        if total > 0
        else []
    )
    flags: list[RiskFlag] = []

    for holding in sorted(held):
        for cp in sorted(_load_relationship_counterparties(holding)):
            if cp in held and cp != holding:
                flags.append(
                    RiskFlag(
                        kind="supply_chain",
                        severity="warn",
                        tickers=sorted({holding, cp}),
                        message_zh=f"{holding} 與 {cp} 互為 10-K 供應鏈對手方，雙重曝險",
                    )
                )

    if len(held) >= 2:
        for members, corr in _load_clusters_with_corr():
            overlap = sorted(set(members) & held)
            if len(overlap) >= 2:
                flags.append(
                    RiskFlag(
                        kind="correlation_cluster",
                        severity="warn",
                        tickers=overlap,
                        message_zh=(
                            f"持倉 {'、'.join(overlap)} 落在同一相關性叢集"
                            f"（平均相關 {corr * 100:.0f}%），分散度偏低"
                        ),
                    )
                )

    # De-duplicate supply-chain mirror pairs (A-B and B-A).
    seen: set[tuple[str, tuple[str, ...]]] = set()
    unique: list[RiskFlag] = []
    for f in flags:
        key = (f.kind, tuple(f.tickers))
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)

    return PortfolioPulse(
        top_holdings=holdings[:5],
        concentration_top_pct=holdings[0].weight if holdings else 0.0,
        risk_flags=unique,
    )


def _recent_alert_days(
    affected: list[str], prev_alerts: dict[str, str], as_of: date
) -> Optional[int]:
    best: Optional[int] = None
    for ticker in affected:
        prev = prev_alerts.get(ticker.upper())
        if not prev:
            continue
        try:
            days = (as_of - date.fromisoformat(prev[:10])).days
        except ValueError:
            continue
        best = days if best is None else min(best, days)
    return best


def build_invest_brief(
    *,
    items: list[dict[str, Any]],
    positions: list[tuple[str, float, str, list[str]]],
    catalysts: list[Any],
    graded_records: list[dict[str, Any]],
    evidence_level: str = "insufficient",
    prev_alerts: Optional[dict[str, str]] = None,
    as_of: Optional[date] = None,
) -> InvestBrief:
    """Assemble the brief. `positions` rows = (ticker, value, thesis, watch)."""
    as_of = as_of or datetime.now(timezone.utc).date()
    prev_alerts = prev_alerts or {}

    pulse = _portfolio_pulse(positions)

    ranked = sorted(
        (it for it in items if float(it.get("impact_score") or 0) > 0),
        key=lambda it: -float(it.get("impact_score") or 0),
    )[:MATERIAL_LIMIT]

    material: list[BriefItem] = []
    alerted: dict[str, str] = {}
    for it in ranked:
        affected = [str(a).upper() for a in (it.get("affected_tickers") or [])]
        kinds = set(it.get("affected_kinds") or [])
        impact = float(it.get("impact_score") or 0)
        decision = decide_posture(
            impact_score=impact,
            evidence_level=evidence_level,
            affected_kinds=kinds,
            recent_alert_days=_recent_alert_days(affected, prev_alerts, as_of),
            cooldown_days=COOLDOWN_DAYS,
            as_of=as_of,
        )
        material.append(
            BriefItem(
                id=str(it.get("id") or ""),
                title=str(it.get("title") or ""),
                impact_score=round(impact, 4),
                posture=decision.posture,
                label_zh=decision.label_zh,
                reason_zh=decision.reason_zh,
                falsification_zh=decision.falsification_zh,
                next_check=decision.next_check,
                affected_tickers=affected,
                market_flags=[str(f) for f in (it.get("market_flags") or [])],
            )
        )
        if decision.posture in ALERT_POSTURES and not decision.suppressed_by_cooldown:
            for ticker in affected:
                alerted[ticker] = as_of.isoformat()

    # Carry forward prior alerts still inside the cooldown window.
    for ticker, day in prev_alerts.items():
        try:
            if (as_of - date.fromisoformat(day[:10])).days < COOLDOWN_DAYS:
                alerted.setdefault(ticker, day)
        except ValueError:
            continue

    thesis_updates: list[ThesisEvidence] = []
    for ticker, _value, thesis, _watch in positions:
        if not thesis:
            continue
        thesis_updates.append(
            link_thesis_evidence(
                ticker=ticker,
                thesis=thesis,
                graded_records=graded_records,
                upcoming_catalysts=catalysts,
            )
        )

    catalyst_payload = [
        c.model_dump() if hasattr(c, "model_dump") else dict(c) for c in catalysts
    ]

    return InvestBrief(
        generated_at=as_of.isoformat(),
        evidence_level=evidence_level,
        portfolio_pulse=pulse,
        material_items=material,
        catalyst_watch=catalyst_payload,
        thesis_updates=thesis_updates,
        alerted_tickers=alerted,
    )


def load_prev_alerts(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    alerts = data.get("alerted_tickers") if isinstance(data, dict) else None
    return {str(k).upper(): str(v) for k, v in (alerts or {}).items()}
