# syntax=docker/dockerfile:1

# --- stage 1: minify the browser JS (sources in git stay readable) -------------------------
FROM node:22-alpine AS assets
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY tools/minify.mjs tools/minify.mjs
COPY static static
RUN node tools/minify.mjs static

# --- stage 2: runtime -------------------------------------------------------------------------
FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8888
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY run.py ./
COPY controllers controllers
COPY modules modules
COPY templates templates
COPY models/*.glb models/
COPY --from=assets /build/static static

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin radient
USER 10001
EXPOSE 8888
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/main' % os.environ.get('PORT', '8888'), timeout=2)"
CMD ["python", "run.py"]
