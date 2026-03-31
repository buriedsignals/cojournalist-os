# syntax=docker/dockerfile:1.7

ARG NODE_VERSION=22

FROM node:${NODE_VERSION}-bookworm AS frontend-builder
WORKDIR /workspace/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend .
ARG VITE_API_URL=''
ARG PUBLIC_MAPTILER_API_KEY
ENV VITE_API_URL=${VITE_API_URL}
ENV PUBLIC_MAPTILER_API_KEY=${PUBLIC_MAPTILER_API_KEY}
RUN npm run build

FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /workspace

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential curl && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY automation/SETUP_AGENT.md ./backend/app/SETUP_AGENT.md
COPY automation/setup.sh ./backend/app/setup.sh
COPY automation/sync-upstream.yml ./backend/app/sync-upstream.yml
COPY deploy/render/render.yaml ./backend/app/render.yaml
COPY deploy/SETUP.md ./backend/app/SETUP.md
COPY --from=frontend-builder /workspace/frontend/build ./backend/app/frontend_client

ENV HOST=0.0.0.0 \
    PORT=7860

EXPOSE 7860
WORKDIR /workspace/backend

CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"
