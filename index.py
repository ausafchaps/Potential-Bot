"""Vercel entry point for the backend package in this repository."""

import sys
from pathlib import Path

from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.main import create_app  # noqa: E402

app = create_app()
# API routes take precedence; only public frontend files are mounted here.
app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent / "frontend", html=True))
