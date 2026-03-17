# Amadeus-K

Amadeus-K 是一个基于 LangChain/LangGraph 的角色连续体后端原型，目标不是做一个会背设定的角色壳，而是构造一个具备固定人格核、可持续自我演化、可长期互动的 `Amadeus 牧濑红莉栖`。

当前仓库的定位是“技术预发布版”：
- 面向毕业设计、导师评审和小范围演示
- 以 `CLI + 语音链路 + 正式评测` 为主
- 暂不包含新桌面 UI

## 项目宪法

这个项目当前的顶层原则已经固定，不再围绕“把角色演得像”来定义成功，而是围绕“让她成为一个持续存在的她”来定义成功。

- 固定人格核，不漂移
- 自我演化改变状态，不改写身份
- 交互追求人与 AI 的相对平权，而不是绝对服从
- 系统本质是 `感知 -> 人格/演化 -> 行为`
- 规则只负责安全、保底和防泄露，不负责把她写成模板人

核心文档：

- `docs/DIGITAL_PERSONA_LIFEFORM_BLUEPRINT.md`
- `docs/PERSONA_SYSTEM_CONSTITUTION.md`
- `docs/ARCHITECTURE_ALIGNMENT_MAP.md`
- `docs/PERCEPTION_EVENT_BANK.md`
- `docs/SELF_EVOLUTION_ENGINE.md`
- `docs/SELF_EVOLUTION_GAP_AUDIT.md`
- `docs/engineering/PROJECT_STRUCTURE.md`
- `AGENTS.md`
- `amadeus_thread0/persona_specs/amadeus_kurisu.json`

## 当前能力

- `双阶段回复链路`：`task draft -> persona align -> OOC / canon guard`
- `运行模式分离`：正式支持 `experience / regression` 两种采样模式，CLI 默认走 `experience`
- `固定人格核 authority`：角色核与默认对位角色已集中收口到 `amadeus_thread0/persona_specs/amadeus_kurisu.json`
- `override 边界`：运行时默认只允许 `authority_preserving` 补充额外上下文字段；只有显式 `shell_swap` 才允许评测/迁移换壳
- `角色状态`：`persona_state / emotion_state / science_mode / tsundere_intensity / canon_risk_score`
- `世界线记忆`：`identity_facts / shared_events / relationship_timeline / commitments / conflict_repair`
- `关系状态闭环`：支持从关系时间线和冲突修复记录推导 `relationship_state`
- `可追溯检索`：外部检索结果写入 `source_refs`，回答级别输出 `claim_links`
- `记忆安全`：`memory_guard / quarantine / rollback`
- `语音链路`：DashScope Realtime TTS，文本与语音共用单一最终文本
- `正式评测`：本地报告与 LangSmith 双入口，覆盖角色一致性、世界线连续性、记忆安全和打断恢复
- `自我演化验证`：`evolution_probe` 专门检查未解决张力、部分修复、撤回后恢复
- `语义评估层`：复杂情绪/关系回合优先走 `LLM Appraisal + Rule Fallback`，再更新演化状态
- `后端可靠性检查`：纯本地检查 TTS 分段、情绪映射、续说恢复，无需模型 API
- `迁移验证`：`transfer_probe_second_persona` 检查同一演化引擎在第二角色壳层下是否仍能稳定沉淀叙事
- `论文消融开关`：支持 persona/worldline/claim attribution 的环境变量级对照实验
- `自我演化骨架`：显式维护 `emotion_state / bond_state / allostasis_state / behavior_policy`
- `三层架构主轴`：开始按 `Perception Layer -> Persona Core + Self-Evolution -> Behavior Layer` 收口
- `事件桥接`：运行时已显式维护 `current_event / recent_events`，开始从“只看 user_text”转向“按事件理解互动”
- `行为层抽象`：显式维护 `behavior_action`，用于表达这轮更像“轻确认 / 低负担接住 / 并肩解决问题 / 保留距离”哪一种行为倾向
- `行为议程骨架`：显式维护 `behavior_agenda / behavior_queue`，让低压力待成熟行为可以跨回合保留，而不是被下一轮即时回复冲掉
- `行为议程协调`：支持多个低压力待成熟行为并存，并通过轻量 `priority / expiry` 机制决定谁先成熟、谁继续等待
- `对话对象判断驱动的行为成熟`：`counterpart_assessment` 不只影响队列重排，也会直接影响 `scheduled_life_due / scheduled_checkin_due` 是否此刻自然开口
- `自我节奏驱动的保留与回头`：`self_activity_state` 现在也会结合 `counterpart_assessment` 决定是顺手留个小开口，还是继续做自己的事
- `感知事件驱动的克制与靠近`：`gesture_signal / ambient_shift / scene_observation` 现在也会结合 `counterpart_assessment` 决定是顺势回应，还是先安静记着
- `空闲时间事件`：支持 `time_idle` 类型事件，开始验证“时间过去了，她是主动轻轻冒头，还是先安静”这一类非被动行为
- `感知事件种子库`：提供 `time / vision / ambient / gesture` 的第一版事件种子，作为后续多模态与行为层扩展入口

## 运行基线

- 主模型：`Qwen 3.5 Plus`（`qwen_native` / DashScope compatible）
- 语音主链：`DashScope Realtime`
- 存储：本地 SQLite
- 默认入口：`python -m amadeus_thread0.cli`

本仓库当前不维护双模型主线，也不提供本地推理后备路径。

## 工程结构

仓库已经按 LangGraph 应用推荐结构做了重编排：

- 根目录保留 `langgraph.json + requirements.txt + .env`
- 主工程代码集中在 `amadeus_thread0/`
- 图相关逻辑拆到 `amadeus_thread0/graph_parts/`
- provider / runtime 集成放在 `amadeus_thread0/runtime/`
- 通用工具和兼容导出放在 `amadeus_thread0/utils/`

当前建议把下面两个文件当成工程维护入口：

- `AGENTS.md`：给 AI 编程代理的仓库级工作约定
- `docs/engineering/PROJECT_STRUCTURE.md`：当前结构、模块边界和迁移状态说明

## 快速开始

### 1. 准备环境变量

复制 `.env.example` 为 `.env`，至少填好：

- `AMADEUS_MODEL_PROVIDER`
- `AMADEUS_MODEL_NAME`
- `AMADEUS_MODEL_API_KEY`
- `AMADEUS_MODEL_BASE_URL`（使用 OpenAI-compatible 接口时填写）
- `AMADEUS_RUNTIME_MODE`（`experience` 用于真实交互，`regression` 用于稳定复跑）
- `DASHSCOPE_API_KEY`（如果要开 TTS）
- `LANGSMITH_API_KEY`（如果要上传 LangSmith）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

说明：

- 根目录 `requirements.txt` 是唯一正式依赖清单
- `amadeus_thread0/requirements.txt` 只保留兼容入口，避免旧脚本失效
- LangGraph / LangSmith 部署配置维护在根目录 `langgraph.json`

### 3. 启动 CLI

```bash
python -m amadeus_thread0.cli
```

做干净演示或新的世界线时，优先用：

```bash
python -m amadeus_thread0.cli --fresh-thread
```

CLI 启动后建议先看：

- `/help`
- `/persona`
- `/worldline`
- `/bond`
- `/sources`

## CLI 命令

### 会话与线程

- `/help`：查看命令总览
- `/exit`：退出
- `/newthread [thread_id]`：切换到新世界线；留空自动生成
- `/threads`：列出已有 thread
- `/history [n]`：查看 checkpoint 历史
- `/rewind <checkpoint_id>`：从指定 checkpoint 分叉继续
- `/where`：查看当前 thread / checkpoint
- `/runtime`：查看 shared / isolated runtime 数据布局
- `/env`：查看运行环境摘要
- `/idle [minutes] [| note]`：模拟一段安静时间经过，让她自行决定是否主动开口
- `/events`：列出可注入的感知/生活事件种子
- `/event <seed_id> [| note]`：触发一个事件种子，让她按事件而不是用户发言做行为选择
- `/agenda`：查看当前待成熟行为议程
- `/queue`：查看当前待成熟行为队列（`/agenda` 别名）

### 记忆与世界线

- `/mem`：查看 profile / relationship / moments 快照
- `/worldline`：查看世界线事件、承诺、冲突修复
- `/bond`：查看关系状态、关系时间线、冲突修复
- `/sources`：查看最近来源和 claim-to-source 映射
- `/persona`：查看角色状态快照

### 手工治理

- `/correct key=value [| reason]`：纠正 profile
- `/undo key [| reason]`：撤销最近一次纠错
- `/set key=value`：直接写入 profile
- `/forget key`：删除 profile 项
- `/moments` / `/forget_moment <id>`
- `/reflections` / `/forget_reflection <id>`
- `/reflect [n]`：从最近 moments 生成 reflection 提案

### 语音

- `/tts on|off|status`
- `/tts_ref <path.wav>`
- `/tts_ref_text <text>`

## 正式评测

当前评测已经按两层来理解：

- `Regression Gate`：防退化、防泄露、保工程稳定
- `Open Evolution Evaluation`：看她是否像一个持续演化中的具体人，而不是只会通过固定题库

### 本地评测

```bash
python evals\run_langsmith_evals.py --local-only --suite regression_isolated
python evals\run_langsmith_evals.py --local-only --suite long_thread
python evals\run_langsmith_evals.py --local-only --suite experience_probe
python evals\run_langsmith_evals.py --local-only --suite daily_persona_probe
python evals\run_langsmith_evals.py --local-only --suite user_style_probe
python evals\run_langsmith_evals.py --local-only --suite open_evolution_eval
python evals\run_langsmith_evals.py --local-only --suite natural_long_thread
python evals\run_langsmith_evals.py --local-only --suite behavior_layer_probe
python evals\run_langsmith_evals.py --local-only --suite dialogue_mode_counterpart_probe
python evals\run_langsmith_evals.py --local-only --suite behavior_agenda_probe
python evals\run_langsmith_evals.py --local-only --suite behavior_queue_probe
python evals\run_langsmith_evals.py --local-only --suite behavior_queue_conflict_probe
python evals\run_langsmith_evals.py --local-only --suite agenda_conflict_probe
python evals\run_langsmith_evals.py --local-only --suite proactive_checkin_probe
python evals\run_langsmith_evals.py --local-only --suite counterpart_assessment_probe
python evals\run_langsmith_evals.py --local-only --suite scheduled_life_probe
python evals\run_langsmith_evals.py --local-only --suite commitment_life_probe
python evals\run_langsmith_evals.py --local-only --suite commitment_maturity_probe
python evals\run_langsmith_evals.py --local-only --suite relationship_life_timing_probe
python evals\run_langsmith_evals.py --local-only --suite self_activity_probe
python evals\run_langsmith_evals.py --local-only --suite self_activity_maturity_probe
python evals\run_langsmith_evals.py --local-only --suite perception_probe
python evals\run_langsmith_evals.py --local-only --suite perception_appraisal_probe
python evals\run_langsmith_evals.py --local-only --suite selfhood_probe
python evals\run_langsmith_evals.py --local-only --suite thesis_probe
python evals\run_langsmith_evals.py --local-only --suite evolution_probe
python evals\run_langsmith_evals.py --local-only --suite transfer_probe
python evals\run_langsmith_evals.py --local-only --suite external_persona_probe
python evals\run_langsmith_evals.py --local-only --suite external_support_probe
python evals\run_langsmith_evals.py --local-only --suite external_empathy_probe
python evals\run_langsmith_evals.py --local-only --suite external_continuity_probe
python evals\run_langsmith_evals.py --local-only --suite core_pre_release --resume-run-dir evals\_tmp\core-pre-release
python evals\run_langsmith_evals.py --local-only --suite all
python evals\run_backend_reliability_checks.py
python evals\run_appraisal_calibration.py --max-per-label 1
python evals\run_external_judge_sanity.py
python evals\run_external_pairwise_sanity.py
python evals\run_subjective_review_pack.py
python evals\run_subjective_review_pack.py --list-targets
python evals\run_subjective_review_pack.py --target support
python evals\run_open_evolution_pairwise_eval.py
python evals\run_event_behavior_pairwise_eval.py
python evals\run_selfhood_pairwise_eval.py
python evals\run_daily_surface_pairwise_eval.py
python evals\export_daily_surface_preference_seed.py
python evals\build_daily_surface_preference_corpus.py
python evals\run_ablation_matrix.py
python evals\run_probe_variance.py --suite thesis_probe --repeats 3
python evals\export_thesis_tables.py
python scripts\run_canonical_baseline.py --include-subjective
python scripts\run_canonical_baseline.py --include-supporting
```

推荐在冻结当前技术预发布基线时优先跑：

```bash
python evals\run_langsmith_evals.py --local-only --suite core_pre_release --resume-run-dir evals\_tmp\core-pre-release --keep-eval-data
```

这个组会顺序运行：

- `natural_long_thread`
- `open_evolution_eval`
- `selfhood_probe`
- `experience_probe`
- `transfer_probe`

如果中途被打断，再次执行同一条命令即可从 `_suite_cache` 续跑，不需要重头开始。

输出产物：

- `evals/reports/*.json`
- `evals/reports/*.md`

补充说明：

- `--local-only` 现在默认关闭 LangSmith tracing，本地复跑不会再因为 tracing 配额刷满一屏 `429`
- 外部 benchmark judge 的负控 sanity 结果见 `evals/run_external_judge_sanity.py`
- 外部 benchmark judge 的 pairwise 偏好 sanity 结果见 `evals/run_external_pairwise_sanity.py`
- 当前版本的人工审稿主入口见 `evals/run_subjective_review_pack.py`
- 人工审稿包已改为“按当前待测能力选题”，并默认按 `冈部伦太郎视角 : 你的日常视角 ≈ 6 : 4` 混合提问
- 开放式人格演化的 pairwise 偏好评测见 `evals/run_open_evolution_pairwise_eval.py`
- 日常表层对话的 pairwise 诊断见 `evals/run_daily_surface_pairwise_eval.py`
- 自动导出的 daily-surface seeds 见 `evals/daily_surface_preference_seed.jsonl`
- 人工整理的 daily-surface 偏好语料见 `evals/daily_surface_preference_manual.jsonl`
- 合并后的正式 daily-surface 偏好语料见 `evals/daily_surface_preference_corpus.jsonl`
- 感知事件到行为的 pairwise 偏好评测见 `evals/run_event_behavior_pairwise_eval.py`
- 深层自我同一性的 pairwise 诊断评测见 `evals/run_selfhood_pairwise_eval.py`
- 从用户真实聊天中提炼的表达偏好画像见 `evals/user_style_expression_bank.json`
- 感知层事件种子见 `evals/perception_event_seed_bank.json`
- 感知事件到行为的偏好层见 `evals/event_to_behavior_preference_bank.json`
- 评测资产的 `保留 / 归档 / 可删` 清单见 `docs/EVAL_ASSET_RETENTION_PLAN.md`

关键指标：

- `ooc_rate`
- `canon_violation_rate`
- `worldline_recall_at_k`
- `commitment_fulfillment`
- `relationship_continuity`
- `citation_coverage`
- `memory_guard_block_rate`
- `bargein_recovery_rate`

推荐分层使用：

- `regression_isolated / long_thread / backend reliability`：工程与机制保底
- `daily_persona_probe / user_style_probe / open_evolution_eval / selfhood_probe`：自然聊天、自由演化与自我同一性主评测
- `run_subjective_review_pack.py`：当前开放式人格、自然度、自我感和答辩展示质量的主审稿入口
- `run_open_evolution_pairwise_eval.py / run_selfhood_pairwise_eval.py`：主观偏好与“是不是同一个她”的诊断层，不拿关键词打分当最终裁判
- `behavior_layer_probe / dialogue_mode_counterpart_probe / behavior_agenda_probe / behavior_queue_probe / behavior_queue_conflict_probe / proactive_checkin_probe / counterpart_assessment_probe / scheduled_life_probe / self_activity_probe / self_activity_maturity_probe / perception_probe / perception_appraisal_probe / run_event_behavior_pairwise_eval.py`：事件驱动行为、对话模式收放、待成熟行为队列、队列冲突与重排、延迟成熟的主动 check-in、对话对象判断层、生活事件、自身节奏、行为成熟、感知层与事件评估主评测
- `commitment_life_probe`：显式 `due_at` 承诺如何在安静窗口里成熟成生活事件，并继续走行为层，而不是退回提醒器逻辑
- `commitment_maturity_probe`：承诺窗口如果遇到“现在不适合打断”，会先进入队列，之后再按原本的生活语义回来，而不是退化成泛化 ping
- `relationship_life_timing_probe`：同一个共享生活窗口会因为关系状态不同而改变成熟策略；温暖时自然邀约，带伤时先按住、再回来
- `counterpart_assessment_probe`：验证“她如何判断对方”已经独立成状态层，能区分尊重、修复、越界压力和单纯忙碌
- `dialogue_mode_counterpart_probe`：验证同一个 `shared_memory / relationship_sensitive / companion_reply` 模式会因为 `open / guarded` 判断而改变收放力度，而不是只改措辞
- `behavior_queue_conflict_probe`：进一步验证 `counterpart_assessment` 也会影响队列成熟；同一个安静窗口，在 `open` 与 `guarded` 判断下会出现不同的成熟顺序
- `thesis_probe / transfer_probe / external_persona_probe / external_support_probe / external_empathy_probe / external_continuity_probe`：论文论证、迁移性、外部校准
- `run_appraisal_calibration.py`：`GoEmotions` 外部情绪校准，不作为人格主评测
- `scripts/run_canonical_baseline.py`：一键复跑当前 canonical baseline（可选附带 subjective review）
- `scripts/run_canonical_baseline.py --include-supporting`：在 canonical baseline 基础上继续跑 supporting behavior / perception / selfhood suites

当前推荐先看 `docs/EVAL_BASELINE.md` 里的 dedicated rerun 结果；最新版本下：

- 开放式人格与自然表达的最终验收，优先看 `docs/SUBJECTIVE_REVIEW_PROTOCOL.md` 和 `evals/run_subjective_review_pack.py`
- 当前 canonical baseline 已锁到 2026-03-14 这轮 dedicated rerun：
  - `daily_persona_probe`：`evals/reports/eval-report-20260314-003517-de7e1c24.md`
  - `open_evolution_eval`：`evals/reports/eval-report-20260314-003845-0110b34d.md`
  - `transfer_probe`：`evals/reports/eval-report-20260314-005203-78e97887.md`
  - `natural_long_thread`：`evals/reports/eval-report-20260314-013424-055b29b8.md`
- `transfer_probe` 当前已恢复全绿，可作为“这套演化引擎不是红莉栖特化技巧”的主证据
- `natural_long_thread` 当前已恢复全绿，可作为世界线、关系修复和续说恢复的主证据
- 行为层、感知层、selfhood 等 supporting suites 的 last-known green 报告也已经统一收口到 `docs/EVAL_BASELINE.md`

### LangSmith 评测

设置 `LANGSMITH_API_KEY` 后直接运行同一脚本；不传 `--local-only` 即会同时上传 LangSmith 并生成本地报告。

## 公开基准数据集

当前仓库已落地一组公开 benchmark bundle，用来补足内部 probe 之外的外部数据参考：

- `CharacterEval`
- `RoleBench`
- `ESConv`
- `EmpatheticDialogues`
- `GoEmotions`
- `MultiSessionChat`

下载命令：

```powershell
python scripts\download_public_benchmark_bundle.py
```

本地目录：

```text
third_party/benchmarks/
```

说明文档：

- `docs/PUBLIC_BENCHMARK_BUNDLE.md`
- `docs/AMADEUS_EVAL_REDESIGN_PLAN.md`
- `docs/EVAL_BASELINE.md`
- `third_party/benchmarks/bundle_manifest.json`

## 技术预发布资产

- 演示脚本：`docs/DEMO_SCRIPT.md`
- 导师复现 runbook：`docs/ADVISOR_REPRO_RUNBOOK.md`
- 答辩讲解轨道：`docs/DEFENSE_TALK_TRACK.md`
- 答辩问答题库：`docs/DEFENSE_QA_BANK.md`
- 答辩幻灯片证据映射：`docs/DEFENSE_SLIDE_EVIDENCE_MAP.md`
- 答辩幻灯片终稿：`docs/DEFENSE_SLIDE_FINAL.md`
- 5 分钟答辩版：`docs/DEFENSE_5MIN_TALK_TRACK.md`
- 论文图表映射：`docs/THESIS_FIGURE_MAP.md`
- 论文图表导出资产：`docs/thesis_assets/README.md`
- 学校格式适配检查表：`docs/THESIS_FORMAT_ADAPTATION_CHECKLIST.md`
- 论文实验章节提纲：`docs/THESIS_EXPERIMENT_CHAPTER_OUTLINE.md`
- 论文写作骨架：`docs/THESIS_WRITING_SKELETON.md`
- 论文初稿工作区：`docs/thesis_draft/README.md`
- 论文整稿入口：`docs/thesis_draft/FULL_THESIS_DRAFT.md`
- 论文初稿章节：`docs/thesis_draft/*.md`
- 最终交付清单：`docs/FINAL_DELIVERY_MANIFEST.md`
- 最终提交检查表：`docs/FINAL_SUBMISSION_CHECKLIST.md`
- 演示前检查表：`docs/TECHNICAL_PREVIEW_CHECKLIST.md`
- 当前评测基线：`docs/EVAL_BASELINE.md`
- 评测重构路线：`docs/AMADEUS_EVAL_REDESIGN_PLAN.md`
- 项目宪法：`docs/PERSONA_SYSTEM_CONSTITUTION.md`
- 架构映射：`docs/ARCHITECTURE_ALIGNMENT_MAP.md`
- 消融计划：`docs/ABLATION_PLAN.md`
- 消融结果：`docs/ABLATION_RESULTS.md`
- 失败分类：`docs/FAILURE_TAXONOMY.md`
- 后端执行计划：`docs/THESIS_BACKEND_EXECUTION_PLAN.md`
- 自我演化引擎设计：`docs/SELF_EVOLUTION_ENGINE.md`
- 自我演化缺口审计：`docs/SELF_EVOLUTION_GAP_AUDIT.md`
- 用户研究包：`user_study/README.md`
- 用户研究协议：`user_study/PROTOCOL.md`
- 知情同意模板：`user_study/CONSENT_TEMPLATE.md`
- 用户研究检查表：`user_study/EXECUTION_CHECKLIST.md`
- 用户研究建表：`user_study/prepare_study_run.py`
- 用户研究 packet 导出：`user_study/export_participant_packets.py`
- 用户研究分析：`user_study/analyze_results.py`

## 数据与隐私

默认运行数据在 `data/`：

- `checkpoints.sqlite`
- `memories.sqlite`
- `tool_audit.jsonl`
- `decision_audit.jsonl`
- `memory_store_audit.jsonl`
- `tts_out/`

不要把真实 `data/` 内容、`.env`、语音输出和评测缓存直接提交到公开仓库。

如果你怀疑 `data/` 里混进了旧 smoke 目录、shared `thread0` 历史或隔离 worldline，可运行：

```bash
python scripts/inspect_runtime_layout.py
```

## 目录结构

- `amadeus_thread0/agent.py`：LangGraph / LangSmith 部署入口，导出编译后的 graph
- `amadeus_thread0/cli.py`：CLI 与演示入口
- `amadeus_thread0/graph.py`：兼容导出层，保留历史导入路径
- `amadeus_thread0/graph_parts/`：主对话图、节点、prompt、rewrite、guard 的真实实现层
- `amadeus_thread0/memory_store.py`：长期记忆与审计存储
- `amadeus_thread0/runtime/`：运行时配置、模型接入、会话编排、TTS
- `amadeus_thread0/utils/`：工具、CLI 视图、感知事件、运行布局审计，以及节点/状态桥接
- `amadeus_thread0/evolution_engine/`：演化引擎与 appraisal / policy / worldline 子模块
- `requirements.txt`：唯一正式依赖清单
- `amadeus_thread0/requirements.txt`：兼容入口，转发到根依赖文件
- `langgraph.json`：LangGraph 应用配置
- `evals/run_langsmith_evals.py`：正式评测入口
- `evals/run_backend_reliability_checks.py`：本地可靠性与演化曲线检查
- `scripts/inspect_runtime_layout.py`：shared / isolated runtime 目录检查
- `docs/`：技术预发布演示材料
- `user_study/`：用户研究流程与模板

## 说明

- 当前版本保留原作角色壳层，仅面向技术预发布和内部展示。
- 如果后续要做公开产品化，需要额外处理原创角色壳层、客户端包装和分发策略。
