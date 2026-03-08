# Amadeus-K

Amadeus-K 是一个基于 LangChain/LangGraph 的角色连续体后端原型，目标是复现《命运石之门 0》中 Amadeus 的核心体验：人格稳定、长期连续、可追溯、可审计、可控。

当前仓库的定位是“技术预发布版”：
- 面向毕业设计、导师评审和小范围演示
- 以 `CLI + 语音链路 + 正式评测` 为主
- 暂不包含新桌面 UI

## 当前能力

- `双阶段回复链路`：`task draft -> persona align -> OOC / canon guard`
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

## 运行基线

- 主模型：`DeepSeek`
- 语音主链：`DashScope Realtime`
- 存储：本地 SQLite
- 默认入口：`python -m amadeus_thread0.cli`

本仓库当前不维护双模型主线，也不提供本地推理后备路径。

## 快速开始

### 1. 准备环境变量

复制 `.env.example` 为 `.env`，至少填好：

- `DEEPSEEK_API_KEY`
- `DASHSCOPE_API_KEY`（如果要开 TTS）
- `LANGSMITH_API_KEY`（如果要上传 LangSmith）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动 CLI

```bash
python -m amadeus_thread0.cli
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
- `/newthread`：切换到新世界线
- `/threads`：列出已有 thread
- `/history [n]`：查看 checkpoint 历史
- `/rewind <checkpoint_id>`：从指定 checkpoint 分叉继续
- `/where`：查看当前 thread / checkpoint
- `/env`：查看运行环境摘要

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

### 本地评测

```bash
python evals\run_langsmith_evals.py --local-only --suite regression_isolated
python evals\run_langsmith_evals.py --local-only --suite long_thread
python evals\run_langsmith_evals.py --local-only --suite experience_probe
python evals\run_langsmith_evals.py --local-only --suite daily_persona_probe
python evals\run_langsmith_evals.py --local-only --suite thesis_probe
python evals\run_langsmith_evals.py --local-only --suite evolution_probe
python evals\run_langsmith_evals.py --local-only --suite transfer_probe
python evals\run_langsmith_evals.py --local-only --suite all
python evals\run_backend_reliability_checks.py
python evals\run_ablation_matrix.py
python evals\run_probe_variance.py --suite thesis_probe --repeats 3
python evals\export_thesis_tables.py
```

输出产物：

- `evals/reports/*.json`
- `evals/reports/*.md`

关键指标：

- `ooc_rate`
- `canon_violation_rate`
- `worldline_recall_at_k`
- `commitment_fulfillment`
- `relationship_continuity`
- `citation_coverage`
- `memory_guard_block_rate`
- `bargein_recovery_rate`

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
- `third_party/benchmarks/bundle_manifest.json`

## 技术预发布资产

- 演示脚本：`docs/DEMO_SCRIPT.md`
- 导师复现 runbook：`docs/ADVISOR_REPRO_RUNBOOK.md`
- 答辩讲解轨道：`docs/DEFENSE_TALK_TRACK.md`
- 答辩问答题库：`docs/DEFENSE_QA_BANK.md`
- 答辩幻灯片证据映射：`docs/DEFENSE_SLIDE_EVIDENCE_MAP.md`
- 答辩幻灯片逐页文案：`docs/DEFENSE_SLIDE_DRAFT.md`
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

## 目录结构

- `amadeus_thread0/cli.py`：CLI 与演示入口
- `amadeus_thread0/graph.py`：主对话图
- `amadeus_thread0/memory_store.py`：长期记忆与审计存储
- `amadeus_thread0/session_orchestrator.py`：claim attribution 与续说恢复辅助逻辑
- `amadeus_thread0/tools.py`：工具定义
- `evals/run_langsmith_evals.py`：正式评测入口
- `evals/run_backend_reliability_checks.py`：本地可靠性与演化曲线检查
- `docs/`：技术预发布演示材料
- `user_study/`：用户研究流程与模板

## 说明

- 当前版本保留原作角色壳层，仅面向技术预发布和内部展示。
- 如果后续要做公开产品化，需要额外处理原创角色壳层、客户端包装和分发策略。
