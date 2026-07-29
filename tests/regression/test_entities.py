from context_guard import ContextGuard, GuardConfig, SafetyStatus


def test_explicit_entity_change_is_detected() -> None:
    result = ContextGuard(GuardConfig(language="en", profile="business")).validate(
        "Alice approves the release with Bob.",
        "Eve approves the release with Bob.",
    )
    assert result.status is SafetyStatus.FAIL
    assert "ENTITY_CHANGED" in result.reason_codes
