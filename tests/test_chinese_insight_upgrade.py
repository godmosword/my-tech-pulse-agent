import yaml

from agents.deep_insight_agent import BRIEF_PROMPT, BRIEF_SYSTEM
from agents.synthesizer_agent import DigestOutput, StoryInsight, SYNTHESIS_PROMPT, SYSTEM_PROMPT
from delivery.message_formatter import format_items_digest, format_insight_brief
from llm.localization import normalize_llm_payload
from sources.rss_fetcher import KOL_REGISTRY_PATH, RSSFetcher
from agents.deep_insight_agent import InsightBrief
from agents.extractor_agent import ArticleSummary


def test_chinese_sources_load_nested_registry_and_skip_transcript_candidates():
    with open(KOL_REGISTRY_PATH) as f:
        data = yaml.safe_load(f)

    assert "kol_sources" in data
    assert "chinese_sources" in data

    fetcher = RSSFetcher()
    assert "manny_newsletter" in fetcher._kol_registry
    assert "blocktrend" in fetcher._kol_registry
    assert "blocktempo_opinion" in fetcher._kol_registry

    assert fetcher._kol_registry["manny_newsletter"].display_name.startswith("曼報")
    assert fetcher._kol_registry["blocktrend"].language == "zh-TW"

    transcript_candidate = fetcher._kol_registry["dr_chu_tech_classroom"]
    assert transcript_candidate.enabled is False
    assert transcript_candidate.connector == "youtube_transcript"
    enabled_rss = {
        source.name
        for source in fetcher._kol_registry.values()
        if source.enabled and source.connector == "rss"
    }
    assert "dr_chu_tech_classroom" not in enabled_rss


def test_chinese_source_weights_exist():
    with open("scoring/score_config.yaml") as f:
        data = yaml.safe_load(f)

    assert data["source_weights"]["manny_newsletter"] == 1.5
    assert data["source_weights"]["blocktrend"] == 1.5
    assert data["source_weights"]["blocktempo_opinion"] == 1.2


def test_prompts_lock_traditional_chinese_and_ban_weak_openers():
    prompt_text = "\n".join([BRIEF_SYSTEM, BRIEF_PROMPT, SYSTEM_PROMPT, SYNTHESIS_PROMPT])

    assert "Traditional Chinese (zh-TW)" in prompt_text
    assert "【核心洞見】" in prompt_text
    assert "【底層邏輯】" in prompt_text
    assert "【生態影響】" in prompt_text
    assert "這篇文章報導了" in prompt_text
    assert "作者認為" in prompt_text


def test_normalize_llm_payload_converts_to_traditional_and_strips_weak_openers():
    payload = {
        "insight": "这篇文章报道了新型态的 L2 排序器通过共享内存降低延迟。",
        "nested": ["作者认为芯片网络带宽是瓶颈。"],
    }

    normalized = normalize_llm_payload(payload)

    assert normalized["insight"].startswith("新型態的 L2 排序器透過")
    assert "這篇文章報導了" not in normalized["insight"]
    assert "作者認為" not in normalized["nested"][0]
    assert "晶片" in normalized["nested"][0]


def test_digest_output_parses_story_insight_schema():
    digest = DigestOutput(
        date="2026-05-01",
        headline="排序器經濟學成為 DeFi 分水嶺",
        themes=[],
        contradictions=[],
        narrative="全鏈衍生品競爭開始轉向底層撮合與風控設計。",
        top_stories=[
            {
                "entity": "ExampleDEX",
                "title": "Orderbook redesign",
                "source_name": "example",
                "source_display_name": "Example Source",
                "source_url": "https://example.com",
                "source_language": "en",
                "insight": "新排序器把撮合權從前端移回協議層。",
                "tech_rationale": "協議將訂單簿狀態拆成可驗證批次，降低跨鏈訊息延遲，並讓做市商能用同一組風控參數覆蓋多市場。",
                "implication": "前端聚合器的差異化下降，底層清算與風控模組取得議價能力。",
            }
        ],
        cross_ref_count=0,
    )

    assert isinstance(digest.top_stories[0], StoryInsight)
    assert digest.top_stories[0].source_language == "en"


def test_formatter_renders_three_part_story_and_translation_tag():
    summary = ArticleSummary(
        entity="ExampleDEX",
        title="Example item",
        summary="Example summary",
        category="research",
        sentiment="neutral",
        confidence="high",
        score=8.5,
        source_name="example",
        source_url="https://example.com/item",
        source_display_name="Example Source",
        source_language="en",
    )
    story = StoryInsight(
        entity="ExampleDEX",
        title="Orderbook redesign",
        source_name="example",
        source_display_name="Example Source",
        source_url="https://example.com/story",
        source_language="en",
        insight="新排序器把撮合權從前端移回協議層。",
        tech_rationale="協議將訂單簿狀態拆成可驗證批次，降低跨鏈訊息延遲。",
        implication="前端聚合器的差異化下降，底層清算模組取得議價能力。",
    )

    msg = format_items_digest(
        [summary],
        total_fetched=1,
        total_after_filter=1,
        story_insights=[story],
    )

    assert "*【核心洞見】*" in msg
    assert "*【底層邏輯】*" in msg
    assert "*【生態影響】*" in msg
    assert "\\[📝 原文為英文，已由 Q\\-Silicon 深度編譯\\]" in msg
    assert "[Example Source](https://example.com/story)" in msg


def test_format_insight_brief_uses_display_source_and_skips_tag_for_zh_tw():
    brief = InsightBrief(
        item_id="abc12345",
        title="矽光子封裝分析",
        author="Analyst",
        source_name="manny_newsletter",
        source_display_name="曼報 (Manny's Newsletter)",
        source_language="zh-TW",
        url="https://manny-li.com/example",
        domain="semiconductor",
        insight="共同封裝光學把資料中心瓶頸從交換器推回封裝設計，讓先進封裝不再只是良率問題。",
        tech_rationale=(
            "光訊號若在封裝邊界才轉換，SerDes 與銅線損耗會把功耗吃掉；把光引擎貼近運算晶粒，"
            "可縮短電訊號距離，但熱管理、對準精度與良率控制會同步變成系統級約束。"
        ),
        implication="封測廠、矽光子供應商與雲端自研晶片團隊的合作深度會上升，單純交換器供應商議價力被壓縮。",
        confidence="high",
    )

    msg = format_insight_brief(brief)

    assert "曼報" in msg
    assert "*【核心洞見】*" in msg
    assert "Q\\-Silicon" not in msg
