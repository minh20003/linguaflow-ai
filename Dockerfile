# ---- Stage 1: Build ----
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Stage 2: Production ----
FROM python:3.11-slim

WORKDIR /app

# The virtual environment is outside /root so the non-root runtime user can
# execute console scripts such as Alembic as well as import installed packages.
# It includes imageio-ffmpeg's platform binary for bounded, temporary STT-only
# conversion without the full Debian multimedia dependency closure.
COPY --from=builder /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

# Security: run as non-root user
RUN useradd -m appuser

# Copy application code
COPY . .

# Create data directory with correct ownership
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

# The port is whatever the host injects: Railway, Render and Cloud Run all set
# $PORT and route to it, so a fixed port makes the service unreachable there.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.environ.get('PORT', '8000'))" || exit 1

# Shell form so $PORT is expanded at run time. Deliberately no `--workers`:
# ConnectionManager holds the open sockets in process memory (see
# src/api/websocket.py), so a second worker would only see half the connections
# and message fan-out would drop the other half.
#
# Migrations run here rather than in the application's lifespan: the container
# must fail loudly and stay down when the schema cannot be brought up to date,
# instead of serving requests against a database it disagrees with.
CMD ["sh", "-c", "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
