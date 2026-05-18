# syntax=docker/dockerfile:1
FROM node:22-alpine

LABEL maintainer="VideoReverse"
LABEL description="Universal Video-to-Prompt Pipeline"

RUN apk add --no-cache \
    ffmpeg \
    bash \
    && npm install -g peepshow

WORKDIR /app

COPY package.json ./
RUN npm ci --only=production

COPY src/ ./src/
COPY config/ ./config/
COPY utils/ ./utils/

ENV NODE_ENV=production

ENTRYPOINT ["node", "src/main.js"]
CMD ["--help"]