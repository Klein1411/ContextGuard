from __future__ import annotations

import shutil
from pathlib import Path

from context_guard.storage import get_data_home, is_within_data_home

repo_root = Path(__file__).resolve().parents[1]
data_home = get_data_home()

for name in (".runtime", ".pytest_cache", ".ruff_cache", ".mypy_cache", "htmlcov", ".coverage"):
    path = (repo_root / name).resolve()
    if is_within_data_home(path, data_home):
        raise RuntimeError(f"refusing to clean persistent data home: {path}")
    if path.is_dir():
        shutil.rmtree(path)
    elif path.is_file():
        path.unlink()
