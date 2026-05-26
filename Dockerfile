# syntax=docker/dockerfile:1
FROM python:3.12-slim

LABEL maintainer="VideoReverse"
LABEL description="Universal Video-to-Prompt Pipeline"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/
COPY utils/ ./utils/
COPY tests/ ./tests/
COPY scripts/ ./scripts/
COPY web/ ./web/

ENV PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["python", "-m"]
CMD ["src.main", "--help"]
