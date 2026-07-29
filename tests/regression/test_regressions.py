from context_guard import ContextGuard, GuardConfig, SafetyStatus


def test_units_are_not_interchangeable() -> None:
    result = ContextGuard(GuardConfig(language="en", profile="technical")).validate(
        "Use 4 GB RAM.", "Use 4 MB RAM."
    )
    assert result.status is SafetyStatus.FAIL
    assert any(code.startswith("UNIT_") for code in result.reason_codes)


def test_must_to_should_is_not_accepted() -> None:
    result = ContextGuard(GuardConfig(language="en")).validate(
        "You must deploy.", "You should deploy."
    )
    assert result.status is SafetyStatus.FAIL
    assert "MODALITY_CHANGED" in result.reason_codes


def test_condition_removal_is_critical() -> None:
    result = ContextGuard(GuardConfig(language="en")).validate("Deploy if tests pass.", "Deploy.")
    assert result.status is SafetyStatus.FAIL
    assert "CONDITION_REMOVED" in result.reason_codes


def test_technical_literals_include_filename_config_and_boolean() -> None:
    result = ContextGuard(GuardConfig(language="en", profile="technical")).validate(
        "Use config.yaml with safe=true.",
        "Use other.py with safe=false.",
    )
    assert result.status is SafetyStatus.FAIL
    assert {"FILENAME_CHANGED", "CONFIG_CHANGED"} <= set(result.reason_codes)
