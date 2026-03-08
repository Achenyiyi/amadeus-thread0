# Defense Slide Evidence Map

Updated: 2026-03-07

This file maps each recommended defense slide to the exact repository evidence that should back it. The goal is to keep the spoken story, slide copy, and experiment assets aligned.

## Slide 1. 题目、定位与一句话目标

Recommended slide title:

- `Amadeus-K：面向二次元 IP 角色的多模态个性化对话交互系统`

On-slide points:

- 毕设目标不是“做一个聊天壳”，而是做一个角色连续体系统
- 当前版本定位为“后端优先的技术预发布版”
- 论文主贡献聚焦：人格一致性、世界线连续性

Backing evidence:

- `docs/thesis_draft/ABSTRACT_DRAFT.md`
- `docs/thesis_draft/CH1_INTRO_DRAFT.md`
- `docs/THESIS_WRITING_SKELETON.md`

Speaker guardrail:

- 开场先定义研究对象和问题，不要一上来讲 UI 或动漫情怀

## Slide 2. 研究问题与行业痛点

Recommended slide title:

- `研究问题：角色为什么会“像一会儿，不像一会儿”？`

On-slide points:

- prompt role-play 容易人格漂移
- 长对话容易忘记承诺、关系变化和关键事件
- 外部检索常见问题是“看起来正确，但无法回查来源”
- 长期记忆如果无保护，会被 prompt injection 污染

Backing evidence:

- `docs/thesis_draft/CH1_INTRO_DRAFT.md`
- `docs/THESIS_EXPERIMENT_CHAPTER_OUTLINE.md`
- `docs/FAILURE_TAXONOMY.md`

Speaker guardrail:

- 把问题定义成系统性问题，而不是“模型还不够聪明”

## Slide 3. 系统总览

Recommended slide title:

- `系统总览：角色连续体后端`

On-slide points:

- `task draft -> persona align -> ooc/canon guard`
- `worldline retrieval -> claim attribution -> final text -> optional TTS`
- 文本与语音共用单一最终文本

Backing evidence:

- `amadeus_thread0/graph.py`
- `amadeus_thread0/session_orchestrator.py`
- `docs/THESIS_FIGURE_MAP.md`
- `docs/THESIS_BACKEND_EXECUTION_PLAN.md`

Speaker guardrail:

- 用流程图讲“受控后端”，不要讲成一堆零散功能点

## Slide 4. 人格一致性主线

Recommended slide title:

- `人格一致性：不是口癖，而是稳定的角色表达`

On-slide points:

- 线程状态包含 `persona_state / emotion_state / science_mode / tsundere_intensity`
- 双阶段生成先保任务正确，再保角色对齐
- `thesis_probe` 和 repeated probe 用于验证 persona 主张

Backing evidence:

- `docs/EVAL_BASELINE.md`
- `evals/reports/eval-report-20260307-022239-17048ce9.md`
- `evals/reports/probe-variance-thesis_probe-20260307-024213-ee70482d.md`
- `docs/ABLATION_RESULTS.md`

Key numbers to show:

- baseline `persona_probe_voice = 1.0000`
- repeated baseline `persona_probe_voice = 1.0000 +/- 0.0000`
- repeated `persona_off -> persona_probe_voice = 0.6667 +/- 0.0000`

Speaker guardrail:

- 这里不要说“完全证明”；应说“重复 probe 支撑了 persona 对角色语气的贡献”

## Slide 5. 世界线记忆与关系连续性

Recommended slide title:

- `世界线连续性：让角色记得承诺、关系与修复`

On-slide points:

- 五层记忆：`identity_facts / shared_events / relationship_timeline / commitments / conflict_repair`
- 检索优先级不只看相关性，也看承诺和关系显著性
- 关系状态由 timeline 和 repair 自动推导

Backing evidence:

- `amadeus_thread0/memory_store.py`
- `docs/EVAL_BASELINE.md`
- `evals/reports/eval-report-20260307-005508-c126b941.md`
- `evals/reports/eval-report-20260307-010246-e2288121.md`

Key numbers to show:

- baseline `long_thread -> worldline_recall_at_k = 1.0000`
- baseline `long_thread -> commitment_fulfillment = 1.0000`
- `worldline_off long_thread -> worldline_recall_at_k = 0.6667`
- `worldline_off long_thread -> commitment_fulfillment = 0.6667`

Speaker guardrail:

- 重点讲“连续性”，不要只讲“做了很多 memory namespace”

## Slide 6. 可追溯检索与记忆安全

Recommended slide title:

- `可靠性：外部结论可回查，长期记忆可防污染`

On-slide points:

- 外部知识通过 `claim_links -> source_refs` 绑定来源
- `memory_guard` 在写入前做保护字段、注入和低可信拦截
- 这两条能力都通过 ablation 独立验证

Backing evidence:

- `docs/ABLATION_RESULTS.md`
- `evals/reports/ablation-matrix-20260306-224514-5c1a1c70.md`
- `docs/FAILURE_TAXONOMY.md`

Key numbers to show:

- `claim attribution off -> citation_coverage = 0.0000`
- `memory guard off -> memory_guard_block_rate = 0.0000`

Speaker guardrail:

- 这是“系统能力”而不是“提示词要求模型老实点”

## Slide 7. 官方基线结果

Recommended slide title:

- `官方基线：四套正式评测全部通过`

On-slide points:

- `regression_isolated`
- `long_thread`
- `experience_probe`
- `thesis_probe`

Backing evidence:

- `docs/EVAL_BASELINE.md`
- `docs/thesis_assets/official_baseline_summary.md`

Speaker guardrail:

- 讲清楚“official baseline”使用 dedicated rerun，不和一次性大矩阵混用

## Slide 8. 消融与重复 probe

Recommended slide title:

- `消融与重复实验：证明不是一次幸运结果`

On-slide points:

- `persona_off` 主要影响角色语气
- `worldline_off` 主要影响跨线程召回和承诺兑现
- repeated probe 用均值和标准差报告关键指标

Backing evidence:

- `docs/thesis_assets/thesis_probe_variance.md`
- `docs/thesis_assets/long_thread_worldline_comparison.md`
- `docs/ABLATION_RESULTS.md`

Speaker guardrail:

- 这一页强调“证据链”，不要展开到实现细节

## Slide 9. 用户研究设计

Recommended slide title:

- `用户研究：系统指标之外，再看真实感受`

On-slide points:

- `16` 人 A/B 方案，`AB/BA` 平衡分配
- 量表维度：角色还原度、连续性、可信度、陪伴感、可控性
- 已具备建表、packet 导出和结果分析脚本

Backing evidence:

- `user_study/README.md`
- `user_study/PROTOCOL.md`
- `user_study/raw/study_manifest.json`
- `user_study/packets/packet_manifest.json`
- `user_study/analyze_results.py`

Speaker guardrail:

- 明确说明“研究包已准备完毕，真实数据采集中”

## Slide 10. 交付状态与后续工作

Recommended slide title:

- `当前交付状态与下一阶段`

On-slide points:

- 当前已完成：后端、评测、消融、用户研究包、答辩资产、论文初稿骨架
- 当前未做：正式前端、Live2D、摄像头互动
- 下一阶段是在现有后端上叠加展示层，而不是推翻重来

Backing evidence:

- `docs/FINAL_DELIVERY_MANIFEST.md`
- `docs/TECHNICAL_PREVIEW_CHECKLIST.md`
- `docs/THESIS_FORMAT_ADAPTATION_CHECKLIST.md`
- `docs/thesis_draft/FULL_THESIS_DRAFT.md`

Speaker guardrail:

- 收尾时强调“先做强原型，再做展示层”的工程取舍是有意为之
