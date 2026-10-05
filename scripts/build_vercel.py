"""Apply staging migrations, then publish the frontend to Vercel's CDN."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    database_url = os.environ.get("DATABASE_URL")
    if not database_url or os.environ.get("ENVIRONMENT") != "production":
        raise RuntimeError("Set ENVIRONMENT=production and DATABASE_URL before building staging")
    url = make_url(database_url)
    if url.get_backend_name() not in {"postgres", "postgresql"}:
        raise RuntimeError("Vercel staging requires persistent PostgreSQL, not a local database")
    if url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
        raise RuntimeError("The staging database connection must require TLS")
    os.environ["DATABASE_URL"] = url.set(drivername="postgresql+psycopg").render_as_string(
        hide_password=False
    )
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, check=True)
    shutil.copytree(root / "frontend", root / "public", dirs_exist_ok=True)
    print("Migrations complete; frontend prepared for the CDN")


if __name__ == "__main__":
    main()
