"""Persistent data-home helpers used by long-running benchmarks and reviews."""

from __future__ import annotations

import os
from pathlib import Path

DATA_HOME_ENV = "CONTEXTGUARD_DATA_HOME"
DATA_HOME_CHILDREN = (
    "raw",
    "extracted",
    "normalized",
    "model_cache",
    "reviewer_runs",
    "benchmark_cache",
    "manifests",
)


def get_data_home() -> Path:
    """Return the configured persistent data home without creating it."""

    configured = os.environ.get(DATA_HOME_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        return Path("D:/fact_safeguard_data").resolve()
    return (Path.home() / ".contextguard_data").resolve()


def ensure_data_home(path: Path | None = None) -> Path:
    """Create the data home and its stable child directories."""

    root = (path or get_data_home()).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for child in DATA_HOME_CHILDREN:
        (root / child).mkdir(exist_ok=True)
    return root


def is_within_data_home(path: Path, data_home: Path | None = None) -> bool:
    """Return whether ``path`` is the data home or one of its descendants."""

    target = path.resolve()
    root = (data_home or get_data_home()).resolve()
    return target == root or root in target.parents
