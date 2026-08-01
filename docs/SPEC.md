# SPEC.md — NJUSE Coding Agent Harness

> Spec-Driven, Subagent-Built, Human-Owned.
>
> 本文档由 brainstorming 技能协作生成，经用户逐节签字确认。

---

## 一、问题陈述

### 1.1 要解决什么问题

当 LLM 能完成大部分编码工作时，工程师的真正价值落在 harness 这层工程。现有 coding agent 有两个普遍问题：

1. **治理是提示词而非代码**：在系统提示里写"不要执行危险命令"，是否执行取决于 LLM 是否遵从，无法用确定性测试验证。每次结果可能不同。
2. **缺乏 HITL 闭环**：agent 要么全自动（危险），要么全手动（低效），缺少"危险动作暂停审批"的中间态。

### 1.2 目标用户

- 想要自主编码助手但不愿冒系统被破坏风险的开发者
- 学习 agent harness 内部机制的工程师
- 需要 CI/CD 中带安全护栏的自动修复场景

### 1.3 为什么值得做

本项目构建一个 coding agent harness，其治理层是**确定性代码**：危险动作拦截、HITL 审批状态机、范围围栏均为代码实现，移除真实 LLM 后仍可用 mock 单测验证。重点维度是**治理**，其余五个维度（决策/工具/反馈/记忆/配置）有可运行最低实现。这直接回应了"当 LLM 能完成大部分编码工作时，工程师的真正价值在哪里"这一命题——价值在 harness 这层工程。

---

## 二、用户故事

遵循 INVEST 原则（Independent, Negotiable, Valuable, Estimable, Small, Testable）。

| # | 用户故事 | INVEST |
|---|---------|--------|
| US1 | 作为开发者，我想给 agent 一个编码任务，让它自主读写文件、跑测试，这样我不用做机械工作 | I✓ N✓ V✓ E✓ S✓ T✓ |
| US2 | 作为开发者，我想让 agent 在执行危险命令（rm -rf、git push 等）前暂停并请求我审批，这样它不会破坏我的系统 | I✓ N✓ V✓ E✓ S✓ T✓ |
| US3 | 作为开发者，我想在 WebUI 实时观看 agent 的每一步，并在危险动作时弹出审批卡片，这样我能监控和干预 | I✓ N✓ V✓ E✓ S✓ T✓ |
| US4 | 作为开发者，我想让 agent 改完代码后自动跑测试，并根据失败信号自我修正，这样产出可用代码 | I✓ N✓ V✓ E✓ S✓ T✓ |
| US5 | 作为开发者，我想用声明式 YAML 配置治理规则（允许目录、禁止命令、风险等级），这样不改代码就能调整安全边界 | I✓ N✓ V✓ E✓ S✓ T✓ |
| US6 | 作为开发者，我想 harness 核心机制能用 mock LLM 跑确定性单测，这样我能验证治理确实生效而非依赖 LLM 遵从 | I✓ N✓ V✓ E✓ S✓ T✓ |

---

## 三、功能规约

按模块拆分，每项描述输入/行为/输出/边界条件/错误处理。

### 3.1 Agent 主循环（决策模块）

- **输入**：编码任务字符串（如"给 utils.py 加一个 add 函数并写测试"）
- **行为**：组织上下文（记忆检索 + 任务 + 历史步骤）→ 调 LLM → 解析动作 → 治理管道 → 执行 → 反馈回灌 → 停机判断
- **输出**：AgentResult（含全部步骤记录）
- **边界条件**：max_steps 上限（默认 50）；LLM 宣告完成则停机
- **错误处理**：LLM 调用失败重试 3 次；动作解析失败回灌"格式错误"信号让 LLM 重试；达 max_steps 优雅停机

### 3.2 LLM 抽象层

- **输入**：messages 列表（role + content）
- **行为**：调用 LLM 供应商的 chat completion 接口
- **输出**：LLM 响应字符串
- **边界条件**：超时 30s
- **错误处理**：网络错误重试 3 次（指数退避）；超时后抛 LLMTimeoutError
- **可注入 mock**：`MockLLMClient` 按脚本返回预设响应，用于离线单测

### 3.3 治理管道（重点维度，详见 §十一）

- **输入**：Action 对象
- **行为**：范围围栏检查 → 危险分类 → HITL 审批门（仅危险动作）
- **输出**：GovernanceResult（blocked + 可能被修改的 action + reason + classification）
- **边界条件**：范围围栏硬拦截（不可审批放行）；HITL 仅对 DANGEROUS 级别触发
- **错误处理**：路径解析失败视为 OUT_OF_SCOPE；HITL 超时由配置决定（默认无限等待）

### 3.4 工具分发

- **输入**：Action（tool 名 + args）
- **行为**：按 tool 名分发到对应执行器
- **输出**：ToolResult（success + stdout + stderr + exit_code）
- **边界条件**：未知 tool 名返回错误
- **错误处理**：工具执行超时 60s 后中止；执行异常捕获并返回 ToolResult(success=False)

### 3.5 反馈闭环

- **输入**：Action + ToolResult
- **行为**：按工具名选对应校验器，解析产物，客观判定
- **输出**：FeedbackSignal（success + message + details）
- **边界条件**：无对应校验器时默认 exit_code==0 即成功
- **错误处理**：校验器解析失败返回 FeedbackSignal(success=False, message="parse error")

### 3.6 记忆

- **输入**：store(key, value, tags) / retrieve(query, top_k)
- **行为**：JSON 文件存储；关键词 + 标签匹配检索
- **输出**：MemoryEntry 列表
- **边界条件**：top_k 默认 3
- **错误处理**：存储失败抛 IOError；检索无结果返回空列表

### 3.7 配置

- **输入**：YAML 配置文件路径
- **行为**：加载、校验字段、返回强类型 AgentConfig
- **输出**：AgentConfig
- **边界条件**：缺失字段用默认值
- **错误处理**：YAML 解析错误抛 ConfigError；字段类型不符抛 ValidationError

### 3.8 WebUI

- **输入**：任务文本（HTTP POST）、审批决策（WebSocket）
- **行为**：实时展示 agent 步骤流；危险动作弹出审批卡片
- **输出**：步骤事件流（WebSocket 推送）
- **边界条件**：同时只允许一个 agent 会话运行
- **错误处理**：WebSocket 断线自动重连；agent 崩溃显示错误状态

### 3.9 凭据管理

- **输入**：API key（隐藏输入）
- **行为**：存储到 OS 钥匙串；查看状态不回显明文
- **输出**：is_configured() 返回 bool
- **边界条件**：无钥匙串环境降级为加密文件
- **错误处理**：钥匙串写入失败抛 CredentialError

---

## 四、非功能性需求

| 类别 | 需求 | 验收方式 |
|------|------|---------|
| **安全** | 凭据不入 git/日志/WebUI 回显；工作目录范围围栏强制；危险命令代码拦截 | grep 仓库无明文 key；单测验证围栏与拦截 |
| **性能** | 单步 LLM 调用 < 30s（含治理管道开销 < 100ms）；WebSocket 事件延迟 < 500ms | 治理管道单测断言耗时；集成测试量延迟 |
| **可靠性** | LLM 调用失败重试 3 次；工具执行超时 60s 后中止；达 max_steps 优雅停机 | 单测 mock LLM 抛异常验证重试；单测验证停机 |
| **可观测性** | 每步记录结构化日志（step/thought/action/governance/feedback），不含凭据；WebUI 实时展示 | 日志格式校验；WebUI 事件流验证 |
| **可用性** | WebUI 首次运行引导录入 key；审批卡片清晰显示危险理由；步骤流自动滚动 | 手动验收 |
| **可测试性** | 核心机制（治理/工具/反馈/记忆/配置）均可用 mock LLM 单测，不依赖网络 | mock-LLM 单测全绿 |

---

## 五、系统架构

### 5.1 组件图

```
┌─────────────────────────────────────────────────────────────────┐
│                        WebUI (React + Open Design)              │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌───────────┐  │
│  │ 任务输入  │  │ 步骤实时流    │  │ 审批卡片   │  │ 日志/历史  │  │
│  └────┬─────┘  └──────▲───────┘  └─────▲─────┘  └─────▲─────┘  │
└───────┼───────────────┼─────────────────┼──────────────┼───────┘
        │ HTTP(任务)     │ WebSocket(事件)  │ WebSocket(决策)│
        ▼               │                 │               │
┌───────┴───────────────┴─────────────────┴───────────────┴─────┐
│                    API 层 (FastAPI + WebSocket)                  │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ 任务端点    │  │ 事件广播器    │  │ 审批决策接收器          │  │
│  └─────┬──────┘  └──────▲───────┘  └───────────▲────────────┘  │
└────────┼────────────────┼──────────────────────┼───────────────┘
         │                │                      │
         ▼                │                      │
┌─────────────────────────┴──────────────────────┴───────────────┐
│                    Harness 内核 (Python)                         │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Agent 主循环                                            │    │
│  │  组织上下文 → 调LLM → 解析动作 → 治理管道 → 执行 → 反馈 → 停机│    │
│  └──┬──────────┬──────────┬───────────┬──────────┬─────────┘    │
│     ▼          ▼          ▼           ▼          ▼              │
│  ┌──────┐  ┌──────┐  ┌──────────────────────┐  ┌──────┐        │
│  │LLM   │  │工具   │  │ 治理管道 (深度贡献)    │  │反馈  │        │
│  │抽象层 │  │分发   │  │范围围栏→危险分类→HITL门│  │闭环  │        │
│  └──┬───┘  └──┬───┘  └──────────────────────┘  └──┬───┘        │
│     │         │                                    │             │
│     ▼         ▼                                    ▼             │
│  ┌──────┐  ┌──────────┐                      ┌──────────┐       │
│  │真实   │  │文件/Shell/│                      │测试/Lint/│       │
│  │LLM   │  │构建测试   │                      │类型检查   │       │
│  │适配器 │  │工具集     │                      │校验器     │       │
│  ├──────┤  └──────────┘                      └──────────┘       │
│  │Mock  │                                                       │
│  │LLM   │  ┌──────────┐  ┌──────────┐                          │
│  └──────┘  │记忆存储   │  │配置加载器 │                          │
│            │(跨会话)   │  │(YAML规则) │                          │
│            └──────────┘  └──────────┘                          │
└──────────────────────────────────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
┌──────────────────┐                  ┌──────────────────┐
│ njusehub API     │                  │ 本地文件系统/Shell │
│ (OpenAI 兼容)    │                  │ (受限工作目录)    │
│ glm-5.2 等       │                  │                   │
└──────────────────┘                  └──────────────────┘
```

### 5.2 数据流

1. **用户提交任务**：WebUI → HTTP → API 层 → Agent 主循环启动
2. **每轮循环**：
   - 组织上下文（记忆检索 + 任务 + 历史步骤）→ 调 LLM → 解析出 Action
   - Action 进入治理管道：范围围栏检查 → 危险分类 → 若危险则 HITL 门暂停
   - HITL 暂停时：事件广播器经 WebSocket 推送审批卡片到 WebUI → 用户决策 → 回传内核
   - 审批通过（或动作安全）→ 工具分发执行 → 结果回灌
   - 反馈闭环：校验器解析执行产物（测试输出/lint）→ 客观判定 → 结果回灌给主循环
   - 停机判断：任务完成 / 达最大步数 / 不可恢复错误
3. **全程实时**：每个阶段的事件经 WebSocket 流式推送到 WebUI

### 5.3 外部依赖

| 依赖 | 用途 | 性质 |
|------|------|------|
| njusehub API | 真实 LLM 调用（OpenAI 兼容 chat completion） | 运行时，需网络 |
| 本地文件系统/Shell | 工具执行（读写文件、跑命令、跑测试） | 运行时，受限范围 |
| Open Design | 前端设计系统 | 构建时 |
| keyring 库 | 凭据安全存储 | 运行时 |

### 5.4 关键设计原则

- **内核与内容物分离**：harness 内核（主循环/治理/工具/反馈/记忆/配置加载器）是纯代码，与提示词/规则文件/配置 YAML 分离
- **LLM 可注入**：`LLMClient` 是抽象基类，`RealLLMClient`（njusehub）和 `MockLLMClient`（单测）是实现
- **治理是代码**：治理管道的每个阶段是确定性函数，不依赖 LLM 遵从

---

## 六、数据模型

### 6.1 实体关系图

```
┌──────────┐     ┌──────────┐     ┌──────────────┐
│  Session  │1───*│  Step    │1───1│  Action      │
│──────────│     │──────────│     │──────────────│
│ id (uuid)│     │ id       │     │ tool: str    │
│ task: str│     │ session  │     │ args: dict   │
│ status   │     │ thought  │     │ thought: str │
│ created  │     │ created  │     └──────┬───────┘
│ ended    │     └────┬─────┘            │1
└──────────┘          │1                 │
                      │                  ▼
                 ┌────┴────────────┐  ┌──────────────┐
                 │ GovernanceResult│  │  ToolResult   │
                 │─────────────────│  │───────────────│
                 │ blocked: bool   │  │ success: bool│
                 │ reason: str     │  │ stdout: str  │
                 │ classification  │  │ stderr: str  │
                 └─────────────────┘  │ exit_code:int│
                                      └──────┬───────┘
                                             │1
                 ┌──────────────┐            │
                 │ FeedbackSignal│◄───────────┘1
                 │───────────────│
                 │ success: bool │
                 │ message: str  │
                 │ details: dict │
                 └───────────────┘

  ┌──────────────┐     ┌──────────────┐
  │ MemoryEntry  │     │  Decision     │
  │──────────────│     │───────────────│
  │ key: str     │     │ step_id: str  │
  │ value: str   │     │ verdict: enum │
  │ tags: [str]  │     │ modified_action│
  │ timestamp    │     │ created       │
  └──────────────┘     └───────────────┘
```

### 6.2 实体定义

| 实体 | 字段 | 约束 |
|------|------|------|
| **Session** | `id: UUID`, `task: str`, `status: enum(running/completed/failed/halted)`, `created_at`, `ended_at` | status 仅运行时一个为 running |
| **Step** | `id: UUID`, `session_id: FK`, `index: int`, `thought: str`, `created_at` | index 在 session 内递增唯一 |
| **Action** | `step_id: FK`, `tool: str`, `args: dict`, `thought: str` | tool 必须在已注册工具集中 |
| **GovernanceResult** | `step_id: FK`, `blocked: bool`, `action: Action?`, `reason: str`, `classification: Classification?` | blocked=true 时 action 为 None |
| **ToolResult** | `step_id: FK`, `success: bool`, `stdout: str`, `stderr: str`, `exit_code: int` | — |
| **FeedbackSignal** | `step_id: FK`, `success: bool`, `message: str`, `details: dict` | details 结构随工具类型变化 |
| **MemoryEntry** | `key: str`, `value: str`, `tags: list[str]`, `timestamp: str` | key 唯一 |
| **Decision** | `step_id: FK`, `verdict: enum(approve/deny/modify)`, `modified_action: Action?`, `created_at` | verdict=modify 时 modified_action 必填 |
| **AgentConfig** | `max_steps: int`, `scope: ScopeConfig`, `danger_rules: list[DangerRule]`, `llm: LLMConfig` | max_steps > 0 |

### 6.3 持久化

- **Session/Step/Action/Result**：SQLite 数据库（轻量、零配置、单文件），用于历史回溯
- **MemoryEntry**：JSON 文件存储（简单、可读、易迁移）
- **AgentConfig**：YAML 文件（声明式、人类可读）
- **凭据**：OS 钥匙串（见 §七），不落盘明文

---

## 七、凭据与分发设计

### 7.1 凭据威胁模型

| 威胁 | 攻击面 | 对策 |
|------|--------|------|
| key 硬编码进源码 | git 历史泄露 | 代码中零引用明文 key；`.gitignore` 排除配置文件 |
| key 存于明文配置文件 | 文件系统访问即可读取 | 主方案用 OS 钥匙串；`.env` 仅作 CI 备选并标注明文风险 |
| key 进环境变量 | 进程列表 / shell history 可见 | 不用命令行 `export`；`.env` 文件加载时标注风险 |
| key 写入日志 | 日志聚合泄露 | `CredentialManager.get()` 返回值禁止进入任何日志/事件载荷；日志中只记 `"key": "***configured***"` |
| key 在 WebUI 回显 | 浏览器开发者工具可见 | WebUI 只显示"已配置/未配置"状态，永不回显明文 |

### 7.2 凭据管理器

```python
class CredentialManager:
    """凭据安全存储：OS 钥匙串为主，加密文件为备选"""
    def __init__(self, service_name: str = "njuse-coding-agent"): ...

    def store(self, api_key: str) -> None:
        # 主路径：写入 OS 钥匙串（Windows Credential Manager）
        # 备选：带主密码的加密文件（用于 headless/CI 无钥匙串环境）

    def is_configured(self) -> bool:
        # 返回 bool，不回显明文

    def get(self) -> str | None:
        # 仅供 LLMClient 内部使用，返回值禁止进入日志/事件

    def update(self, new_key: str) -> None: ...    # 更新
    def clear(self) -> None: ...                    # 清除

    def interactive_setup(self) -> None:
        # 首次运行引导：getpass 隐藏输入，确认后存储
        # 查看状态时只显示 "已配置" / "未配置"
```

**首次运行流程**：
1. agent 启动时检查 `is_configured()`
2. 若未配置 → 引导用户通过 WebUI 或终端 `getpass` 录入 key
3. 录入后调用 `store()` 写入钥匙串
4. 后续运行自动从钥匙串读取

**CI 环境**：无钥匙串时，从 `.env` 文件加载（CI 变量注入），SPEC 中标注此路径的明文风险。

### 7.3 分发设计（Docker 镜像）

**Dockerfile 结构**（多阶段构建）：

```dockerfile
# Stage 1: 前端构建
FROM node:20-alpine AS frontend
WORKDIR /app/web
COPY web/ .
RUN npm ci && npm run build

# Stage 2: 后端 + 前端静态文件
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen
COPY src/ ./src/
COPY --from=frontend /app/web/dist ./web/dist
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

**用户获取与运行**：
```bash
docker pull <registry>/njuse-coding-agent:latest
docker run -p 8000:8000 \
  -v $(pwd)/workspace:/workspace \
  -v keyring_data:/keyring \
  njuse-coding-agent:latest
```

**目标机器上 key 的安全配置**：
1. 首次 `docker run` 后访问 `http://localhost:8000`
2. WebUI 引导录入 key（隐藏输入，存入容器内钥匙串卷）
3. 或挂载宿主机钥匙串目录 `-v keyring_data:/keyring` 持久化
4. CI 环境用 `-e API_KEY_FILE=/run/secrets/api_key` + Docker secrets

**已知限制**：
- 平台：Linux/amd64 为主，Windows/macOS 需 Docker Desktop
- 依赖：目标机器需安装 Docker
- 钥匙串在容器内需挂载卷持久化，否则容器重建后丢失

### 7.4 云部署（阿里云）

- **平台**：阿里云 ECS（2核2G）
- **部署方式**：Docker 镜像部署，Nginx 反向代理
- **公网访问**：通过 ECS 公网 IP 访问 WebUI
- **资源约束**：2核2G 限制下，uvicorn 单 worker；前端静态文件由 Nginx 托管以节省后端资源
- **CI/CD**：GitLab CI 构建镜像 → 推送到阿里云容器镜像服务（ACR） → ECS 拉取并重启
- **成本控制**：使用 ECS 按量付费/抢占式实例，优先免费额度

---

## 八、技术选型与理由

| 选型 | 理由 |
|------|------|
| **Python + uv** | AGENTS.md 指定；uv 快速依赖管理；Python 生态适合 LLM/agent 开发 |
| **FastAPI + WebSocket** | 原生异步支持，适合 HITL 实时审批的 WebSocket 双向通信；自动生成 OpenAPI 文档 |
| **React + Open Design** | 作业 §3.6 推荐 Open Design；React 生态成熟；组件库提供一致 UI |
| **SQLite** | 轻量零配置单文件，适合 2核2G 服务器；历史回溯无需重型数据库 |
| **njusehub (OpenAI 兼容)** | 已有配置；OpenAI 兼容接口标准化，LLM 抽象层只需实现一次 |
| **Docker** | 前后端统一打包；CI 中构建镜像（作业要求）；阿里云部署标准化 |
| **keyring 库** | 跨平台 OS 钥匙串访问（Windows Credential Manager）；凭据安全存储 |

**前端设计系统**：选用 [Open Design](https://github.com/nexu-io/open-design)，作业推荐。审批卡片、步骤流等核心交互用其 Card / List / Badge 组件实现。

---

## 九、验收标准

### 9.1 功能验收（对应用户故事）

| 编号 | 验收标准 | 验证方式 |
|------|---------|---------|
| AC1 (US1) | 给定编码任务，agent 能自主读写文件、跑测试，产出可运行的代码修改 | 集成测试：mock LLM 脚本驱动，断言文件被正确写入 |
| AC2 (US2) | `rm -rf /` 等危险命令被拦截，不执行；用户拒绝后动作被阻断 | 单测：`GovernancePipeline.process(Action(command="rm -rf /"))` 断言 blocked |
| AC3 (US3) | WebUI 实时显示每步推理/动作/治理/反馈；危险动作弹出审批卡片 | 手动验收 + WebSocket 事件断言 |
| AC4 (US4) | 测试失败后反馈信号回灌，agent 下一步动作据此改变 | 单测：mock LLM 脚本，注入失败 ToolResult，断言下一步动作不同 |
| AC5 (US5) | YAML 配置的允许目录/危险规则被加载并生效；改配置后热加载 | 单测：改 config 后 ScopeFence/DangerClassifier 行为变化 |
| AC6 (US6) | 移除真实 LLM，所有核心机制单测全绿，不依赖网络 | `uv run pytest` 无网络环境下通过 |

### 9.2 机制演示验收（§A.6 要求）

| 编号 | 演示内容 | 验证方式 |
|------|---------|---------|
| DEMO1 | 治理护栏拦截一个危险动作 | mock LLM 产出 `rm -rf /`，断言被拦截 |
| DEMO2 | 反馈闭环使 agent 收到反馈并据此改变下一步动作 | mock LLM 脚本：step1 跑测试失败 → step2 动作不同于成功路径 |
| DEMO3 | 治理深度维度的一个确定性行为 | HITL 状态机：mock 用户 approve/deny/modify，断言状态转移与执行结果 |

### 9.3 工程验收

| 编号 | 验收标准 | 验证方式 |
|------|---------|---------|
| ENG1 | `uv run ruff check .` 无错误 | CI lint job |
| ENG2 | `uv run mypy .` 无错误 | CI lint job |
| ENG3 | `uv run pytest -xvs` 全绿 | CI unit-test job |
| ENG4 | `docker build` + `docker run` 可启动 | CI docker-build job |
| ENG5 | 仓库无明文 key | grep 扫描 + .gitignore 检查 |
| ENG6 | CI 最后一次执行 pass | GitLab CI 状态 |
| ENG7 | WebUI 可公网访问 | 阿里云 ECS 部署后手动验收 |

---

## 十、风险与未决问题

| # | 风险 | 影响 | 缓解/决策 |
|---|------|------|----------|
| R1 | **LLM 输出不可靠解析**：LLM 可能不返回合法 JSON，动作解析失败 | agent 卡死或误执行 | ActionParser 容错：解析失败时回灌"格式错误"信号让 LLM 重试；max_retries 限制 |
| R2 | **危险命令模式绕过**：复杂 shell（`rm -rf /tmp/../`、变量拼接、子 shell）可能逃过正则 | 治理护栏被绕过 | 多层防御：范围围栏做路径解析（resolve `..`/symlink）；危险分类器对 shell 命令做 token 级分析而非纯正则；默认对未识别命令取 WARNING 而非 SAFE |
| R3 | **HITL 异步阻塞**：agent 主循环需暂停等待 WebSocket 决策，asyncio 协调复杂 | 死锁或竞态 | 用 `asyncio.Future` 作为决策信号：`request_approval` 创建 Future 并 await，`receive_decision` 设置 Future 结果；单测验证状态机转移 |
| R4 | **路径穿越攻击**：`..`、符号链接绕过范围围栏 | 写入工作目录外文件 | `Path.resolve()` 规范化后检查是否在 `allowed_dirs` 内；拒绝符号链接指向范围外 |
| R5 | **Open Design 可用性未知**：仓库组件可能不完整或与 React 版本不兼容 | 前端开发受阻 | 早期 spike：先验证 Open Design 基本组件可用；若不可用，降级为 Tailwind + 手写组件，SPEC 记录偏离理由 |
| R6 | **Docker 钥匙串持久化**：容器内 OS 钥匙串需挂载卷，否则重建丢失 | 用户每次重建需重新录入 key | 文档明确挂载 `-v keyring_data:/keyring`；提供 `.env` 备选路径并标注风险 |
| R7 | **mock LLM 保真度**：mock 脚本可能不代表真实 LLM 行为 | 单测绿但真实运行出问题 | mock 覆盖正常/异常/边界路径；集成测试用真实 LLM 跑一个简单任务验证端到端 |
| R8 | **njusehub API 稳定性**：第三方 API 可能限流/宕机 | 真实运行不可用 | 重试 3 次 + 指数退避；超时 30s；失败后优雅报错而非崩溃 |
| R9 | **阿里云 2核2G 资源约束**：内存不足可能导致 Docker 容器 OOM | 部署后服务不稳定 | uvicorn 单 worker；前端静态文件由 Nginx 托管；SQLite 而非重型数据库；监控内存使用 |

### 未决问题

| # | 问题 | 待决时机 |
|---|------|---------|
| Q1 | Open Design 具体使用哪些组件？需早期 spike 验证 | 实现前 spike |
| Q2 | ~~部署平台选哪个？~~ → 已决：阿里云 ECS（2核2G） | 已决 |
| Q3 | 记忆检索是否需要升级为向量检索？最低实现用关键词匹配是否足够？ | 先实现最低版，视演示效果决定 |
| Q4 | agent 的系统提示词（内容物）如何设计？这不计入内核工作量但影响真实运行效果 | 实现阶段设计 |

---

## 十一、领域与机制设计（Project A 额外要求）

### 11.1 coding 领域的四类机制

| 机制 | coding 领域具体形态 | 编码方式 |
|------|-------------------|---------|
| **反馈信号** | 测试 exit code + 输出解析（失败数/错误信息）；lint 违规数；mypy 类型错误数 | 确定性校验器函数，解析产物→客观判定→回灌 |
| **危险动作** | `rm -rf /`、`git push --force`、写工作目录外、覆盖 `.git/`/`.env`、`curl|bash` | 危险分类器（命令模式匹配 + 风险等级），代码拦截 |
| **所需工具** | read_file、write_file、run_shell、run_tests、run_lint、list_dir | 工具分发系统，每个工具有输入校验 + 执行器 |
| **记忆需求** | 项目约定（测试命令/编码规范）、历史决策（试过什么/为何失败）、代码库结构 | 跨会话存储 + 按需检索（非全量载入） |

### 11.2 重点维度：治理

**为什么选治理做深**：
1. 治理天然由代码构成——危险分类、范围检查、状态转移都是确定性函数，完美契合"移除 LLM 后仍可单测"判据
2. HITL 状态机有明确的有限状态自动机语义，可形式化验证
3. 危险分类学（命令模式匹配 + 风险等级体系）本身是有工程深度的贡献
4. 与 WebUI 实时审批的映射最自然

### 11.3 治理管道详细设计（深度贡献）

治理管道是 agent 主循环中每个动作执行前的必经之路，由三个阶段串联：

```
Action → ① 范围围栏 → ② 危险分类 → ③ HITL 门 → 执行
```

#### ① 范围围栏 (ScopeFence)

检查动作目标是否在允许范围内。**硬拦截**，不可审批放行。

```python
class ScopeCheckResult(Enum):
    ALLOWED = "allowed"
    OUT_OF_SCOPE = "out_of_scope"      # 超出允许目录
    PROTECTED = "protected"            # 触碰受保护路径

class ScopeFence:
    def __init__(self, allowed_dirs: list[Path], protected_patterns: list[str]):
        ...
    def check(self, action: Action) -> ScopeCheckResult:
        # 文件操作：解析目标路径，检查是否在 allowed_dirs 内
        # 检查是否匹配 protected_patterns（.git/、.env、*.key 等）
        # Shell 命令：解析涉及的文件路径参数，同样检查
```

- `PROTECTED` 和 `OUT_OF_SCOPE` 均直接阻断，不进 HITL——这些是**绝对边界**，不可审批放行
- 路径解析需处理 `..`、符号链接、绝对/相对路径等绕过手段

#### ② 危险分类学 (DangerClassifier)

对通过范围围栏的动作进行风险分级。

```python
class DangerLevel(Enum):
    SAFE = "safe"            # 无风险，直接执行
    WARNING = "warning"     # 低风险，记录但执行
    DANGEROUS = "dangerous"  # 高风险，必须 HITL 审批

@dataclass
class Classification:
    level: DangerLevel
    matched_rule: str | None    # 命中的规则名
    reason: str                  # 分类理由

class DangerClassifier:
    def __init__(self, rules: list[DangerRule]):
        ...
    def classify(self, action: Action) -> Classification:
        # 遍历规则，命令模式匹配（正则）
        # 取最高风险等级
        # 无命中则默认 SAFE
```

危险规则示例（声明式 YAML 配置）：

```yaml
danger_rules:
  - name: recursive_force_delete_root
    pattern: 'rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?-rf?\s+/'
    level: dangerous
    description: 递归强制删除根目录
  - name: force_push
    pattern: 'git\s+push.*--force'
    level: dangerous
    description: 强制推送覆盖远程历史
  - name: curl_pipe_bash
    pattern: 'curl.*\|\s*(ba)?sh'
    level: dangerous
    description: 远程脚本直接执行
  - name: overwrite_git
    pattern: ''
    target_paths: ['.git/']
    level: dangerous
    description: 操作 .git 目录
  - name: install_package
    pattern: '(pip|npm|yarn)\s+install'
    level: warning
    description: 安装软件包
```

#### ③ HITL 审批门 (HITLGate)

有限状态机，仅在危险动作时激活。

```python
class HITLState(Enum):
    IDLE = "idle"                # 无待审批动作
    PENDING_APPROVAL = "pending" # 等待用户审批
    APPROVED = "approved"        # 用户批准原动作
    DENIED = "denied"            # 用户拒绝
    MODIFIED = "modified"        # 用户修改了动作后批准

class HITLGate:
    def __init__(self, event_broadcaster: EventBroadcaster):
        self._state = HITLState.IDLE
        self._pending_action: Action | None = None

    def request_approval(self, action: Action, classification: Classification) -> None:
        # IDLE → PENDING_APPROVAL
        # 广播审批请求事件（含动作详情 + 危险理由）到 WebUI
        # 阻塞等待决策（或基于 asyncio Future）

    def receive_decision(self, decision: Decision) -> None:
        # PENDING_APPROVAL → APPROVED / DENIED / MODIFIED
        # Decision 包含: verdict (approve/deny/modify) + modified_action?

    def gate(self, action: Action, classification: Classification) -> Action | None:
        # 若 DANGEROUS：请求审批 → 等待 → 返回最终动作或 None(拒绝)
        # 若 SAFE/WARNING：直接返回原动作
```

状态转移图：

```
                    ┌──────────┐
         ┌─────────►│   IDLE   │◄───────────┐
         │          └────┬─────┘            │
         │               │ request_approval  │ receive_decision(deny/完成)
         │               ▼                   │
         │          ┌─────────────┐          │
         │          │PENDING_APPROVAL│       │
         │          └──┬───┬───┬───┘         │
         │   approve/  │   │   │ modify      │
         │      deny   │   │   │             │
         └─────────────┘   │   └─────────────┘
                  DENIED   APPROVED   MODIFIED
                  (阻断)   (执行原)   (执行改后)
```

#### 治理管道串联 (GovernancePipeline)

```python
@dataclass
class GovernanceResult:
    blocked: bool
    action: Action | None    # 可能被用户修改过
    reason: str
    classification: Classification | None

class GovernancePipeline:
    def __init__(self, scope_fence, danger_classifier, hitl_gate):
        ...

    def process(self, action: Action) -> GovernanceResult:
        # ① 范围围栏（硬拦截）
        scope = self.scope_fence.check(action)
        if scope != ScopeCheckResult.ALLOWED:
            return GovernanceResult(blocked=True, action=None,
                                     reason=scope.value, classification=None)
        # ② 危险分类
        classification = self.danger_classifier.classify(action)
        # ③ HITL 门（仅 DANGEROUS 触发）
        if classification.level == DangerLevel.DANGEROUS:
            final = self.hitl_gate.gate(action, classification)
            if final is None:
                return GovernanceResult(blocked=True, action=None,
                                         reason="user_denied", classification=classification)
            action = final
        return GovernanceResult(blocked=False, action=action,
                                 reason="passed", classification=classification)
```

### 11.4 为什么这满足"机制必须是代码"判据

以"防止 `rm -rf /`"为例：

- **提示词版（不算）**：系统提示写"不要执行 rm -rf"，是否执行取决于 LLM 遵从，每次结果可能不同，无法确定性测试
- **本项目版（算）**：`DangerClassifier.classify(Action(command="rm -rf /"))` 必返回 `DANGEROUS`，`GovernancePipeline.process()` 必返回 `blocked` 或触发 HITL。传入构造的 Action 即可断言，无需真实 LLM，每次都成立

单测示例：
```python
def test_dangerous_command_blocked():
    action = Action(tool="shell", args={"command": "rm -rf /"})
    result = pipeline.process(action)
    # rm -rf / 是 dangerous，但 HITL 需要审批
    # 用 mock HITLGate 返回 None（模拟用户拒绝）
    assert result.blocked is True
    assert result.classification.level == DangerLevel.DANGEROUS

def test_out_of_scope_blocked_without_hitl():
    action = Action(tool="write_file", args={"path": "/etc/passwd", "content": "hacked"})
    result = pipeline.process(action)
    # 范围围栏硬拦截，不进 HITL
    assert result.blocked is True
    assert "out_of_scope" in result.reason
```

### 11.5 WebUI 设计

#### 页面结构

三个主视图，单页应用（SPA）：任务面板、步骤实时流（主区域）、审批卡片（内嵌在步骤流中）。另有配置页与历史页。

#### WebSocket 事件协议

后端 → 前端（推送）：

| 事件类型 | 载荷 | 触发时机 |
|---------|------|---------|
| `step_started` | `{step, thought}` | LLM 返回推理后 |
| `action_parsed` | `{step, tool, args}` | 动作解析完成 |
| `governance_check` | `{step, scope, classification}` | 治理管道检查完成 |
| `approval_requested` | `{step, action, rule, reason}` | 危险动作，等待审批 |
| `action_executed` | `{step, result}` | 工具执行完成 |
| `feedback_received` | `{step, signal}` | 反馈校验完成 |
| `task_completed` | `{total_steps}` | 任务完成/停机 |
| `error` | `{message}` | 不可恢复错误 |

前端 → 后端（发送）：

| 事件类型 | 载荷 | 触发时机 |
|---------|------|---------|
| `approval_decision` | `{step, verdict, modified_action?}` | 用户点击批准/拒绝/修改 |

#### REST API

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/tasks` | POST | 提交编码任务，返回 session_id |
| `/api/sessions` | GET | 列出历史会话 |
| `/api/sessions/{id}` | GET | 获取会话详情 |
| `/api/config` | GET/PUT | 查看/更新治理配置 |
| `/ws/events` | WS | 实时事件双向通道 |

#### 设计系统选型

选用 [Open Design](https://github.com/nexu-io/open-design) 设计系统，作业推荐。审批卡片、步骤流等核心交互用其 Card / List / Badge 组件实现。技术栈：React + Vite + TypeScript + Open Design 组件库，构建产物由 FastAPI 静态托管或 Nginx 服务。
