"""Extract Non-GAAP / adjusted diluted EPS from earnings press-release text."""

from __future__ import annotations

import re
from typing import Optional

# Patterns ordered by specificity; value must appear verbatim in source text.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:non-gaap|non gaap)\s+(?:diluted\s+)?eps(?:\s+was|\s+of)?\s*\$?\s*([0-9]+\.?[0-9]*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"adjusted\s+(?:diluted\s+)?eps(?:\s+was|\s+of)?\s*\$?\s*([0-9]+\.?[0-9]*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"diluted\s+eps[,\s]+on\s+a\s+non-gaap\s+basis[,\s]+was\s+\$?\s*([0-9]+\.?[0-9]*)",
        re.IGNORECASE,
    ),
)


def extract_non_gaap_eps_diluted(filing_text: str) -> Optional[float]:
    """Return first verified Non-GAAP diluted EPS in [0.01, 500] or None."""
    if not filing_text or len(filing_text) < 50:
        return None
    for pattern in _PATTERNS:
        for match in pattern.finditer(filing_text):
            raw = match.group(1)
            needle = raw if raw.startswith("$") else f"${raw}"
            if needle not in filing_text and raw not in filing_text:
                continue
            try:
                value = float(raw)
            except ValueError:
                continue
            if 0.01 <= value <= 500.0:
                return value
    return None
