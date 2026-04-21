# syntax=docker/dockerfile:1.7

ARG NODE_VERSION=22

FROM node:${NODE_VERSION}-bookworm AS frontend-builder
WORKDIR /workspace/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend .
# SvelteKit's `$env/dynamic/public` is resolved at BUILD TIME for adapter-static
# (no SSR at runtime), reading from process.env — NOT from .env.production.
# We declare each PUBLIC_* var as ARG with a sensible default so process.env
# always has the right value during `npm run build`. Render-passed build args
# (if any) override these defaults; otherwise the bake-in value wins.
#
# PUBLIC_SUPABASE_URL is the Supabase project URL — public, not a secret.
# PUBLIC_SUPABASE_ANON_KEY is the public RLS-gated anon key — safe to expose,
#   committed to frontend/.env.production for local dev parity.
# Secrets (service role key, MapTiler key) stay out of defaults; they come
#   in via Render-passed build args.
ARG PUBLIC_DEPLOYMENT_TARGET=supabase
ARG PUBLIC_SUPABASE_URL=https://gfmdziplticfoakhrfpt.supabase.co
ARG PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmbWR6aXBsdGljZm9ha2hyZnB0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc2MDYzMjIsImV4cCI6MjA4MzE4MjMyMn0.Liz22BqK2qfHBcIsIJxGTT4VvMzfBE_yRFraVrUPKq4
ARG PUBLIC_MUCKROCK_ENABLED=true
ARG VITE_API_URL=/api
ARG PUBLIC_MAPTILER_API_KEY=''
ENV PUBLIC_DEPLOYMENT_TARGET=${PUBLIC_DEPLOYMENT_TARGET}
ENV PUBLIC_SUPABASE_URL=${PUBLIC_SUPABASE_URL}
ENV PUBLIC_SUPABASE_ANON_KEY=${PUBLIC_SUPABASE_ANON_KEY}
ENV PUBLIC_MUCKROCK_ENABLED=${PUBLIC_MUCKROCK_ENABLED}
ENV VITE_API_URL=${VITE_API_URL}
ENV PUBLIC_MAPTILER_API_KEY=${PUBLIC_MAPTILER_API_KEY}
RUN npm run build

FROM python:3.13-slim AS runtime
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
