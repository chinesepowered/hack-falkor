# ---- frontend
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- app
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 CAPYBRAIN_CACHE=/app/.cache
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# bake the embedding model into the image so the first start works offline
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/app/.cache/fastembed')"
COPY capybrain/ capybrain/
COPY data/ data/
COPY scripts/ scripts/
COPY --from=web /web/dist frontend/dist
EXPOSE 8000
CMD ["uvicorn", "capybrain.api:app", "--host", "0.0.0.0", "--port", "8000"]
