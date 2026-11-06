"""Make src/ importable for the test suite (stdlib only, no install step)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
