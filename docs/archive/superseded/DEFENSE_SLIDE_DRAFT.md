# Defense Slide Draft

Updated: 2026-03-07

This file is the draft copy for a 10-slide defense deck. Each slide includes the recommended on-slide bullets, the short speaker note, and the evidence source to cite.

## Slide 1. 题目与项目定位

On-slide copy:

- Amadeus-K：面向二次元 IP 角色的多模态个性化对话交互系统
- 技术预发布版，当前以后端、语音链路和正式评测为主
- 主贡献聚焦：人格一致性、世界线连续性

Speaker note:

> 这项工作的目标不是做一个套了角色 prompt 的聊天壳，而是做一个在长期交互中还能保持角色连续性的后端系统。论文阶段，我把重点固定在人格一致性和世界线连续性两条主线上。

Evidence:

- `docs/thesis_draft/ABSTRACT_DRAFT.md`
- `docs/thesis_draft/CH1_INTRO_DRAFT.md`

## Slide 2. 研究问题

On-slide copy:

- 为什么角色会在长对话里漂移成通用助手？
- 为什么承诺、关系变化和关键事件容易被忘记？
- 为什么 RAG 结论常常无法回查来源？
- 为什么长期记忆会成为新的攻击面？

Speaker note:

> 这项工作针对的是角色智能体的四类典型问题：人格漂移、世界线断裂、来源不可追溯和记忆污染。后面的系统设计和实验都围绕这四个问题展开。

Evidence:

- `docs/THESIS_EXPERIMENT_CHAPTER_OUTLINE.md`
- `docs/FAILURE_TAXONOMY.md`

## Slide 3. 总体架构

On-slide copy:

- `task draft -> persona align -> ooc/canon guard`
- `worldline retrieval -> claim attribution -> final text`
- `optional TTS` 与文本共用单一真源

Speaker note:

> 我没有把系统做成松散的 prompt 拼接，而是把角色状态、记忆检索、来源归因、记忆安全和语音编排放进统一图结构里。整个流程的关键是，所有后处理最终都收敛到单一最终文本。

Evidence:

- `amadeus_thread0/graph.py`
- `amadeus_thread0/session_orchestrator.py`
- `docs/THESIS_FIGURE_MAP.md`

## Slide 4. 人格一致性主线

On-slide copy:

- 固定线程状态：`persona_state / emotion_state / science_mode / tsundere_intensity`
- 双阶段生成：先保证任务正确，再做角色对齐
- repeated `thesis_probe` 验证 persona 主线

Speaker note:

> 这里的人格一致性不是看有没有口癖，而是看回答是否稳定符合角色的表达方式、理性风格和关系语境。我们用 dedicated thesis probe 和 repeated probe 来验证这条主张。

Evidence:

- `docs/EVAL_BASELINE.md`
- `docs/thesis_assets/thesis_probe_variance.md`

## Slide 5. 世界线与关系连续性

On-slide copy:

- 五层记忆：身份事实、共同事件、关系时间线、长期承诺、冲突修复
- 检索显式提升 commitments / repair / relationship 的权重
- 关系状态由历史轨迹自动推导，不靠手工设置

Speaker note:

> 世界线连续性的关键不是“存更多记忆”，而是让系统在合适的时候把承诺、关系和修复历史拉回来，并自然地反映到当前回答里。

Evidence:

- `amadeus_thread0/memory_store.py`
- `docs/thesis_assets/long_thread_worldline_comparison.md`

## Slide 6. 可追溯检索与记忆安全

On-slide copy:

- `claim_links -> source_refs`
- `memory_guard -> quarantine -> rollback`
- 两条能力都用 ablation 单独验证

Speaker note:

> 这两条能力的价值在于，它们并不是“看上去有”，而是关闭以后指标会直接掉。也就是说，来源归因和记忆安全都是可测的系统能力。

Evidence:

- `docs/thesis_assets/support_ablation_summary.md`
- `docs/ABLATION_RESULTS.md`

## Slide 7. 官方基线

On-slide copy:

- 四套正式 suite：`regression_isolated / long_thread / experience_probe / thesis_probe`
- 当前 dedicated baseline 全绿
- 后端已经达到技术预发布版标准

Speaker note:

> 这里我强调 dedicated rerun 的 baseline，而不是只展示一次性大矩阵结果。因为对于角色系统，稳定的基线要比一次偶然的好看结果更重要。

Evidence:

- `docs/thesis_assets/official_baseline_summary.md`
- `docs/EVAL_BASELINE.md`

## Slide 8. 消融与重复 probe

On-slide copy:

- `persona_off` 主要影响 `persona_probe_voice`
- `worldline_off` 主要影响 `worldline_recall_at_k / commitment_fulfillment`
- repeated probe 用均值和标准差压随机性

Speaker note:

> 这页的目的不是列很多数字，而是证明两条主贡献确实对应两类不同退化：去掉 persona 会先伤角色语气，去掉 worldline 会先伤跨线程回忆和承诺兑现。

Evidence:

- `docs/thesis_assets/thesis_probe_variance.md`
- `docs/thesis_assets/long_thread_worldline_comparison.md`

## Slide 9. 用户研究与论文资产

On-slide copy:

- `16` 人 A/B 平衡分组
- 量表维度：角色还原度、连续性、可信度、陪伴感、可控性
- 已完成建表、packet 导出、分析脚本和论文初稿骨架

Speaker note:

> 这意味着项目已经不只是工程原型，而是进入了论文实验可执行阶段。下一步是正式收集用户研究数据，并把结果回填到实验章节。

Evidence:

- `user_study/PROTOCOL.md`
- `user_study/raw/study_manifest.json`
- `user_study/packets/packet_manifest.json`
- `docs/thesis_draft/FULL_THESIS_DRAFT.md`

## Slide 10. 当前结论与下一阶段

On-slide copy:

- 当前已完成：后端、评测、消融、用户研究包、答辩资产、论文初稿
- 当前未做：正式前端、Live2D、摄像头互动
- 下一阶段是在现有后端之上叠加展示层

Speaker note:

> 当前项目已经达到“可答辩、可复现、可写论文、可继续产品化”的状态。下一阶段不是重写系统，而是在这套后端之上补足展示层和最终交互形态。

Evidence:

- `docs/FINAL_DELIVERY_MANIFEST.md`
- `docs/TECHNICAL_PREVIEW_CHECKLIST.md`
- `docs/THESIS_FORMAT_ADAPTATION_CHECKLIST.md`
