# syntax=docker/dockerfile:1
FROM python:3.12.8-slim AS base

LABEL maintainer="Venkata-Manoj"
LABEL description="Universal Video-to-Prompt Pipeline — deconstruct any video into AI prompts for 8+ models"
LABEL org.opencontainers.image.source="https://github.com/Venkata-Manoj/videoreverse"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.documentation="https://github.com/Venkata-Manoj/videoreverse/tree/main/docs"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e .

COPY config/ ./config/
COPY utils/ ./utils/
COPY web/ ./web/

ENV PYTHONDONTWRITEBYTECODE=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

ENTRYPOINT ["python", "-m"]
CMD ["src.main", "--help"]
