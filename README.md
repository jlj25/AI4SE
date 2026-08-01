# NJUSE Coding Agent Harness

> Spec-Driven, Subagent-Built, Human-Owned.
>
> 以**治理（Governance）为核心深度**的编码智能体工具，治理层为确定性代码，移除真实 LLM 后仍可用 Mock 单测验证。
>
> **线上部署**：http://116.62.78.157:8000

## 项目简介

本项目构建一个 coding agent harness，核心架构为一条确定性管道：

```
用户输入 → 组织上下文 → 调用 LLM → 解析动作 → 治理管道 → 工具执行 → 反馈注入 → 停机判断
```

治理管道由三阶段串联组成（本项目深度贡献）：

```
ScopeFence（范围围栏，硬拦截）→ DangerClassifier（危险分级）→ HITLGate（人工审批门）
```

- **ScopeFence**：检查路径是否在允许目录内、是否触碰受保护路径（`.git/`、`.env`），路径穿越攻击通过 `Path.resolve()` 解析后拦截。绝对边界，不可审批放行。
- **DangerClassifier**：对通过围栏的动作分级（SAFE/WARNING/DANGEROUS），正则模式匹配，取最高风险等级。规则从 YAML 配置加载。
- **HITLGate**：有限状态机，仅 DANGEROUS 时激活。**fail-closed** 语义：无决策时直接判 DENIED。

所有核心机制可用 MockLLM 离线测试，无需网络或真实模型。107 个测试全通过。

## 安装

### 后端（Python 3.12+）

```bash
# 安装 uv（如未安装）
pip install uv

# 同步依赖（含开发依赖）
uv sync --extra dev
```

### 前端（Node.js 20+）

```bash
cd frontend
npm install
```

## 运行

### 测试 / Lint / 类型检查

```bash
uv run pytest -xvs           # 全量测试（107 个）
uv run ruff check .          # Lint
uv run mypy .                # 类型检查
```

运行顺序：`ruff check .` → `mypy .` → `pytest -xvs`

### 演示脚本（离线，无需 LLM）

```bash
uv run python demo/run_demo.py
```

### 启动后端 API

```bash
uv run uvicorn src.api.main:create_app --factory --host 0.0.0.0 --port 8000
```

访问 `http://localhost:8000/api/health` 验证。

### 启动前端开发服务器

```bash
cd frontend
npm run dev
```

访问 `http://localhost:5173`，前端通过 Vite 代理连接后端。

### 前端构建

```bash
cd frontend
npm run build    # 产物在 frontend/dist/
```

## 分发命令

### 线上部署（阿里云 ECS）

已部署到阿里云 ECS（Ubuntu 22.04, 2核2G），裸机部署（无 Docker）：

- **WebUI 地址**：http://116.62.78.157:8000
- **健康检查**：http://116.62.78.157:8000/api/health
- **部署方式**：Python 3.12 + Node.js 20 + uvicorn，前端静态文件由 FastAPI 托管
- **部署架构**：FastAPI 单进程（uvicorn 单 worker），前端构建产物在 `frontend/dist/`，通过 `STATIC_DIR` 环境变量挂载

部署步骤见 `deploy_baremetal.sh`。

### Docker 部署（备选）

```bash
# 构建镜像
docker build -t njuse-agent .

# 通过 docker-compose 启动
docker compose up
```

### CI/CD

GitHub Actions（`.github/workflows/ci.yml`）：每次 push 到 main 自动运行：

```
ruff check . → mypy . → pytest -xvs
```

CI 执行记录：https://github.com/jlj25/AI4SE/actions

### 接入真实 LLM（可选）

在项目根目录创建 `.env` 文件：

```env
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.njusehub.ai/v1
LLM_MODEL=njusehub/glm-5.2
```

> 不配置 `.env` 时，所有核心机制仍可用 MockLLM 离线测试。

## 目录结构

```
njuse/
├── SPEC.md                    # 设计规范文档
├── PLAN.md                    # 17 个 TDD Task 实现计划
├── REFLECTION.md              # 反思报告
├── AGENTS.md                  # 项目规范（uv/ruff/mypy/pytest 命令）
├── pyproject.toml             # Python 项目配置
├── uv.lock                    # 依赖锁定
├── Dockerfile                 # 多阶段构建
├── docker-compose.yml         # 容器编排
├── .gitlab-ci.yml             # CI pipeline
├── .dockerignore
├── config/
│   └── config.yaml            # 默认配置（危险规则、允许目录等）
├── src/
│   ├── types.py               # 核心类型（Action/ToolResult/FeedbackSignal/Message）
│   ├── agent/
│   │   └── loop.py            # Agent 主循环
│   ├── llm/
│   │   ├── base.py            # LLMClient ABC
│   │   └── mock.py            # MockLLMClient（离线测试用）
│   ├── parser/
│   │   └── action_parser.py   # tool_code 代码块解析
│   ├── governance/            # 治理管道（深度维度）
│   │   ├── scope.py           # ScopeFence（范围围栏）
│   │   ├── classifier.py      # DangerClassifier（危险分级）
│   │   ├── hitl.py            # HITLGate（人工审批门）
│   │   └── pipeline.py        # GovernancePipeline（三阶段串联）
│   ├── tools/
│   │   ├── base.py            # Tool ABC
│   │   ├── dispatcher.py      # ToolDispatcher
│   │   ├── fs.py              # ReadFile/WriteFile/ListDir 工具
│   │   └── shell.py           # ShellTool
│   ├── feedback/
│   │   ├── validators.py      # Validator ABC + ExitCode/OutputContains 验证器
│   │   └── loop.py            # FeedbackLoop（信号注入上下文）
│   ├── memory/
│   │   └── store.py           # MemoryStore（关键词选择性检索）
│   ├── credentials/
│   │   └── manager.py         # CredentialManager（环境变量 + .env）
│   ├── config/
│   │   └── loader.py          # ConfigLoader（YAML 配置加载）
│   └── api/
│       ├── main.py            # FastAPI 应用工厂
│       ├── routes.py          # REST 路由（/health, /approve）
│       └── ws.py              # WebSocket 端点
├── tests/                     # 107 个测试
│   ├── test_types.py
│   ├── test_demo.py           # DEMO1-3 集成测试
│   ├── test_integration.py    # 端到端集成测试
│   ├── governance/
│   ├── tools/
│   ├── feedback/
│   ├── memory/
│   ├── credentials/
│   ├── config/
│   ├── llm/
│   ├── parser/
│   ├── agent/
│   └── api/
├── frontend/                  # React + Vite + TypeScript
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api.ts
│   │   ├── ws.ts
│   │   ├── components/
│   │   │   ├── ChatView.tsx
│   │   │   └── ApprovalDialog.tsx
│   │   └── index.css
│   ├── package.json
│   └── vite.config.ts
└── demo/
    └── run_demo.py            # 演示脚本
```

## 安全边界说明

### 治理管道三阶段

| 阶段 | 机制 | 行为 | 可审批放行 |
|------|------|------|------------|
| 1 | ScopeFence | OUT_OF_SCOPE / PROTECTED → 硬阻断 | ❌ 否 |
| 2 | DangerClassifier | SAFE → 放行 / WARNING → 放行 / DANGEROUS → 进 HITL | — |
| 3 | HITLGate | approve → 放行 / deny → 阻断 / modify → 替换动作 / 无决策 → DENIED | ✅ 是 |

### fail-closed 语义

DANGEROUS 动作若无可用决策（异步超时、网络断开等），HITLGate 直接判为 DENIED 并返回 None。系统不会"默认放行"危险操作。

### 确定性代码，非提示词

治理逻辑全部为确定性代码函数（正则匹配、路径解析、状态机），不依赖 LLM 遵从系统提示词。测试标准：移除真实 LLM，机制仍可单测。

### 受保护路径

默认配置保护 `.git/` 和 `.env`，可通过 `config/config.yaml` 声明式扩展。

### 凭据安全

API key 从环境变量或 `.env` 文件读取，不硬编码在代码中，不写入日志。`.env` 已在 `.gitignore` 和 `.dockerignore` 中排除。
