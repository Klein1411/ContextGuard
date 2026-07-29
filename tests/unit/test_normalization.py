from context_guard.normalization.text import extract_facts


def test_vietnamese_language_and_protected_values() -> None:
    facts, spans, warnings, language = extract_facts(
        "Không dùng Python 3.11 với 4 GB RAM và accuracy 90%.", "auto"
    )
    assert language == "vi"
    assert {fact.type for fact in facts} >= {"version", "unit", "percentage"}
    assert any(span.normalized_value == "python 3.11" for span in spans)
    assert warnings == []


def test_ambiguous_date_is_warning() -> None:
    _, _, warnings, _ = extract_facts("Deadline là 03/04/2026.", "vi")
    assert warnings == ["Ambiguous date locale: 03/04/2026"]


def test_mixed_language_is_supported() -> None:
    _, _, _, language = extract_facts("Không deploy nếu accuracy thấp hơn 90%.", "auto")
    assert language == "vi"
