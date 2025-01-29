FROM python:3.12-slim AS builder

WORKDIR /app

RUN echo "deb http://deb.debian.org/debian/ stable main contrib non-free" > /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends libjemalloc2 git && \
    rm -rf /var/lib/apt/lists/*

ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2

RUN pip install --no-cache-dir poetry && poetry config virtualenvs.create false

RUN poetry --version

COPY pyproject.toml poetry.lock ./

RUN if [ ! -f poetry.lock ]; then poetry lock; fi

RUN poetry install --no-root --no-interaction

FROM python:3.12-slim

WORKDIR /app

RUN echo "deb http://deb.debian.org/debian/ stable main contrib non-free" > /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends libjemalloc2 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local /usr/local
COPY . .

CMD ["python", "main.py"]
