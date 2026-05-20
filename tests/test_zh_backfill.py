"""Tests for lightweight zh backfill extraction helpers."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm.localization import has_cjk
from llm.zh_backfill import ZhBackfillResult, _clean_zh_summary, _clean_zh_title
from scripts.backfill_zh_fields import _patch_from_zh


def test_clean_zh_title_accepts_cjk():
    assert _clean_zh_title("Google 發布新工具") == "Google 發布新工具"


def test_clean_zh_summary_rejects_english():
    assert _clean_zh_summary("English only summary here.") is None


def test_patch_replaces_empty_zh_fields():
    zh = ZhBackfillResult(
        zh_title="Google 發布 Antigravity 2.0",
        zh_summary="Google 在 I/O 2026 發表 Antigravity 2.0，整合桌面與 CLI。此舉意在強化開發者代理工作流。",
        hook="代理工具再升級",
    )
    patch = _patch_from_zh({"zh_title": "", "zh_summary": ""}, zh)
    assert "zh_title" in patch
    assert has_cjk(patch["zh_title"])
