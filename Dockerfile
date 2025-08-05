# Install uv
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Change the working directory to the `app` directory
WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable

# Copy the project into the intermediate image
ADD . /app

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

FROM python:3.12-slim

RUN adduser --disabled-password --gecos "" app

# Copy the environment, but not the source code
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app note2read.py /app
COPY --chown=app:app hello.py /app

USER app
WORKDIR /app
# Run the application
#CMD ["/app/.venv/bin/hello"]
#CMD ["/app/.venv/bin/python", "/app/note2read.py"]
CMD ["/app/.venv/bin/python", "/app/hello.py"]

