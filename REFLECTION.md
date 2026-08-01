# REFLECTION.md — NJUSE Coding Agent Harness 反思报告

## 一、项目概述

本项目从零构建了一个以**治理（Governance）为核心深度**的编码智能体工具。通过 17 个 TDD Task 逐步实现，最终交付了一个可离线测试、可 Docker 部署、具备前端交互的完整系统。

核心架构为一条确定性管道：用户输入 → 组织上下文 → 调用 LLM → 解析动作 → 治理管道 → 工具执行 → 反馈注入 → 停机判断。其中治理管道由三阶段串联：ScopeFence（范围围栏）→ DangerClassifier（危险分级）→ HITLGate（人工审批门）。

## 二、深度维度：治理管道的设计

### 2.1 为什么选择治理作为深度

编码智能体的核心风险不在于"能不能做"，而在于"该不该做"。市面上的 agent 框架将安全逻辑放在系统提示词中，本质是"建议"而非"约束"——LLM 可以忽略提示词，用户也无法验证安全检查是否执行。

本项目核心原则：**治理逻辑必须是确定性代码，不是提示词。** 测试标准："移除真实 LLM，机制是否仍可测？"全部 107 个测试用 MockLLM 驱动，治理管道每阶段都是纯函数，输入构造的 Action 即可验证输出。

### 2.2 三阶段职责划分

**ScopeFence**：硬拦截，不可审批放行。检查路径是否在允许目录内、是否触碰受保护路径。路径穿越攻击通过 `Path.resolve()` 解析后被拦截。设计哲学是"绝对边界"。

**DangerClassifier**：对通过围栏的动作分级（SAFE/WARNING/DANGEROUS）。正则模式匹配，取最高风险等级。规则从 YAML 配置加载，可声明式扩展。这是"相对边界"——危险动作可执行，但需审批。

**HITLGate**：有限状态机，仅 DANGEROUS 时激活。关键设计是 **fail-closed**：DANGEROUS 动作若无可用决策，直接判 DENIED 返回 None。确保异步环境中（审批超时、网络断开）不会"默认放行"危险操作。

### 2.3 集成决策

围栏拦截不进 HITL（绝对边界）；分类后仅 DANGEROUS 触发 HITL（减少审批疲劳）；每次 process 后 reset gate（有状态需重置）。

## 三、关键设计决策

### 3.1 MockLLM 驱动的测试策略

`LLMClient` 抽象基类 + `MockLLMClient` 按脚本返回预设响应。所有核心机制均用 MockLLM 单测，无网络、无真实模型。覆盖：安全放行、范围越界、受保护路径、危险 deny、fail-closed、WARNING 放行、路径穿越、HITL 全路径、端到端读/写/列/shell。

### 3.2 Windows 路径适配

开发环境为 Windows，PLAN 中的测试用例行为不同：`/` 被 `Path.resolve()` 解析为驱动器根目录，被 ScopeFence 先拦截；Windows 路径反斜杠在 JSON 中需转义。解决方案：用 `json.dumps()` 构造 JSON；用 `git push --force`（无文件路径）测 HITL 路径；用 `tmp_path` fixture 传入 `allowed_dirs`。

### 3.3 其他决策

- **ToolResult 字段**：用 `stdout`/`stderr`/`exit_code` 而非 PLAN 后续 Task 中的 `output`/`error`，更贴近 shell 语义。
- **HITLGate 同步实现**：单测中同步模拟更简单，API 层通过 WebSocket 桥接异步。fail-closed 确保同步实现的安全性。
- **记忆存储**：关键词子串匹配 + 时间排序，非向量嵌入。资源约束下的务实选择，接口可替换。

## 四、已知偏离与未来改进

**已知偏离**：SQLite 持久化未实现（用内存 MemoryStore 替代）；REST API 精简（仅 `/api/health` + `/api/approve`）；CredentialManager 用环境变量（CI/headless 无钥匙串）；工具集精简（`run_shell` 统一覆盖 `run_tests`/`run_lint`）。

**未来改进**：向量记忆（chromadb/faiss）；异步 HITL（asyncio.Future）；SQLite 持久化；更多专用工具；治理规则热加载。

## 五、自检结果

| 检查项 | 结果 |
|--------|------|
| 核心机制可用 MockLLM 单测 | ✅ 107 测试全通过 |
| 治理管道三阶段均为确定性代码 | ✅ 纯函数/状态机 |
| 无 LangChain/AutoGen/CrewAI 依赖 | ✅ |
| opencode.json 未被 git 追踪 | ✅ |
| CI pipeline 配置完整 | ✅ ruff→mypy→pytest |
| Docker 镜像可构建 | ⚠️ 结构正确，daemon 未运行 |

## 六、总结

本项目从 SPEC 到 PLAN 到实现，全程遵循 TDD（红→绿→提交）工作流。深度选择治理维度，实现三阶段确定性管道，所有机制可用 MockLLM 离线测试。17 个 Task、107 个测试、32 个源文件，ruff/mypy 全绿。核心贡献是证明了"治理逻辑可以是代码而非提示词"这一设计哲学的可行性。
