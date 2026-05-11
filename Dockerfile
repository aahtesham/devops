# Pin Python 3.12 so pydantic-core installs from wheels (avoids Rust/maturin on read-only FS).
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY crypton/ ./crypton/
COPY app.py main.py ./

EXPOSE 8000

# Render sets PORT; local fallback 8000
CMD sh -c "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"
