# Task 3 报告：配置加载器

## 状态
DONE

## 提交
- `a9c2e74` feat: 配置加载器（YAML→强类型 AgentConfig）+ 默认 config.yaml

## 测试摘要
`uv run pytest tests/config/ -v` → 3 passed（test_load_full_config / test_load_defaults_when_fields_missing / test_danger_rule_creation）。全量 `uv run pytest` → 11 passed，无回归。

## 验证结果
- `uv run ruff check src/config/ tests/config/` → All checks passed
- `uv run mypy src/config/` → Success: no issues found in 2 source files
- `uv run ruff format --check` → 已格式化
- 默认 `config.yaml` 实测加载：max_steps=50, 4 条 danger_rules, model=glm-5.2, dirs=['./src','./tests']

## 交付物
- `src/config/__init__.py`：配置子包
- `src/config/loader.py`：`ScopeConfig` / `DangerRule` / `LLMConfig` / `AgentConfig` dataclass + `ConfigLoader.load(path)` 静态方法
- `config.yaml`：默认配置（4 条危险规则：递归删根/强制推送/curl 管道 bash/安装包）
- `tests/config/__init__.py` + `tests/config/test_loader.py`：3 个单测

## TDD 流程
1. 红：先写 test_loader.py，运行 → `ModuleNotFoundError: No module named 'src.config'`
2. 绿：实现 loader.py + 默认 config.yaml → 3 passed
3. 重构：ruff --fix 清理未用 import + ruff format

## 与 brief 的偏差（必要且最小）
1. **测试 YAML 字符串改用 raw string `r"""..."""`**：brief 用普通三引号字符串包含 `rm\s+-rf`，Python 3.12 会触发 `SyntaxWarning: invalid escape sequence '\s'`，ruff 会报 W605。改用 raw string 后字符串内容完全一致（反斜杠原样保留），仅消除告警。YAML 值逐字不变。
2. **测试 import 清理**：brief 的 import 行引入了 `AgentConfig`/`ScopeConfig`/`LLMConfig` 但测试体仅通过属性间接访问，ruff F401 报未使用。`ruff check --fix` 自动移除这三个未直接引用的名称。测试断言完全不变。
3. **新增 `types-PyYAML` dev 依赖**：mypy strict 模式下 `import yaml` 缺类型桩会报 `import-untyped`。已加入 `[project.optional-dependencies] dev`（与 pytest/ruff/mypy 同处），并重新 `uv lock`。

## 自检对照（SPEC 约束）
- ✅ 所有 docstring 简体中文
- ✅ 无代码注释
- ✅ 未使用禁用 SDK（仅用 pyyaml 低层库）
- ✅ 核心机制可用 mock/stub 离线测试（ConfigLoader 纯本地文件解析，无网络）
- ✅ kernel 与 contents 分离（loader 代码与 config.yaml 规则文件解耦）

---

## Review 修复报告（3 Important + 1 全局约束）

提交：`fix: 配置加载器修复（DRY默认值/校验/默认配置测试/路径迁移）`

### 1. DRY 违规 — 默认值两处重复
**问题**：每个默认值在 dataclass 字段与 `load()` 中各写一遍（如 `max_steps=50` 与 `agent_section.get("max_steps", 50)`）。
**修复**：新增 `_section_kwargs(section, allowed_keys)` 辅助函数，仅提取 YAML 中实际存在的键，缺失键交由 dataclass 默认值兜底。`load()` 不再重复字面默认值。`DangerRule` 同样经 `_section_kwargs` 构造，`description` 默认值仅存于 dataclass。

### 2. Docstring 声称校验但实际无校验
**问题**：docstring 写"加载并校验"，但 `load()` 无校验；`agent:` 为 null 时 `.get()` 抛 `AttributeError`，缺规则键抛裸 `KeyError`。
**修复**：新增 `ConfigError` 异常与 `_build_danger_rules()` 校验函数：
- null 段落经 `_section_kwargs` 优雅回退为默认值（不再 `AttributeError`）；
- `danger_rules` 非列表、元素非映射、缺 `name`/`pattern`/`level` 必填字段 → `ConfigError`（不再裸 `KeyError`）；
- `level` 必须属于 `ALLOWED_LEVELS = {dangerous, warning, safe}`，否则 `ConfigError`。
docstring"加载并校验"现在名副其实。

### 3. 默认 config.yaml 无测试
**问题**：仓库默认配置无自动化测试，回归会静默通过。
**修复**：新增 `test_default_config_loads`，加载仓库 `config/config.yaml`，断言 `max_steps > 0`、`len(danger_rules) >= 1`、`model` 非空字符串。

### 4. config.yaml 路径迁移（全局约束）
**问题**：`config.yaml` 位于仓库根，全局约束要求 `config/config.yaml`。
**修复**：`git mv config.yaml config/config.yaml`；`test_default_config_loads` 指向新路径；源码无硬编码路径引用，无需改动。

### 验证结果
- `uv run pytest tests/config/ -v` → 8 passed（原 3 + 新增 5）
- `uv run pytest`（全量）→ 16 passed，无回归
- `uv run ruff check src/config/ tests/config/` → All checks passed
- `uv run ruff format --check` → 已格式化
- `uv run mypy src/config/` → Success: no issues found in 2 source files

### TDD 流程
1. 红：先写 5 个新测试（默认配置加载 / null 段落 / 缺必填字段 / 非法 level / 非列表），运行 → `ImportError: cannot import name 'ConfigError'`（特性缺失）
2. 绿：实现 `ConfigError` + `_section_kwargs` + `_build_danger_rules` + DRY 重构 → 8 passed
3. 重构：`ruff format` 规整 loader.py 长行
