FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libjemalloc2 git && rm -rf /var/lib/apt/lists/*
ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2

# Install Poetry first, then install dependencies
RUN pip install --no-cache-dir poetry
RUN poetry config virtualenvs.create false

# Copy only the requirements first to leverage Docker cache
COPY pyproject.toml poetry.lock ./

# Install dependencies using poetry
RUN poetry install --no-dev --no-interaction --no-ansi

# Copy the rest of the app code
COPY . .

CMD ["python", "-Xnoassert", "main.py"]
