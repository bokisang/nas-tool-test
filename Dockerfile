FROM node:22.15.1-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11.11-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    AI_NAS_DATA_DIR=/app/data \
    AI_NAS_SOURCE_DIR=/source
WORKDIR /app
COPY backend/pyproject.toml backend/README.md ./
COPY backend/src ./src
RUN pip install --no-cache-dir . && \
    useradd --create-home --uid 1000 --shell /usr/sbin/nologin ainas && \
    mkdir -p /app/static /app/data /source && \
    chown -R ainas:ainas /app
COPY --from=frontend-build /build/frontend/dist /app/static
USER ainas
EXPOSE 8080
CMD ["uvicorn", "ainas.main:app", "--host", "0.0.0.0", "--port", "8080"]
