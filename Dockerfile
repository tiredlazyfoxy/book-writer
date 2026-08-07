# BookWriter — all-in-one image: nginx (:80) + uvicorn (127.0.0.1:8185) under
# supervisord. Build context is the REPO ROOT:
#   docker build -t iezious/bookwriter:latest .

# ---------------------------------------------------------------------------
# Stage 1 — build the five-entry Vite bundle.
# ---------------------------------------------------------------------------
FROM node:22-alpine AS web

WORKDIR /app

# Lockfile first: this is what makes the dependency layer cacheable.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2 — runtime.
# Full python:3.13, not -slim: `git` is needed to install the llm-client VCS
# dependency and `curl` is needed by the compose healthcheck.
# ---------------------------------------------------------------------------
FROM python:3.13

RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx supervisor \
 && rm -rf /var/lib/apt/lists/*

# Required, not cosmetic: Debian's nginx.conf includes BOTH conf.d/*.conf and
# sites-enabled/*, so the stock default site would collide on `listen 80`.
RUN rm -f /etc/nginx/sites-enabled/default

# Cache-friendly dependency layer. The stub app/__init__.py is deliberate:
# [tool.setuptools.packages.find] include = ["app*"] makes an install with zero
# packages present fragile, so the stub gives setuptools something to find.
# uvicorn later runs with cwd /app and imports app.main off the filesystem, so
# the installed distribution itself is not needed once its dependencies are in
# place — hence the stub and the egg-info are removed in the same layer.
WORKDIR /app
COPY backend/pyproject.toml ./
RUN mkdir -p app && touch app/__init__.py \
 && pip install --no-cache-dir . \
 && rm -rf app *.egg-info
COPY backend/ .

COPY --from=web /app/dist /usr/share/nginx/html
COPY nginx/prod.conf /etc/nginx/conf.d/bookwriter.conf
COPY docker/supervisord.conf /etc/supervisord.conf

RUN mkdir -p /app/data

# Both are required. Setting only BOOKWRITER_DB_PATH leaves the LanceDB vector
# index outside the mounted volume, where it is silently destroyed on every
# container replace. Note LANCEDB_DIR is BARE — that settings field has no
# BOOKWRITER_ prefix.
ENV BOOKWRITER_DB_PATH=/app/data/bookwriter.db
ENV LANCEDB_DIR=/app/data/vector

# No entrypoint script and no schema bootstrap: the app is designed to boot
# with zero tables and be finished in the browser via the first-run setup API.
EXPOSE 80
CMD ["supervisord", "-c", "/etc/supervisord.conf"]
