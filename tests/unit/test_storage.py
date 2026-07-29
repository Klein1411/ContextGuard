from __future__ import annotations

from pathlib import Path

from context_guard.storage import ensure_data_home, get_data_home, is_within_data_home


def test_data_home_uses_environment(monkeypatch, tmp_path: Path) -> None:
    configured = tmp_path / "persistent"
    monkeypatch.setenv("CONTEXTGUARD_DATA_HOME", str(configured))
    assert get_data_home() == configured.resolve()
    root = ensure_data_home()
    assert root == configured.resolve()
    assert (root / "benchmark_cache").is_dir()
    assert is_within_data_home(root / "reviewer_runs" / "run.json", root)


def test_data_home_does_not_mark_unrelated_path(tmp_path: Path) -> None:
    root = tmp_path / "persistent"
    assert not is_within_data_home(tmp_path / "repo", root)
