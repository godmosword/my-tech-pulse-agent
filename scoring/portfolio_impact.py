"""P1 — score how much a news item matters to the user's actual portfolio.

Converts a generic news summary into "does this change what I should do with my
book?" The impact is a transparent product of components (the brief surfaces
each one), with the strongest relation per held name counted once and
diminishing returns so a single mega-cap story cannot dominate forever.

Pure, read-only, dependency-light: no network, no recompute of upstream signals.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
RELATIONSHIPS_DIR = ROOT / "data" / "relationships"
CLUSTERS_PATH = ROOT / "data" / "clusters.json"
ALIASES_PATH = ROOT / "config" / "company_aliases.yaml"

RelationKind = Literal["direct", "supply_chain", "cluster", "theme"]

# Strongest relation wins; weights express how directly the news touches a holding.
RELATION_WEIGHT: dict[RelationKind, float] = {
    "direct": 1.0,
    "supply_chain": 0.6,
    "cluster": 0.4,
    "theme": 0.25,
}
_RELATION_RANK: dict[RelationKind, int] = {
    "direct": 3,
    "supply_chain": 2,
    "cluster": 1,
    "theme": 0,
}
_CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.7, "low": 0.4}


class AffectedPosition(BaseModel):
    ticker: str
    kind: RelationKind
    note_zh: str


class ImpactComponents(BaseModel):
    relevance: float
    exposure_weight: float
    relation_weight: float
    freshness: float
    confidence: float


class PortfolioImpact(BaseModel):
    score: float
    components: ImpactComponents
    affected_positions: list[AffectedPosition] = Field(default_factory=list)
    exposure_basis: Literal["cost", "market"] = "cost"
    rationale_zh: str = ""


@lru_cache(maxsize=1)
def _load_clusters() -> list[list[str]]:
    if not CLUSTERS_PATH.is_file():
        return []
    try:
        data = json.loads(CLUSTERS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    out: list[list[str]] = []
    for cl in data.get("clusters") or []:
        members = [str(m).upper() for m in (cl.get("members") or []) if m]
        if len(members) >= 2:
            out.append(members)
    return out


@lru_cache(maxsize=128)
def _load_relationship_counterparties(ticker: str) -> frozenset[str]:
    """Counterparty tickers named in a holding's 10-K relationship file."""
    path = RELATIONSHIPS_DIR / f"{ticker.upper()}.json"
    if not path.is_file():
        return frozenset()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return frozenset()
    out = {
        str(e.get("counterparty_ticker") or "").upper()
        for e in (data.get("edges") or [])
        if e.get("counterparty_ticker")
    }
    return frozenset(out - {""})


@lru_cache(maxsize=1)
def _load_aliases() -> dict[str, str]:
    """Lower-cased company alias -> ticker, for entity resolution (best-effort)."""
    if not ALIASES_PATH.is_file():
        return {}
    try:
        import yaml  # noqa: PLC0415

        raw = yaml.safe_load(ALIASES_PATH.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 - optional aux data; never block scoring
        return {}
    out: dict[str, str] = {}
    if isinstance(raw, dict):
        for ticker, aliases in raw.items():
            sym = str(ticker).upper()
            out[sym.lower()] = sym
            for alias in aliases or []:
                out[str(alias).strip().lower()] = sym
    return out


def resolve_tickers(tickers: list[str], entity: str) -> set[str]:
    """Explicit tickers plus any ticker resolved from the entity name via aliases."""
    resolved = {t.strip().upper() for t in tickers if t and t.strip()}
    ent = (entity or "").strip().lower()
    if ent:
        aliases = _load_aliases()
        if ent in aliases:
            resolved.add(aliases[ent])
    return resolved


def _freshness(published_at: str, as_of: date) -> float:
    if not published_at:
        return 0.8
    try:
        pub = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        pub_day = pub.date()
    except ValueError:
        return 0.8
    days = max((as_of - pub_day).days, 0)
    return round(math.exp(-days / 5.0), 4)  # ~0.5 at 3.5d, ~0.14 at 10d


def _relevance(news_score: float, cross_ref: bool) -> float:
    base = max(0.0, min(news_score / 10.0, 1.0))
    floor = 0.5 if cross_ref else 0.2
    return round(max(base, floor), 4)


def _exposure_weights(positions: list[tuple[str, float]]) -> dict[str, float]:
    """Cost-basis weight per held ticker (no live price needed)."""
    total = sum(v for _, v in positions if v > 0)
    if total <= 0:
        return {}
    return {t.upper(): v / total for t, v in positions if v > 0}


def _classify(
    news_tickers: set[str],
    held_weights: dict[str, float],
    theme: str,
    held_themes: set[str],
) -> dict[str, tuple[RelationKind, str]]:
    """Map each affected held ticker -> (strongest relation kind, note)."""
    best: dict[str, tuple[RelationKind, str]] = {}

    def _offer(holding: str, kind: RelationKind, note: str) -> None:
        cur = best.get(holding)
        if cur is None or _RELATION_RANK[kind] > _RELATION_RANK[cur[0]]:
            best[holding] = (kind, note)

    for holding in held_weights:
        if holding in news_tickers:
            _offer(holding, "direct", f"{holding} 為新聞直接標的")
        if news_tickers & _load_relationship_counterparties(holding):
            _offer(holding, "supply_chain", f"{holding} 的供應鏈對手方出現在新聞")

    for cluster in _load_clusters():
        if news_tickers & set(cluster):
            for holding in held_weights:
                if holding in cluster and holding not in news_tickers:
                    _offer(holding, "cluster", f"{holding} 與新聞標的同相關性叢集")

    if theme and theme in held_themes:
        for holding in held_weights:
            _offer(holding, "theme", f"{holding} 屬同主題 {theme}")

    return best


def score_impact(
    *,
    tickers: list[str],
    entity: str,
    theme: str,
    confidence: str,
    news_score: float,
    cross_ref: bool,
    published_at: str,
    positions: list[tuple[str, float]],
    held_themes: set[str],
    as_of: Optional[date] = None,
) -> PortfolioImpact:
    """Score a single news item against the portfolio. `positions` = (ticker, value)."""
    as_of = as_of or datetime.now(timezone.utc).date()
    held_weights = _exposure_weights(positions)
    news_tickers = resolve_tickers(tickers, entity)

    affected_map = _classify(news_tickers, held_weights, theme, held_themes)
    affected = [
        AffectedPosition(ticker=t, kind=kind, note_zh=note)
        for t, (kind, note) in sorted(
            affected_map.items(), key=lambda kv: -_RELATION_RANK[kv[1][0]]
        )
    ]

    relevance = _relevance(news_score, cross_ref)
    confidence_w = _CONFIDENCE_WEIGHT.get(confidence, 0.7)
    freshness = _freshness(published_at, as_of)

    if not affected:
        components = ImpactComponents(
            relevance=relevance,
            exposure_weight=0.0,
            relation_weight=0.0,
            freshness=freshness,
            confidence=confidence_w,
        )
        return PortfolioImpact(
            score=0.0, components=components, rationale_zh="與目前持倉無直接或間接關聯。"
        )

    # Diminishing returns on aggregate exposure so one mega-cap story can't dominate.
    raw_exposure = sum(held_weights.get(a.ticker, 0.0) for a in affected)
    exposure_weight = round(1.0 - math.exp(-2.0 * raw_exposure), 4)
    relation_weight = max(RELATION_WEIGHT[a.kind] for a in affected)

    score = round(
        relevance * exposure_weight * relation_weight * freshness * confidence_w, 4
    )
    components = ImpactComponents(
        relevance=relevance,
        exposure_weight=exposure_weight,
        relation_weight=relation_weight,
        freshness=freshness,
        confidence=confidence_w,
    )
    top = affected[0]
    rationale = f"影響 {len(affected)} 檔持倉，最強關聯：{top.note_zh}。"
    return PortfolioImpact(
        score=score,
        components=components,
        affected_positions=affected,
        rationale_zh=rationale,
    )
