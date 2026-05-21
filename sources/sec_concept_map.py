"""US-GAAP XBRL concept tags for headline earnings metrics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConceptSpec:
    metric: str
    label_zh: str
    taxonomy: str
    tags: tuple[str, ...]


HEADLINE_CONCEPTS: tuple[ConceptSpec, ...] = (
    ConceptSpec(
        "revenue",
        "營收",
        "us-gaap",
        (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ),
    ),
    ConceptSpec(
        "eps_diluted",
        "稀釋 EPS",
        "us-gaap",
        ("EarningsPerShareDiluted",),
    ),
    ConceptSpec(
        "eps_basic",
        "基本 EPS",
        "us-gaap",
        ("EarningsPerShareBasic",),
    ),
    ConceptSpec(
        "net_income",
        "淨利",
        "us-gaap",
        ("NetIncomeLoss",),
    ),
    ConceptSpec(
        "gross_profit",
        "毛利",
        "us-gaap",
        ("GrossProfit",),
    ),
    ConceptSpec(
        "operating_income",
        "營業利益",
        "us-gaap",
        ("OperatingIncomeLoss",),
    ),
)

QUARTERLY_FP = frozenset({"Q1", "Q2", "Q3", "Q4"})
