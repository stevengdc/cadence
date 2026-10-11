FROM node:22-bookworm-slim AS ui
WORKDIR /ui
COPY ui/package*.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg tini ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=ui /ui/dist ./web
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=UTC
ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["python","app.py","--serve"]
