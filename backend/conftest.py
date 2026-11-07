"""Ensure the backend package is importable regardless of pytest's cwd."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
