FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

FROM base AS builder
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

FROM base AS runtime
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ ./src/

RUN addgroup --system tng && adduser --system --ingroup tng tng
USER tng

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/health/live')"

CMD ["uvicorn", "tng.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
