"""Test configuration: pre-mock google.genai to avoid cryptography/cffi crash.

This environment has a broken cryptography/cffi installation that causes a
pyo3_runtime.PanicException when google.genai (which imports google.auth →
cryptography) is loaded. We register fake module stubs in sys.modules before
any test imports trigger the real library.
"""

import sys
from unittest.mock import MagicMock

# Only stub if the real library isn't already healthy
if "google.genai" not in sys.modules:
    _google_stub = MagicMock()
    _genai_stub = MagicMock()
    _types_stub = MagicMock()

    # Ensure attribute access on stubs returns MagicMocks (default MagicMock behaviour)
    sys.modules.setdefault("google", _google_stub)
    sys.modules["google.genai"] = _genai_stub
    sys.modules["google.genai.types"] = _types_stub
    sys.modules["google.auth"] = MagicMock()
