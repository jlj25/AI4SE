## Task 16: Docker + CI

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.gitlab-ci.yml`

- [ ] **Step 1: 创建 Dockerfile**

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装 uv
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

# 复制源码
COPY src/ ./src/
COPY config/ ./config/

# 构建前端
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/ .
RUN npm ci && npm run build

FROM python:3.12-slim
WORKDIR /app
COPY --from=0 /app/ ./
COPY --from=frontend-builder /app/frontend/dist ./static/
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "src.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 创建 docker-compose.yml**

```yaml
# docker-compose.yml
version: "3.9"
services:
  agent:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENAI_BASE_URL=${OPENAI_BASE_URL:-https://api.njusehub.ai/v1}
      - LLM_MODEL=${LLM_MODEL:-njusehub/glm-5.2}
    volumes:
      - ./config:/app/config:ro
```

- [ ] **Step 3: 创建 .dockerignore**

```
# .dockerignore
.git
.gitignore
__pycache__
*.pyc
.env
*.key
node_modules
frontend/node_modules
.venv
```

- [ ] **Step 4: 创建 .gitlab-ci.yml**

```yaml
# .gitlab-ci.yml
stages:
  - test

unit-test:
  stage: test
  image: python:3.12-slim
  before_script:
    - pip install uv
    - uv sync --frozen
  script:
    - uv run ruff check .
    - uv run mypy .
    - uv run pytest -xvs
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "main"
```

- [ ] **Step 5: 验证 Docker 构建 + 提交**

```bash
docker build -t njuse-agent .
git add Dockerfile docker-compose.yml .dockerignore .gitlab-ci.yml
git commit -m "feat: Docker 多阶段构建 + GitLab CI（ruff→mypy→pytest）"
```

---