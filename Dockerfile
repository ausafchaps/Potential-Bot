# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    DATABASE_URL=sqlite:////data/studybot.db

WORKDIR /app

RUN groupadd --system studybot \
    && useradd --system --gid studybot --home-dir /app studybot \
    && mkdir -p /data \
    && chown studybot:studybot /data

COPY pyproject.toml README.md alembic.ini ./
COPY backend ./backend

RUN python -m pip install --upgrade pip \
    && python -m pip install .

USER studybot

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/health', timeout=3)"

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
