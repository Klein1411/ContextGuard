from __future__ import annotations

import shutil
from pathlib import Path

for name in (".runtime", ".pytest_cache", ".ruff_cache", ".mypy_cache", "htmlcov", ".coverage"):
    path = Path(name)
    if path.is_dir():
        shutil.rmtree(path)
    elif path.is_file():
        path.unlink()
