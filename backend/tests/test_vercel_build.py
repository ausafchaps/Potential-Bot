"""Ensure staging requires safe migrations and serves both frontend and API."""

import importlib.util
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def build(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "scripts" / "build_vercel.py"
    spec = importlib.util.spec_from_file_location("vercel_build", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/staging?sslmode=require")
    return module


@pytest.mark.parametrize(
    "variable,value",
    [
        ("ENVIRONMENT", "local"),
        ("DATABASE_URL", ""),
        ("DATABASE_URL", "sqlite:///./staging.db"),
        ("DATABASE_URL", "postgresql://test:test@localhost/staging"),
    ],
)
def test_unsafe_configuration_never_migrates(build, monkeypatch, variable, value):
    monkeypatch.setenv(variable, value)
    migrate = Mock()
    monkeypatch.setattr(build.subprocess, "run", migrate)
    with pytest.raises(RuntimeError):
        build.main()
    migrate.assert_not_called()


def test_failed_migration_fails_build(build, monkeypatch):
    monkeypatch.setattr(
        build.subprocess, "run", Mock(side_effect=subprocess.CalledProcessError(1, "alembic"))
    )
    with pytest.raises(subprocess.CalledProcessError):
        build.main()


def test_entrypoint_serves_frontend_and_preserves_api_authentication():
    path = Path(__file__).resolve().parents[2] / "index.py"
    spec = importlib.util.spec_from_file_location("vercel_entrypoint", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with TestClient(module.app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "text/html" in page.headers["content-type"]
        assert "StudyBot" in page.text
        assert client.get("/app.js").status_code == 200
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/auth/me").status_code == 401
        assert client.get("/.env").status_code == 404
