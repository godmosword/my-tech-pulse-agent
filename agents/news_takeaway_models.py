"""Pydantic models for per-article investment takeaway (news feed layer)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TakeawayLLMOutput(BaseModel):
    takeaway_zh: str = ""
    angle: Literal[
        "供應鏈",
        "競爭格局",
        "需求訊號",
        "政策監管",
        "技術突破",
        "資本動向",
        "其他",
    ] = "其他"
    involved_companies: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"


class NewsTakeaway(BaseModel):
    item_id: str
    takeaway_zh: str = ""
    angle: Literal[
        "供應鏈",
        "競爭格局",
        "需求訊號",
        "政策監管",
        "技術突破",
        "資本動向",
        "其他",
    ] = "其他"
    tickers: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
