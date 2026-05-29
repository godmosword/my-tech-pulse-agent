"""Pydantic models for SEC 10-K business relationship extraction."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

RelationKind = Literal["customer", "supplier", "competitor", "partner"]


class RelationshipEdge(BaseModel):
    counterparty_name: str
    counterparty_ticker: Optional[str] = None
    relation: RelationKind
    quote: str
    concentration_note: str = ""
    verified: bool = False


class CompanyRelationships(BaseModel):
    ticker: str
    fiscal_year: Optional[int] = None
    source_form: str = "10-K"
    filed: Optional[str] = None
    edges: list[RelationshipEdge] = Field(default_factory=list)
    as_of: Optional[str] = None
