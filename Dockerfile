FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications and install
COPY requirements.txt pyproject.toml /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code and scripts
COPY src/ /app/src/
COPY scripts/ /app/scripts/
COPY docs/ /app/docs/

# Create persistent mount directories
RUN mkdir -p /app/data /app/vault /root/.cache/research-toolkit

# Install package
RUN pip install --no-cache-dir -e .

# Default volume mount points
VOLUME ["/app/data", "/app/vault"]

# Default entrypoint runs the CLI prototype simulator / CLI tool
ENTRYPOINT ["python3", "scripts/prototype_cli.py"]
CMD ["--help"]
