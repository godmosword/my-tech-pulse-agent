"""Vulture whitelist — public / schema surfaces that static analysis marks unused."""

# Pydantic model fields (serialization / API contract)
from agents.earnings_v3_models import (  # noqa: F401
    FinancialHealth,
    InvestmentSignal,
    MetricTrend,
    EarningsTrend,
    PriceReaction,
    ValuationRatios,
)

_ = FinancialHealth.fcf_conversion_pct
_ = ValuationRatios.gross_margin
_ = ValuationRatios.operating_margin
_ = ValuationRatios.net_margin
_ = ValuationRatios.roe
_ = EarningsTrend.quarters_covered
_ = PriceReaction.bench_ret_5d_pct
_ = InvestmentSignal.rationale_zh

# Agent hooks / limits (called via config or subclass patterns)
from agents.deep_insight_agent import DeepInsightAgent  # noqa: F401
from agents.earnings_agent import EarningsAgent  # noqa: F401
from agents.earnings_narrative_extractor import EarningsNarrativeExtractor  # noqa: F401
from agents.transcript_agent import TranscriptAgent  # noqa: F401

DeepInsightAgent.enforce_summary_length
EarningsAgent.limit_quotes
EarningsNarrativeExtractor.limit_quotes
TranscriptAgent.cap_items

from agents.earnings_fact_guard import _value_in_source  # noqa: F401
from agents.relationship_models import RelationshipEdge  # noqa: F401

_ = RelationshipEdge.source_form

from agents.synthesizer_agent import Theme  # noqa: F401

_ = Theme.supporting_entities

# Store protocol implementations (selected via factory)
from scoring.digest_store import DigestStore, FirestoreDigestStore  # noqa: F401
from scoring.memory_store import FirestoreMemoryStore, SqliteMemoryStore  # noqa: F401

DigestStore.get_latest
FirestoreDigestStore.get_latest
SqliteMemoryStore.archive_earnings
SqliteMemoryStore.is_semantic_duplicate
FirestoreMemoryStore.archive_earnings
FirestoreMemoryStore.is_semantic_duplicate

# Delivery / pipeline entrypoints
from delivery.message_formatter import MAX_PER_CATEGORY, _truncate  # noqa: F401
from delivery.telegram_bot import TelegramBot  # noqa: F401

TelegramBot.send_earnings
TelegramBot.start_polling
_ = MAX_PER_CATEGORY
_ = _truncate

from backtest.decision_log import evaluate_live_log  # noqa: F401
from backtest.pit_data import first_trading_day_on_or_after  # noqa: F401
from pipeline.earnings_pipeline import EarningsRunStats  # noqa: F401

_ = EarningsRunStats.sec_api_calls

# Signal handler parameters (stdlib API contract)
def _signal_handler_whitelist(signum, frame):
    return signum, frame

from sources.fmp_provider import FmpProvider, STABLE  # noqa: F401

FmpProvider.analyst_estimates
_ = STABLE
