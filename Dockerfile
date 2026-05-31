# syntax=docker/dockerfile:1
FROM python:3.12-slim

LABEL maintainer="Venkata-Manoj"
LABEL description="Universal Video-to-Prompt Pipeline — deconstruct any video into AI prompts for 8+ models"
LABEL org.opencontainers.image.source="https://github.com/Venkata-Manoj/videoreverse"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.documentation="https://github.com/Venkata-Manoj/videoreverse/tree/main/docs"

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
