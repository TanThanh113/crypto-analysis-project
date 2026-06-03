FROM python:3.12-slim

# Copy uv binary directly from Docker Hub official image
COPY --from=docker.io/astral/uv:latest /uv /uvx /bin/

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Copy dependency files first
COPY "pyproject.toml" "uv.lock" ".python-version" ./
RUN uv sync --locked

# Copy application code
COPY batch ./batch

# Create a folder named output_data beforehand to avoid permission errors.
RUN mkdir -p output_data

# Set entry point
CMD ["echo", "Please select a script to run. For example: docker run <image> uv run batch/macro_extractor.py"]
