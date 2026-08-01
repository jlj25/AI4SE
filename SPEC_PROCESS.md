# SPEC_PROCESS.md — 与 Superpowers 协作生成 SPEC 与 PLAN 的过程文档

## 一、Brainstorming 关键节点

### 1.1 智能体追问的好问题

在 brainstorming 阶段，Superpowers 技能引导了以下关键追问：

**Q1："治理逻辑放在提示词里还是代码里？"**
这个追问直接催生了项目的核心设计原则。最初设想是在系统提示中写安全规则，但智能体追问"如果 LLM 不遵从怎么办？如何验证？"这让我意识到提示词治理的不可靠性，转而设计确定性代码管道。

**Q2："fail-open 还是 fail-closed？"**
HITLGate 的 fail-closed 语义（无决策 → DENIED）源于此追问。智能体指出异步环境中审批可能超时，问"超时后默认放行还是拒绝？"这让我选择了更安全的 fail-closed。

**Q3："移除真实 LLM 后能否单测？"**
这个追问贯穿了整个设计。它迫使我将 LLM 抽象为 `LLMClient` ABC + `MockLLMClient`，所有核心机制不依赖网络或真实模型。

### 1.2 修正原设想的节点

最初设想中 HITLGate 使用 `asyncio.Future` 异步阻塞等待审批。brainstorming 中讨论了同步 vs 异步的权衡，最终改为同步状态机——单测中直接设置状态，API 层通过 WebSocket 桥接异步。这个修正简化了测试且不影响安全性。

## 二、至少 3 轮关键迭代

### 迭代 1：深度维度选择

**初始设想**：选择"工具分发"作为深度维度，因为工具是 agent 的"手"。
**智能体建议**：工具分发相对成熟（subprocess + 注册表），治理维度更能体现工程价值——"当 LLM 能完成大部分编码工作时，工程师的真正价值在 harness 这层工程"。
**我的决策**：采纳，改为治理深度。后续实现证明这个选择是对的——治理管道的三阶段串联是项目最有辨识度的部分。

### 迭代 2：ToolResult 字段设计

**PLAN 初稿**：ToolResult 用 `output: str` + `error: str | None`。
**实现时发现**：Task 1 实际定义了 `stdout`/`stderr`/`exit_code`，但 PLAN 后续 Task（8/9/13/17）仍用 `output`/`error`。
**我的决策**：统一为 `stdout`/`stderr`/`exit_code`，更贴近真实 shell 语义。修正了所有后续 Task 的代码片段。

### 迭代 3：Windows 路径适配

**PLAN 测试**：`rm -rf /` 作为危险命令测试 HITL 拦截。
**实现时发现**：Windows 上 `/` 被 `Path.resolve()` 解析为驱动器根目录，被 ScopeFence 先拦截为 OUT_OF_SCOPE，到不了 DangerClassifier 和 HITLGate。
**我的决策**：用 `git push --force`（无文件路径 token，通过围栏）测试 HITL 路径；用 `json.dumps()` 解决 Windows 路径反斜杠在 JSON 中的转义问题。

## 三、AI 建议：采纳与推翻

### 采纳的建议

| 建议 | 来源 | 理由 |
|------|------|------|
| 治理作为深度维度 | brainstorming | 工程价值更高，辨识度更强 |
| fail-closed 语义 | brainstorming | 异步环境安全性 |
| MockLLM 驱动所有测试 | brainstorming | 离线可测，满足 SPEC 核心要求 |
| TDD 红→绿→提交循环 | writing-plans | 保证测试先行 |
| SDD 分派→审查模式 | subagent-driven-development | 隔离上下文，质量可控 |

### 推翻/修正的建议

| 建议 | 处理 | 理由 |
|------|------|------|
| HITLGate 用 asyncio.Future | 改为同步状态机 | 单测更简单，API 层桥接异步 |
| SQLite 持久化记忆 | 用内存 MemoryStore | 2核2G 资源约束，非核心机制 |
| OS 钥匙串存凭据 | 用环境变量 + .env | CI/headless 无钥匙串 |
| `npm create vite` 初始化前端 | 手写所有文件 | 更可控，避免交互式命令 |
| mypy strict 检查测试 | 排除 tests/ 和 demo/ | 测试函数类型注解非核心 |

## 四、冷启动测试：SPEC/PLAN 质量验证

### 4.1 测试方法

按照要求，使用与主开发智能体不同的 agent 类型（general subagent），在全新 session 中仅提供 SPEC.md + PLAN.md，不导入任何先前对话历史，指定其从 PLAN 选 1-2 个 Task 自主推进。

由于工具限制（subagent 返回为空），以下基于实现过程中实际遇到的 SPEC/PLAN 缺陷进行记录——这些问题正是一个全新 agent 会受阻的地方。

### 4.2 暴露的 SPEC/PLAN 缺陷

**缺陷 1：ToolResult 字段不一致（严重）**
- Task 1 定义 `stdout`/`stderr`/`exit_code`
- Task 8/9/13/17 代码片段用 `output`/`error`
- 新 agent 会困惑：该用哪个？是两个不同类型还是笔误？
- **修订**：统一为 `stdout`/`stderr`/`exit_code`

**缺陷 2：MockLLMClient 构造参数不一致（严重）**
- Task 2 定义 `MockLLMClient(script: list[str])`
- Task 13/17 代码用 `MockLLMClient(responses=[...])`
- 新 agent 会直接用 `responses=` 导致 `TypeError`
- **修订**：统一为 `script=`

**缺陷 3：LLMClient.chat() 签名不一致（严重）**
- Task 2 定义 `chat(messages: list[Message]) -> str`
- Task 13 实现调用 `chat(prompt_text)` 传字符串
- 新 agent 会传错参数类型
- **修订**：统一为 `chat(list[Message])`

**缺陷 4：Windows 路径行为未说明（中等）**
- PLAN 测试用 `rm -rf /`，未说明 Windows 上 `/` 解析为驱动器根目录
- 新 agent 在 Windows 上会发现 ScopeFence 先拦截，到不了 HITL
- **修订**：增加 Windows 路径适配说明

**缺陷 5：JSON 路径转义未说明（中等）**
- PLAN 测试用 f-string 插值 Windows 路径到 JSON
- 反斜杠未转义导致 `json.loads` 失败
- **修订**：用 `json.dumps()` 构造 JSON

**缺陷 6：Dockerfile 阶段命名混乱（低）**
- Task 16 Dockerfile 用 `COPY --from=0`（未命名阶段），且 final 阶段未安装 uv
- **修订**：用命名阶段，final 阶段安装 uv

**缺陷 7：mypy strict 对测试函数的要求未说明（低）**
- PLAN 要求 `mypy .`，但未说明 strict 模式要求测试函数也有类型注解
- **修订**：配置 mypy 排除 tests/ 和 demo/

### 4.3 产出与预期差距

一个全新 agent 仅凭 SPEC + PLAN 实现，预计会在缺陷 1-3 处严重受阻（字段名/参数名不匹配导致代码无法运行），在缺陷 4-5 处环境适配受阻。这些恰恰是 spec 质量最有价值的反馈信号——它们暴露了 PLAN.md 内部跨 Task 一致性不足的问题。

### 4.4 据此对 SPEC/PLAN 的修订

上述缺陷在实现过程中已全部修正，但 PLAN.md 本身未回溯更新。若要修订，关键 diff 为：

```diff
# Task 8/9/13/17 中所有 ToolResult 构造
- ToolResult(success=True, output="done", error=None)
+ ToolResult(success=True, stdout="done")

# Task 13/17 中 MockLLMClient 构造
- MockLLMClient(responses=[...])
+ MockLLMClient(script=[...])

# Task 13 中 LLM 调用
- response = self._llm.chat(prompt_text)
+ response = self._llm.chat(context)
```

## 五、Brainstorming 技能反思

### 做得好的地方

1. **结构化探索**：brainstorming 技能通过追问而非建议引导思考，让我自己得出结论而非被动接受。深度维度选择、fail-closed 语义等关键决策都源于此。
2. **约束驱动设计**：技能反复追问"移除真实 LLM 能否测试？"这一约束直接塑造了 MockLLM 架构，是项目质量的关键保障。
3. **从问题到原则**：不是直接给方案，而是先问"要解决什么问题"，再推导设计原则。这让最终设计有清晰的因果链。

### 让我不满的地方

1. **跨 Task 一致性未覆盖**：brainstorming 阶段关注了架构层面的设计原则，但未引导检查 PLAN.md 中 17 个 Task 之间的接口一致性。ToolResult 字段、MockLLMClient 参数名等跨 Task 不一致问题在实现时才暴露。
2. **环境适配未考虑**：brainstorming 在抽象层面讨论了 fail-closed 等语义，但未追问"开发环境是 Windows，路径行为不同怎么办？"这导致 `rm -rf /` 测试用例在 Windows 上失效。
3. **冷启动测试未内建**：brainstorming 技能没有"用新 agent 验证 spec 清晰度"这一步骤。如果在内建流程中，上述缺陷可以在 PLAN 阶段就被发现。
