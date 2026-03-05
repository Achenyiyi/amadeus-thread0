# Amadeus-K（原型）

这是一个“个人科研助理/长期陪伴”的对话原型：目标是让对话更像《命运石之门0》里的 Amadeus（牧濑红莉栖）——会记得、会判断、会吐槽，但整体理性可靠。

你可以把它当作：
- 一个带**长期记忆**的命令行聊天助手
- 一个所有关键动作都**可审批、可审计、可回滚**的可控原型（适合个人长期用）

---

## 这项目能做什么？（你关心的“用户功能”）

1) **正常聊天 + 红莉栖式表达**
- 回复会尽量遵守：先给结论 → 再拆解 → 最后追问/下一步。
- 如果回复变成“客服腔/系统日志腔/太啰嗦”，系统会自动触发一次改写。

2) **长期记忆（可控）**
- 你说“我喜欢什么/不喜欢什么/怎么称呼你”等，会进入长期记忆（需要审批）。
- 如果它记错了：可以纠错。
- 如果纠错也错了：可以撤销纠错。
- 如果你只是确认“对，就是这样”：会更新“最后确认时间”（更像真实相处）。

3) **工具调用（更像“能力体系”）**
- 默认只给模型暴露少量低风险工具。
- 如果它需要更强工具，会先提出“升级申请”，你批准后才临时解锁（有 TTL，会自动过期）。
- 工具调用有次数上限与超时保护，避免失控重试。

4) **上下文不会“聊到爆”**（双轨滚动压缩）
- 当同一线程的对话 messages 过长时，系统会触发**滚动归档**：
  - A 轨：生成 `thread_summary`（剧情/进度摘要），写入 `profile.thread_summary`（覆盖更新，且走审批）。
  - B 轨：满足门槛时，从“新增 moments”里提炼 1~3 条 `reflections` 候选（仍走审批）。
- 然后只保留最近一小段 messages，避免模型上下文无限增长。

5) **可回放/可追溯**
- 每次工具调用、记忆写入、升级申请等都有审计日志（JSONL）。

---

## 快速开始（新人照着做就能跑）

### 1) 准备 `.env`

项目根目录提供了示例：`.env.example`。

你只需要：
- 复制一份为 `.env`
- 填好至少两类 key：
  - `DEEPSEEK_API_KEY`
  - （可选）`LANGSMITH_API_KEY`（想开 tracing 再配）

> 其他变量先别动，默认就能跑。

### 2) 安装依赖

依赖列表在 `requirements.txt`。

### 3) 运行 CLI

```bash
python -m amadeus_thread0.cli
```

启动后你会看到审批提示：当模型尝试写入记忆或执行高风险工具时，会弹出一个“批准/拒绝/编辑参数”的选择。

---

## 你会看到哪些“数据文件”？（非常重要）

默认数据目录是 `data/`（可用 `AMADEUS_DATA_DIR` 改到别处）。常见文件：

- `data/checkpoints.sqlite`：对话线程 checkpoint（短期状态/可回放）
- `data/memories.sqlite`：长期记忆库（profile/relationship/moments/skills 等）
- `data/diary.txt`：日记（只有你批准写入时才会改）
- `data/tool_audit.jsonl`：工具审计日志
- `data/memory_audit.jsonl`：记忆抽取/写入审计日志
- `data/decision_audit.jsonl`：检索/分页等决策日志（best-effort）
- `data/mcp_audit.jsonl`：MCP（外部能力口子）相关审计（目前只做防线与记录，占位）

如果你要把仓库分享给别人：
- **不要提交 `data/` 里的真实内容**（尤其 `*.sqlite`、`diary.txt`、`*.jsonl` 可能含隐私）。

---

## 核心概念：线程、记忆、审批（小白版）

### 1) 线程（thread / 世界线）
- 每次对话都有一个 `thread_id`。
- 切换 `thread_id` 相当于开一条新的“世界线”。

相关环境变量：
- `AMADEUS_THREAD_ID`：当前线程 id

### 2) 记忆（长期 vs 短期）

- **短期记忆**：当前线程里的对话状态，由 checkpoint 保存。
- **长期记忆**：写入 SQLite 数据库，主要分三类：
  - profile：稳定事实/偏好/禁忌/称呼
  - relationship：关系阶段与边界（单条状态）
  - moments：共同经历摘要（可检索）

补充：滚动压缩相关的 profile 字段
- `profile.thread_summary`：线程摘要（剧情/进度），会被覆盖更新，用于解决长对话上下文上限。
- `profile.meta_last_reflect_moment_id`：反思增量指针（系统内部使用，避免对同一批 moments 反复提案）。

### 3) 审批（HITL = Human-in-the-loop）

简单说：
- 读工具：大多自动放行
- 写工具：需要你批准

好处：
- 它不会“背着你写入错误记忆/乱改数据”。

---

## CLI 常用命令（只列最常用的）

基础：
- `/exit`：退出
- `/newthread`：新建线程（新世界线）
- `/threads`：列出出现过的 thread_id

记忆：
- `/mem`：查看当前记忆快照
- `/worldline`：查看世界线事件与承诺
- `/bond`：查看关系演化时间线
- `/sources`：查看最近外部来源引用（可追溯）
- `/persona`：查看角色状态快照（persona/emotion/science/canon）
- `/set key=value`：手动写入 profile
- `/correct key=value | reason`：纠错（推荐用这个覆盖冲突值）
- `/undo | reason`：撤销最近一次纠错
- `/forget key`：删除某个 profile key

---

## 工具/错误是怎么“可修复”的？（遇到报错时看这里）

工具失败会返回结构化错误：
- `error.code`：错误类型（例如 `BAD_INPUT` / `REJECTED` / `TIMEOUT`）
- `error.message`：简短说明
- `error.hint`：下一步建议（该怎么改参数/是否需要申请升级）

你一般只需要：
- 审批时改参数，或
- 明确拒绝，让模型给 Plan B（不用工具的替代方案）。

---

## 回归评测（可选，但推荐）

项目带了一个回归脚本：`evals/run_eval.py`。

它会在隔离目录下跑一组对话用例，检查例如：
- 偏好是否写进 profile（而不是误写成 moment）
- 问句是否不会误写入记忆
- 纠错→撤销闭环是否可用
- 工具升级申请是否触发且生效
- 回忆引用是否“像人”（≤2 条、不用系统日志口吻）

---

## 项目结构（开发者/想看代码的人）

- `amadeus_thread0/cli.py`：命令行入口（交互 + 审批）
- `amadeus_thread0/graph.py`：对话图（加载记忆/抽取记忆/检索/对话 + 工具）
- `amadeus_thread0/tools.py`：工具定义
- `amadeus_thread0/memory_store.py`：SQLite 存储
- `amadeus_thread0/tool_registry.py`：工具注册与分组（base/extended、MCP 防线占位）
- `amadeus_thread0/tts_io.py`：TTS I/O（DashScope Realtime + 声音复刻缓存）

---

## 环境变量速查（最常用）

完整列表以 `.env.example` 为准；这里列最常改的：

- 跑起来必须：
  - `DEEPSEEK_API_KEY`

- 数据目录/线程：
  - `AMADEUS_DATA_DIR`
  - `AMADEUS_THREAD_ID`

- 工具防线：
  - `AMADEUS_TOOL_CALLS_MAX`
  - `AMADEUS_TOOL_TIMEOUT_S`
  - `AMADEUS_TOOLSET_TTL_S`

- Legacy 表（一般不要开）：
  - `AMADEUS_LEGACY_TABLES=0|1`

- sqlite-vec（可选；用于把向量 KNN 从 Python 扫描提速到 SQLite 内部）：
  - `AMADEUS_SQLITE_VEC=off|auto|on`
    - `off`：默认值，禁用 sqlite-vec（仍会走 embedding + Python rerank / LIKE 回退，不影响“能不能检索”，只影响性能）
    - `auto`：尽力启用 sqlite-vec（失败自动回退到 Python rerank）
    - `on`：强制启用 sqlite-vec（失败直接报错，避免你以为启用了但其实没生效）

- 双轨上下文滚动压缩（当前为代码内常量，可按需改 config.py）：
  - `CONTEXT_TRIM_TRIGGER_MESSAGES=40`：超过该 messages 条数触发一次压缩
  - `CONTEXT_KEEP_LAST_MESSAGES=20`：压缩后保留最近 messages 数
  - `REFLECT_MIN_TOTAL_MOMENTS=20` 且 `REFLECT_MIN_NEW_MOMENTS=8`：满足双门槛才自动提出 reflections 候选

- MCP（默认禁用；启用后可通过 `langchain-mcp-adapters` 动态加载工具，并写入来源追溯）：
  - `AMADEUS_MCP_ENABLED=0|1`
  - `AMADEUS_MCP_SERVER_ALLOWLIST`
  - `AMADEUS_MCP_TOOL_ALLOWLIST`
  - `AMADEUS_MCP_CALLS_MAX`
  - `AMADEUS_MCP_TIMEOUT_S`
