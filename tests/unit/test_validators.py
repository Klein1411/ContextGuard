from context_guard import ContextGuard, GuardConfig, RecommendedAction, SafetyStatus


def test_negation_removal_is_critical_fail_vi() -> None:
    result = ContextGuard(GuardConfig(language="vi", profile="technical")).validate(
        "Không triển khai nếu accuracy thấp hơn 90%.",
        "Triển khai nếu accuracy thấp hơn 90%.",
    )
    assert result.status is SafetyStatus.FAIL
    assert result.recommended_action is RecommendedAction.USE_ORIGINAL
    assert "NEGATION_REMOVED" in result.reason_codes


def test_version_change_is_critical_fail_en() -> None:
    result = ContextGuard(GuardConfig(language="en", profile="technical")).validate(
        "Do not deploy Python 3.11 when latency exceeds 50 ms.",
        "Do not deploy Python 3.12 when latency exceeds 50 ms.",
    )
    assert result.status is SafetyStatus.FAIL
    assert "VERSION_CHANGED" in result.reason_codes


def test_safe_identity_passes() -> None:
    result = ContextGuard(GuardConfig(language="en")).validate(
        "The model achieved 90% accuracy.", "The model achieved 90% accuracy."
    )
    assert result.status is SafetyStatus.PASS
    assert result.risk_score == 0


def test_ambiguous_date_is_uncertain() -> None:
    result = ContextGuard(GuardConfig(language="vi")).validate(
        "Deadline 03/04/2026.", "Deadline 03/04/2026."
    )
    assert result.status is SafetyStatus.UNCERTAIN
    assert result.recommended_action is RecommendedAction.USE_ORIGINAL


def test_input_is_not_silently_truncated() -> None:
    guard = ContextGuard(GuardConfig(max_input_chars=5))
    try:
        guard.validate("123456", "123456")
    except ValueError as exc:
        assert "max_input_chars=5" in str(exc)
    else:
        raise AssertionError("oversized input must be rejected")


def test_empty_text_is_uncertain() -> None:
    result = ContextGuard().validate("", "")
    assert result.status is SafetyStatus.UNCERTAIN
    assert "EMPTY_TEXT" not in result.reason_codes
