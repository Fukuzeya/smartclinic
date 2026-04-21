# Patient Identity service
#
# Multi-stage build:
#  1. builder  — installs Python dependencies with uv into /app/.venv
#  2. runtime  — copies just the venv + source; runs as non-root uid 1000.
#
# Build from repo root:
#   docker build -f services/patient_identity/Dockerfile -t patient_identity:dev .

ARG PYTHON_VERSION=3.12

# ── Stage 1: dependency installation ──────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS builder

WORKDIR /app

# Install uv (pinned to a known-good version)
COPY --from=ghcr.io/astral-sh/uv:0.4.20 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy

# Copy workspace manifests first so Docker caches the install layer.
COPY pyproject.toml ./
COPY libs/shared_kernel/pyproject.toml ./libs/shared_kernel/
COPY services/patient_identity/pyproject.toml ./services/patient_identity/

# Resolve dependencies (generates uv.lock on the fly), then install.
RUN uv lock && uv sync \
      --frozen \
      --no-dev \
      --package patient_identity \
      --python python${PYTHON_VERSION}

# Copy source code after deps are cached.
COPY libs/shared_kernel/src ./libs/shared_kernel/src
COPY services/patient_identity/src ./services/patient_identity/src

# ── Stage 2: runtime image ─────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS runtime

WORKDIR /app

# Non-root user — principle of least privilege.
RUN adduser --disabled-password --gecos "" --uid 1000 appuser

# Copy the populated venv and source from builder.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/libs /app/libs
COPY --from=builder /app/services/patient_identity /app/services/patient_identity

# Activate the venv for all subsequent commands.
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/services/patient_identity/src:/app/libs/shared_kernel/src"

# Healthcheck — matches the /health/live probe in the FastAPI app.
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')"

USER appuser

EXPOSE 8000

# Uvicorn with 2 workers; Docker Compose override replaces with --reload.
CMD ["uvicorn", "patient_identity.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--access-log", \
     "--log-level", "info"]
