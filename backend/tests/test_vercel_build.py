"""Ensure a staging build cannot publish before a safe migration succeeds."""

import importlib.util
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest


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
def test_unsafe_configuration_never_migrates_or_publishes(build, monkeypatch, variable, value):
    monkeypatch.setenv(variable, value)
    migrate = Mock()
    publish = Mock()
    monkeypatch.setattr(build.subprocess, "run", migrate)
    monkeypatch.setattr(build.shutil, "copytree", publish)
    with pytest.raises(RuntimeError):
        build.main()
    migrate.assert_not_called()
    publish.assert_not_called()


def test_failed_migration_prevents_frontend_publication(build, monkeypatch):
    monkeypatch.setattr(
        build.subprocess, "run", Mock(side_effect=subprocess.CalledProcessError(1, "alembic"))
    )
    publish = Mock()
    monkeypatch.setattr(build.shutil, "copytree", publish)
    with pytest.raises(subprocess.CalledProcessError):
        build.main()
    publish.assert_not_called()
