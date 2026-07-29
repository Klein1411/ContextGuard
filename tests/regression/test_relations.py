from context_guard import ContextGuard, GuardConfig, SafetyStatus


def test_explicit_responsibility_change_is_critical() -> None:
    result = ContextGuard(GuardConfig(language="en", profile="business")).validate(
        "Alice is responsible for the release.",
        "Bob is responsible for the release.",
    )
    assert result.status is SafetyStatus.FAIL
    assert "ROLE_SWAP" in result.reason_codes
