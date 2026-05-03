FROM python:3.13-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser \
    && useradd -r -g appuser -u 1000 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

WORKDIR /app

RUN pip install --no-cache-dir cryptography==43.0.0

COPY backend/ ./backend/

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost:8765/health || exit 1

ENV GRANTLAYER_HOST=0.0.0.0
ENV GRANTLAYER_PORT=8765

CMD ["python3", "-m", "backend"]
