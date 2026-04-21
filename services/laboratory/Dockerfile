ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS builder
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.4.20 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy
COPY pyproject.toml ./
COPY libs/shared_kernel/pyproject.toml ./libs/shared_kernel/
COPY services/laboratory/pyproject.toml ./services/laboratory/
RUN uv lock && uv sync --frozen --no-dev --package laboratory --python python${PYTHON_VERSION}
COPY libs/shared_kernel/src ./libs/shared_kernel/src
COPY services/laboratory/src ./services/laboratory/src

FROM python:${PYTHON_VERSION}-slim AS runtime
WORKDIR /app
RUN adduser --disabled-password --gecos "" --uid 1000 appuser
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/libs /app/libs
COPY --from=builder /app/services/laboratory /app/services/laboratory
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/services/laboratory/src:/app/libs/shared_kernel/src"
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')"
USER appuser
EXPOSE 8000
CMD ["uvicorn", "laboratory.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
