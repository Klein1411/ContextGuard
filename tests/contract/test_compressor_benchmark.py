from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.compressor_benchmark import _metric


def test_compressor_metric_uses_safe_saving_only_for_pass() -> None:
    row = {
        "sample_id": "x",
        "source_name": "test",
        "domain": "technical",
        "language": "en",
    }
    safe = _metric(
        row=row,
        compressor="rule-based",
        rate=0.5,
        protected=True,
        mode="R7_direct_guard",
        original_tokens=100,
        candidate="short",
        candidate_tokens=60,
        status="PASS",
        protected_count=2,
        protected_retained=True,
        fallback=False,
        fallback_reason="",
        latency_ms=1.0,
    )
    unsafe = _metric(
        row=row,
        compressor="rule-based",
        rate=0.5,
        protected=True,
        mode="R7_direct_guard",
        original_tokens=100,
        candidate="short",
        candidate_tokens=60,
        status="FAIL",
        protected_count=2,
        protected_retained=False,
        fallback=False,
        fallback_reason="",
        latency_ms=1.0,
    )
    assert safe.gross_saved_tokens == 40
    assert safe.safe_effective_saved_tokens == 40
    assert unsafe.gross_saved_tokens == 40
    assert unsafe.safe_effective_saved_tokens == 0
