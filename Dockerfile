# syntax=docker/dockerfile:1
#
# Self-contained image: content, search index and the embedding model are all baked in at build
# time, so pods are stateless and need no network at runtime (see docs/ARCHITECTURE.md).

# ---- 1. Tailwind CSS (Node is only needed here) -------------------------------------------------
FROM node:22-slim AS css
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY assets ./assets
COPY src/docx86/templates ./src/docx86/templates
RUN npm run build:css

# ---- 2. Python deps + search index (downloads the embedding model once) ------------------------
FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-default-groups --no-install-project
COPY src ./src
COPY content ./content
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-default-groups
ENV DOCX86_MODEL_CACHE_DIR=/opt/models DOCX86_INDEX_DIR=/app/index
# The runtime user is not root: make the baked-in model cache world-readable (HF files are 0600).
RUN .venv/bin/docx86 build-index && .venv/bin/docx86 validate \
    && .venv/bin/docx86 evidence check --no-sources && chmod -R a+rX /opt/models

# ---- 3. Runtime ---------------------------------------------------------------------------------
FROM python:3.13-slim
RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /app/.venv ./.venv
COPY --from=build /app/src ./src
COPY --from=build /app/content ./content
COPY --from=build /app/index ./index
COPY --from=build /opt/models /opt/models
COPY --from=css /build/src/docx86/static/app.css ./src/docx86/static/app.css

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    HF_HUB_OFFLINE=1 \
    DOCX86_MODEL_CACHE_DIR=/opt/models \
    DOCX86_MODEL_OFFLINE=1 \
    DOCX86_INDEX_DIR=/app/index

USER 10001:10001
EXPOSE 8000
# One worker per pod: scale with replicas, not processes (the pod CPU limit is the budget).
CMD ["uvicorn", "docx86.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--no-server-header", "--proxy-headers", "--forwarded-allow-ips", "*"]
