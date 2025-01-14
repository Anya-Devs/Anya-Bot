FROM python:3.10-slim as builder

RUN echo "deb http://deb.debian.org/debian/ stable main contrib non-free" > /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends libjemalloc2 git && \
    rm -rf /var/lib/apt/lists/*

ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2

RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

FROM python:3.10-slim

RUN echo "deb http://deb.debian.org/debian/ stable main contrib non-free" > /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends libjemalloc2 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local /usr/local

WORKDIR /app
COPY . .

CMD ["python", "main.py"]
