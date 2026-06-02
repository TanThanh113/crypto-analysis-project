FROM python:3.12-slim

# Copy uv binary from official uv image
COPY --from=docker.io/astral/uv:latest /uv /uvx /bin/

# Install system dependencies needed by dbt / BigQuery / git packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# dbt should look for profiles.yml inside the dbt project folder
ENV DBT_PROFILES_DIR="/app/crypto_dbt"

# Copy dependency files first for Docker layer cache
COPY pyproject.toml uv.lock .python-version ./

RUN uv sync --locked

# Copy dbt project
COPY crypto_dbt ./crypto_dbt

WORKDIR /app/crypto_dbt
RUN uv run dbt deps

# Create dbt output folders
RUN mkdir -p target logs

CMD ["sh", "-c", "echo 'dbt image ready. Example: docker run <image> uv run dbt build --select fact_crypto_features_hourly'"]