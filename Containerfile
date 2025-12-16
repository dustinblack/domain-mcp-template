# syntax=docker/dockerfile:1.7-labs

# Single-stage UBI9 Python image with system-wide dependencies
FROM registry.access.redhat.com/ubi9/python-311:latest

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies system-wide
COPY requirements.txt ./
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy application code and docs
COPY src ./src
COPY requirements.txt pyproject.toml README.md ./

# Create a non-root user and fix permissions
USER 0
RUN useradd -r -u 10001 appuser && chown -R appuser:0 /app && chmod -R g=u /app
USER appuser

# Expose HTTP port
EXPOSE 8080

# Default to HTTP mode; allow override via CMD/args
ENV DOMAIN_MCP_LOG_LEVEL=INFO
CMD ["python", "-m", "src.server.cli", "--http", "--host", "0.0.0.0", "--port", "8080"]


