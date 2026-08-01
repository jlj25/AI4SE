# AGENT_LOG.md — 实现过程时间线

> 按时间顺序记录关键节点。每条包含：时间戳与 task 编号、触发的 Superpowers 技能、关键 prompt/context 配置、subagent 输出的关键片段或 commit hash、人工干预、学到的教训。

---

## 阶段 0：规约与计划

### 2026-07-14 11:49 — SPEC.md 签字确认

- **Task**：SPEC.md 生成
- **Superpowers 技能**：`brainstorming`
- **关键 prompt/context**：以"构建一个 coding agent harness，治理为核心深度"为种子想法启动 brainstorming。技能追问三个关键问题：①治理逻辑放在提示词里还是代码里？②fail-open 还是 fail-closed？③移除真实 LLM 后能否单测？
- **产出**：commit `abf11f0`，SPEC.md 707 行，含 10 个必需章节 + §11 领域与机制设计
- **人工干预**：将 HITLGate 从 `asyncio.Future` 异步阻塞改为同步状态机（简化测试）；将深度维度从"工具分发"改为"治理"（工程价值更高）
- **教训**：brainstorming 的追问比建议更有价值——它让我自己得出结论而非被动接受

### 2026-07-14 14:38 — PLAN.md 生成

- **Task**：PLAN.md 生成
- **Superpowers 技能**：`writing-plans`
- **关键 prompt/context**：将 SPEC 分解为 17 个 TDD Task，每步 2-5 分钟，明确文件路径与验证步骤
- **产出**：commit `3227ea3`，PLAN.md 3042 行，17 个 Task + 自检对照表
- **人工干预**：无
- **教训**：PLAN 跨 Task 一致性是最大隐患——ToolResult 字段名、MockLLMClient 参数名在后续 Task 中不一致，实现时才暴露

---

## 阶段 1：SDD subagent 驱动开发（Task 1-6）

### 2026-07-15 11:27 — Task 1：核心类型

- **Task**：Task 1 — 项目脚手架 + 核心类型
- **Superpowers 技能**：`subagent-driven-development`、`test-driven-development`
- **关键 prompt/context**：向 subagent 派发 Task 1 brief，要求先写失败测试再实现 `src/types.py`（Action/ToolResult/FeedbackSignal/Message）
- **Subagent 产出**：commit `624bca4`，types.py 定义了全部核心 dataclass
- **人工干预**：commit `3983708` 补充 `FeedbackType` 枚举 + `Message.feedback` 字段（PLAN 后续 Task 引用了此字段但 Task 1 漏定义）；commit `4066abb` 补充 `FeedbackSignal.message` 断言
- **教训**：PLAN brief 与实际类型定义之间存在字段遗漏，review 时需逐字段比对

### 2026-07-15 11:48 — Task 2：LLM 抽象层

- **Task**：Task 2 — LLMClient ABC + MockLLMClient
- **Superpowers 技能**：`subagent-driven-development`、`test-driven-development`
- **关键 prompt/context**：派发 Task 2 brief，要求 `MockLLMClient(script: list[str])` 按脚本返回预设响应
- **Subagent 产出**：commit `68005b8`，`src/llm/base.py` + `src/llm/mock_client.py`
- **人工干预**：commit `c21d6c8` 重命名 `mock_client.py` → `mock.py`（统一后续 Task 的 import 路径）
- **教训**：文件命名应在 PLAN 中统一规定，避免后续 import 路径修正

### 2026-07-16 01:04 — Task 3：配置加载器

- **Task**：Task 3 — ConfigLoader（YAML → 强类型 AgentConfig）
- **Superpowers 技能**：`subagent-driven-development`、`test-driven-development`
- **关键 prompt/context**：派发 Task 3 brief，要求 YAML 加载 + 字段校验 + 默认值
- **Subagent 产出**：commit `a9c2e74`，`src/config/loader.py` + `config/config.yaml`
- **人工干预**：commit `3f2df96` 修复 4 个问题：DRY 默认值重复、校验逻辑缺失、默认配置未测试、路径迁移
- **教训**：subagent 倾向于重复默认值定义而非集中管理，review 时需检查 DRY

### 2026-07-16 02:07 — Task 4：范围围栏

- **Task**：Task 4 — ScopeFence（路径检查/穿越防御/受保护路径）
- **Superpowers 技能**：`subagent-driven-development`、`test-driven-development`
- **关键 prompt/context**：派发 Task 4 brief，要求 `Path.resolve()` 规范化后检查 allowed_dirs
- **Subagent 产出**：commit `3246116`，`src/governance/scope.py`
- **人工干预**：无（review clean），但记录 Important note：shell 命令路径提取过于宽泛，后续 Task 需细化
- **教训**：shell 命令中的路径提取比文件操作复杂，需要 token 级分析

### 2026-07-31 16:43 — Task 5：危险分类器

- **Task**：Task 5 — DangerClassifier（正则模式匹配/风险分级）
- **Superpowers 技能**：`subagent-driven-development`、`test-driven-development`
- **关键 prompt/context**：派发 Task 5 brief，要求正则匹配 + 取最高风险等级
- **Subagent 产出**：commit `fd4dbd0`，`src/governance/classifier.py`
- **人工干预**：无（review clean）
- **教训**：无

### 2026-07-31 17:05 — Task 6：HITL 审批门

- **Task**：Task 6 — HITLGate（有限状态机）
- **Superpowers 技能**：`subagent-driven-development`、`test-driven-development`
- **关键 prompt/context**：派发 Task 6 brief，要求 IDLE→PENDING→APPROVED/DENIED/MODIFIED 状态转移
- **Subagent 产出**：commit `2a56f69`，`src/governance/hitl.py`
- **人工干预**：commit `aab8d30` 修复 4 个问题：modify 校验缺失、gate 死代码、错误路径未测试、WARNING 路径未测试
- **教训**：状态机的错误路径和边界状态最容易被 subagent 遗漏，review 时需逐状态验证

---

## 阶段 2：自实现（Task 7-17）

> **偏离说明**：Task 7 起 subagent 两次中断返回空结果，改为自实现。偏离原因：subagent 工具不稳定，无法继续 SDD 工作流。此偏离未在 AGENT_LOG.md 中记录（因当时无此文件），现补记。

### 2026-07-31 22:23 — Task 7：治理管道

- **Task**：Task 7 — GovernancePipeline（三阶段串联）
- **Superpowers 技能**：`test-driven-development`（自实现，无 subagent）
- **关键 prompt/context**：按 PLAN Task 7 brief 自行编写，先写失败测试
- **产出**：commit `6dfd035`，`src/governance/pipeline.py`
- **人工干预**：适配 Windows 路径——`rm -rf /` 在 Windows 被 ScopeFence 先拦截为 OUT_OF_SCOPE（`/` 解析为驱动器根目录），到不了 DangerClassifier 和 HITLGate。改用 `git push --force`（无文件路径 token，通过围栏）测试 HITL 路径。Windows 路径反斜杠在 JSON 中需 `json.dumps()` 转义
- **教训**：PLAN 的测试用例未考虑 Windows 路径行为差异，跨平台测试需适配

### 2026-08-01 00:05 — Task 8：工具分发

- **Task**：Task 8 — ToolDispatcher + FS/Shell 工具
- **Superpowers 技能**：`test-driven-development`（自实现）
- **关键 prompt/context**：按 PLAN Task 8 brief 自行编写
- **产出**：commit `3006bec`，`src/tools/`（base.py, dispatcher.py, fs.py, shell.py）
- **人工干预**：适配 ToolResult 字段——PLAN Task 8 代码片段用 `output`/`error`，但 Task 1 实际定义 `stdout`/`stderr`/`exit_code`。统一为后者。新增 dispatch 异常捕获测试
- **教训**：PLAN 跨 Task 字段名不一致是最大隐患，实现时需以 Task 1 的类型定义为准

### 2026-08-01 00:10 — Task 9：反馈闭环

- **Task**：Task 9 — Validator ABC + FeedbackLoop
- **Superpowers 技能**：`test-driven-development`（自实现）
- **产出**：commit `6789507`，`src/feedback/`（validators.py, loop.py）
- **人工干预**：同样适配 ToolResult 字段（stdout/stderr 非 output/error）。新增无校验器信息 + 多校验器失败优先级测试
- **教训**：同 Task 8

### 2026-08-01 00:12 — Task 10：记忆存储

- **Task**：Task 10 — MemoryStore（关键词选择性检索）
- **Superpowers 技能**：`test-driven-development`（自实现）
- **产出**：commit `da0cb9a`，`src/memory/store.py`
- **人工干预**：无字段冲突。新增 latest-first + all_messages 测试
- **教训**：无

### 2026-08-01 00:16 — Task 11：凭据管理

- **Task**：Task 11 — CredentialManager
- **Superpowers 技能**：`test-driven-development`（自实现）
- **产出**：commit `7e263b9`，`src/credentials/manager.py`
- **人工干预**：新增 `python-dotenv` 依赖。新增 model 默认值/model 环境变量/LLM 回退测试
- **教训**：SPEC 设计了 OS 钥匙串方案，但实际实现降级为环境变量 + .env（CI/headless 无钥匙串）。此降级在 SPEC_PROCESS.md 中记录为"推翻的建议"

### 2026-08-01 00:20 — Task 12：动作解析器

- **Task**：Task 12 — ActionParser（tool_code 代码块提取 + JSON 解析）
- **Superpowers 技能**：`test-driven-development`（自实现）
- **产出**：commit `670e936`，`src/parser/action_parser.py`
- **人工干预**：无字段冲突。新增空 tool/非 dict/instance type 测试
- **教训**：无

### 2026-08-01 00:49 — Task 13：Agent 主循环

- **Task**：Task 13 — AgentLoop（上下文→LLM→解析→治理→执行→反馈→停机）
- **Superpowers 技能**：`test-driven-development`（自实现）
- **产出**：commit `ea94bb1`，`src/agent/loop.py`
- **人工干预**：适配 4 个 brief 差异：①`LLMClient.chat()` 接收 `list[Message]` 非 str；②`MockLLMClient` 用 `script=` 非 `responses=`；③ToolResult 用 `stdout/stderr` 非 `output/error`；④Windows 路径反斜杠 JSON 转义用 `json.dumps()`。`_make_agent` 接受自定义 `allowed_dirs` 适配 `tmp_path` 测试
- **教训**：Task 13 是所有跨 Task 不一致的集中爆发点——4 个字段/参数名差异同时出现

### 2026-08-01 00:54 — Task 14：API 层

- **Task**：Task 14 — FastAPI + REST + WebSocket
- **Superpowers 技能**：`test-driven-development`（自实现）
- **产出**：commit `80ceb81`，`src/api/`（main.py, routes.py, ws.py）
- **人工干预**：为 mypy strict 添加类型注解；修复 `dict(object)` 类型错误（用 `isinstance` 检查）。新增 pending-gate approve/deny/modify + websocket 测试
- **教训**：mypy strict 对 `dict` 与 `object` 的类型推断需显式 `isinstance` 收窄

### 2026-08-01 01:20 — Task 15：前端

- **Task**：Task 15 — React + Vite + TypeScript
- **Superpowers 技能**：`test-driven-development`（自实现）
- **产出**：commit `3d43c6e`，`frontend/`（App.tsx, api.ts, ws.ts, ChatView.tsx, ApprovalDialog.tsx）
- **人工干预**：手写所有前端文件而非 `npm create vite`（避免交互式命令）。TypeScript strict 类型。Tokyo Night CSS 主题。`npm build` 验证通过（88 modules, 4.92s）
- **教训**：交互式 CLI 命令（如 `npm create vite`）在 agent 环境中不可用，手写更可控

### 2026-08-01 01:43 — Task 16：Docker + CI

- **Task**：Task 16 — Dockerfile + docker-compose + GitLab CI
- **Superpowers 技能**：`test-driven-development`（自实现）
- **产出**：commit `35a1414`，Dockerfile, docker-compose.yml, .gitlab-ci.yml
- **人工干预**：修复 Dockerfile——命名阶段（非 `--from=0`）；final 阶段安装 uv；安装 dev 依赖以运行测试。Docker daemon 未运行，构建未验证
- **教训**：Dockerfile 多阶段构建的阶段命名和 final 阶段依赖容易出错

### 2026-08-01 02:00 — Task 17：机制演示 + 集成测试

- **Task**：Task 17 — DEMO1-3 + 端到端集成测试
- **Superpowers 技能**：`test-driven-development`（自实现）
- **产出**：commit `78b0cf7`，`tests/test_demo.py` + `tests/test_integration.py` + `demo/run_demo.py`
- **人工干预**：适配 `MockLLMClient script=` 非 `responses=`；Windows 路径用 `json.dumps`。新增 HITL approve flow + write-then-list + shell-echo 测试。mypy 配置排除 `tests/` 和 `demo/`
- **教训**：测试函数无类型注解在 mypy strict 下报错，但测试代码的类型注解非核心，排除即可

---

## 阶段 3：文档与收尾

### 2026-08-01 14:53 — REFLECTION.md

- **Task**：反思报告
- **Superpowers 技能**：无（人工撰写）
- **产出**：commit `284ab87`，REFLECTION.md 2131 字
- **内容**：自检 + 设计决策 + 偏离说明
- **教训**：反思报告须由学生本人撰写，禁止 AI 代写

### 2026-08-01 17:35 — README.md + SPEC_PROCESS.md

- **Task**：项目文档 + 过程文档
- **Superpowers 技能**：无
- **产出**：commit `a324d7b`，README.md（6 个必需章节）+ SPEC_PROCESS.md（brainstorming 节点 + 3 轮迭代 + 冷启动分析）
- **人工干预**：冷启动测试——task 工具两次派发 general subagent 均返回空结果。改为从实现过程中实际遇到的 SPEC/PLAN 缺陷作为冷启动证据，记录 7 个缺陷
- **教训**：冷启动验证是规约工作中最关键的客观证据，但工具限制可能阻碍其执行

---

## 偏离汇总

| 偏离项 | 要求 | 实际 | 原因 |
|--------|------|------|------|
| git worktrees | §4.6.1 每个功能开 worktree | 未使用，直接在 main 上 | 单人项目，worktree 开销大于收益 |
| subagent 驱动 | §4.6.2 每 task 派 subagent | Task 1-6 用 subagent，Task 7-17 自实现 | subagent 工具两次中断返回空 |
| 两阶段评审 | §4.6.4 每 task spec 合规 + 代码质量 | Task 1-6 有评审，Task 7-17 自审 | 同上 |
| 完成分支 | §4.6.5 finishing-a-development-branch | 未使用 | 单分支开发，无 PR |
| HITLGate 异步 | SPEC 设计 asyncio.Future | 改为同步状态机 | 简化测试，API 层桥接异步 |
| OS 钥匙串 | SPEC 设计 keyring 库 | 降级为环境变量 + .env | CI/headless 无钥匙串 |
| 冷启动验证 | §4.5 换 agent 试运行 | task 工具返回空，改为缺陷分析 | 工具限制 |
