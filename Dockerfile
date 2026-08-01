FROM python:3.12-slim AS backend

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra dev

COPY src/ ./src/
COPY config/ ./config/
COPY tests/ ./tests/

FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim AS final

WORKDIR /app

RUN pip install uv

COPY --from=backend /app/ ./
COPY --from=frontend-builder /app/frontend/dist ./static/

EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn src.api.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
