# =========================
# Stage 1: Builder
# =========================
FROM python:3.12-slim AS builder
WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN echo "deb http://deb.debian.org/debian stable main contrib non-free" > /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends git libjemalloc2 && \
    rm -rf /var/lib/apt/lists/*

# Use jemalloc for better memory efficiency
ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2

# Install Poetry (no venv)
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry --version

# Copy source
COPY . .

# Run setup script (if present)
RUN if [ -f data/setup.py ]; then python data/setup.py; fi

# Install dependencies via Poetry
RUN if [ -f pyproject.toml ]; then \
        poetry install --no-root --no-interaction --no-ansi; \
    else \
        echo "No pyproject.toml found, skipping Poetry install"; \
    fi

# =========================
# Stage 2: Final image
# =========================
FROM python:3.12-slim
WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies
RUN echo "deb http://deb.debian.org/debian stable main contrib non-free" > /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends libjemalloc2 && \
    rm -rf /var/lib/apt/lists/*

# Use jemalloc
ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2

# Copy app from builder
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app

# Load env variables at runtime (not build time)
# The .env file will be injected using docker-compose
CMD ["python", "main.py"]
