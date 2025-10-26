# Stage 1 Build with uv
FROM python:3.12-slim AS builder

# Install uv tool
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies into .venv
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable

# Copy application code
ADD . /app

# Sync project (install local deps)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable


# Stage 2 Slim runtime
FROM python:3.12-slim

# Install required system deps
#RUN apt-get update && apt-get install -y --no-install-recommends \
#    build-essential \
#    && rm -rf /var/lib/apt/lists/*

# Create user
RUN adduser --disabled-password --gecos "" app

# Copy only the venv and necessary source files
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app main.py /app
COPY --chown=app:app notes.py /app

USER app
WORKDIR /app
EXPOSE 8000

# Run uvicorn using venv Python
CMD ["/app/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--reload"]

