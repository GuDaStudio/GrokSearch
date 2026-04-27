# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies (none needed for pure Python, but kept for compatibility)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

# ---- Runtime stage ----
FROM python:3.12-slim

WORKDIR /app

# Create non-root user with home directory
RUN groupadd -r appgroup && useradd -r -g appgroup -m -d /home/appuser appuser

# Copy installed packages and console script from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/grok-search /usr/local/bin/grok-search

# Default env for remote HTTP mode
ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000

EXPOSE 8000

USER appuser

CMD ["grok-search"]
