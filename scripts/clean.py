from __future__ import annotations

import shutil
from pathlib import Path

for name in (".runtime", ".pytest_cache", ".ruff_cache", ".mypy_cache", "htmlcov"):
    path = Path(name)
    if path.exists():
        shutil.rmtree(path)
