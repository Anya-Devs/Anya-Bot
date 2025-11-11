# =========================
# Stage 1: Builder - Install build dependencies
# =========================
FROM python:3.12-slim AS builder

# Install system dependencies for building Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends git gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry

WORKDIR /app
COPY pyproject.toml poetry.lock* ./

# Install all dependencies
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root && \
    rm -rf /root/.cache/pip/*

# =========================
# Stage 2: Runtime - Lightweight final image
# =========================
FROM python:3.12-slim

WORKDIR /app

# Install runtime libraries only
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libjemalloc2 && \
    rm -rf /var/lib/apt/lists/*

# Use jemalloc for better memory efficiency
ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2

# Copy installed dependencies and app code
COPY --from=builder /usr/local /usr/local
COPY . .

# Run setup script if present
RUN if [ -f data/setup.py ]; then python data/setup.py; fi

# Clean caches and bytecode to reduce image size
RUN find /usr/local -type d -name '__pycache__' -exec rm -rf {} + && \
    find /usr/local -name '*.py[co]' -delete && \
    rm -rf /root/.cache /tmp/*

# Default startup command
CMD ["python", "main.py"]