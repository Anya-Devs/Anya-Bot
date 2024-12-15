FROM python:3.10-alpine AS builder

WORKDIR /app
RUN apk update && apk add --no-cache \
    libjemalloc \
    git \
    build-base && \
    rm -rf /var/cache/apk/*

RUN pip install poetry
COPY requirements.txt .
RUN poetry config virtualenvs.create false && \
    pip install --no-cache-dir -r requirements.txt

FROM python:3.10-alpine

WORKDIR /app
RUN apk update && apk add --no-cache \
    libjemalloc && \
    rm -rf /var/cache/apk/*

ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2

COPY --from=builder /app /app
COPY .github/.env ./.env

RUN python -OO -m compileall . && \
    rm -rf /root/.cache /app/.git

CMD ["python", "main.py"]
