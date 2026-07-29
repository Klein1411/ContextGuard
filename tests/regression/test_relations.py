from context_guard import ContextGuard, GuardConfig, SafetyStatus


def test_explicit_responsibility_change_is_critical() -> None:
    result = ContextGuard(GuardConfig(language="en", profile="business")).validate(
        "Alice is responsible for the release.",
        "Bob is responsible for the release.",
    )
    assert result.status is SafetyStatus.FAIL
    assert "ROLE_SWAP" in result.reason_codes


def test_model_role_change_is_critical_in_both_languages() -> None:
    for language, original, candidate in (
        ("en", "ModelB is used as target.", "ModelB is used as draft."),
        ("vi", "ModelB được dùng làm target.", "ModelB được dùng làm draft."),
    ):
        result = ContextGuard(GuardConfig(language=language, profile="technical")).validate(
            original, candidate
        )
        assert result.status is SafetyStatus.FAIL
        assert "MODEL_ROLE_SWAP" in result.reason_codes


def test_metric_dataset_relation_change_is_detected() -> None:
    result = ContextGuard(GuardConfig(language="en", profile="academic")).validate(
        "Accuracy is 90% on XNLI.",
        "Accuracy is 90% on MNLI.",
    )
    assert result.status is SafetyStatus.FAIL
    assert "RELATION_CHANGED" in result.reason_codes


def test_config_component_relation_change_is_detected() -> None:
    result = ContextGuard(GuardConfig(language="en", profile="technical")).validate(
        "config.yaml belongs to API.",
        "config.yaml belongs to UI.",
    )
    assert result.status is SafetyStatus.FAIL
    assert "RELATION_CHANGED" in result.reason_codes


def test_method_dataset_relation_change_is_detected_in_vietnamese() -> None:
    result = ContextGuard(GuardConfig(language="vi", profile="academic")).validate(
        "ResNet được đánh giá trên CIFAR-10.",
        "ResNet được đánh giá trên ImageNet.",
    )
    assert result.status is SafetyStatus.FAIL
    assert "RELATION_CHANGED" in result.reason_codes
