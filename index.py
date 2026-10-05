"""Vercel entry point for the backend package in this repository."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.main import app as app  # noqa: E402
