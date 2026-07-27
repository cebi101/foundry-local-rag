"""Make ``src/`` importable when the project has not been pip-installed.

Running ``pip install -e .`` is the recommended setup, but a student who just
cloned the repo should be able to run ``python -m app.cli`` immediately. This
module adds ``src/`` to ``sys.path`` when needed and is a no-op otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
