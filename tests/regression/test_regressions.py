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


def test_vietnamese_comparison_direction_change_is_critical() -> None:
    result = ContextGuard(GuardConfig(language="vi", profile="technical")).validate(
        "Triển khai nếu accuracy ít nhất 90%.",
        "Triển khai nếu accuracy thấp hơn 90%.",
    )
    assert result.status is SafetyStatus.FAIL
    assert "COMPARISON_CHANGED" in result.reason_codes


def test_vietnamese_negation_is_not_double_counted_as_zero() -> None:
    result = ContextGuard(GuardConfig(language="vi", profile="technical")).validate(
        "Không triển khai.",
        "Triển khai.",
    )
    assert result.status is SafetyStatus.FAIL
    assert "NEGATION_REMOVED" in result.reason_codes
    assert "NUMBER_REMOVED" not in result.reason_codes


def test_technical_literals_include_filename_config_and_boolean() -> None:
    result = ContextGuard(GuardConfig(language="en", profile="technical")).validate(
        "Use config.yaml with safe=true.",
        "Use other.py with safe=false.",
    )
    assert result.status is SafetyStatus.FAIL
    assert {"FILENAME_CHANGED", "CONFIG_CHANGED"} <= set(result.reason_codes)


def test_exact_guard_reports_duplicated_and_added_literals() -> None:
    duplicate = ContextGuard(GuardConfig(language="en", profile="technical")).validate(
        "Use 4 GB RAM.",
        "Use 4 GB RAM and 4 GB RAM.",
    )
    assert duplicate.status is SafetyStatus.FAIL
    assert "UNIT_DUPLICATED" in duplicate.reason_codes

    added = ContextGuard(GuardConfig(language="en", profile="technical")).validate(
        "Use 4 GB RAM.",
        "Use 4 GB RAM and 8 GB RAM.",
    )
    assert added.status is SafetyStatus.FAIL
    assert "FACT_ADDED" in added.reason_codes

    new_kind = ContextGuard(GuardConfig(language="en", profile="business")).validate(
        "Deploy.",
        "Deploy on 30/08/2026.",
    )
    assert new_kind.status is SafetyStatus.FAIL
    assert "FACT_ADDED" in new_kind.reason_codes
