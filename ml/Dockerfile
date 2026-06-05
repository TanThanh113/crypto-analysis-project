FROM python:3.12-slim

# Copy uv binary from official uv image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

# System dependencies
# libgomp1 is needed by LightGBM runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    ca-certificates \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/ml

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Copy requirements first for Docker layer cache
COPY requirements.txt ./

# Install Python dependencies into system Python
RUN uv pip install --system -r requirements.txt

# Copy ML code
COPY train_model.py ./
COPY predict_latest.py ./
COPY mlflow_utils.py ./
COPY feature_contract.py ./
COPY strategy_config.py ./
COPY time_split.py ./
COPY feature_list.yml ./

# Local artifacts folder.
# In production/Kestra, mount this folder or upload artifacts to GCS.
RUN mkdir -p artifacts

CMD ["sh", "-c", "echo 'ML image ready. Example: python train_model.py --config feature_list.yml --artifact-dir artifacts'"]
