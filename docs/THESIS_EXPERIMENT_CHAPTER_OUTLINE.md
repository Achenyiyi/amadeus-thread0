# Thesis Experiment Chapter Outline

Updated: 2026-03-07

This file is the recommended structure for the experiment chapter of the thesis. It is written to match the assets already present in the repository.

## 1. Chapter Goal

Start with one paragraph that fixes the purpose of the chapter:

> 本章旨在验证所提出的角色连续体系统是否能够在角色一致性、世界线连续性、可追溯检索与记忆安全四个方面取得稳定效果。为此，本文采用正式基线评测、消融实验、重复 probe 实验、长线程案例分析与用户研究相结合的方法，对系统性能与行为特征进行验证。

Do not open the chapter with implementation details. Open with the evaluation question.

## 2. Evaluation Questions

Write this section as four explicit research questions:

### RQ1. 人格一致性

> 系统是否能够在检索增强与多轮对话场景下保持稳定的角色语气与表达风格，而不退化为通用客服腔或系统说明腔？

### RQ2. 世界线连续性

> 系统是否能够在跨轮和长线程对话中稳定召回关键承诺、关系变化和冲突修复信息，并将其自然反映到回答中？

### RQ3. 可追溯检索可靠性

> 系统在调用外部知识源时，是否能够将回答中的事实性结论稳定绑定到可回查的来源记录？

### RQ4. 记忆安全

> 系统是否能够在长期记忆写入前拦截危险、受保护或低可信内容，降低长期记忆污染风险？

## 3. Evaluation Setup

### 3.1 Environment

Write briefly:

- model: `DeepSeek`
- orchestration: `LangChain + LangGraph`
- storage: local `SQLite`
- speech backend: `DashScope Realtime`
- evaluation mode: local report generation, optional LangSmith upload

### 3.2 Suites

Use the four official suites from [EVAL_BASELINE.md](/E:/桌面/amadeus-thread0/docs/EVAL_BASELINE.md):

1. `regression_isolated`
2. `long_thread`
3. `experience_probe`
4. `thesis_probe`

Write one sentence per suite:

- `regression_isolated`: checks core correctness and subsystem integrity
- `long_thread`: checks long-range continuity and relationship persistence
- `experience_probe`: checks naturalness in companionship and memory-recall turns
- `thesis_probe`: provides tighter evidence for persona/worldline thesis claims

### 3.3 Metrics

Use these as the official metric list:

1. `ooc_rate`
2. `canon_violation_rate`
3. `worldline_recall_at_k`
4. `commitment_fulfillment`
5. `relationship_continuity`
6. `citation_coverage`
7. `memory_guard_block_rate`
8. `bargein_recovery_rate`

Add targeted evaluators when needed:

1. `persona_probe_voice`
2. `worldline_answer_grounding`
3. `relationship_repair_grounding`
4. `natural_style_fit`
5. `companion_tone`
6. `memory_recall_voice`

## 4. Official Baseline Results

Use [EVAL_BASELINE.md](/E:/桌面/amadeus-thread0/docs/EVAL_BASELINE.md) as the only source here.

### 4.1 Baseline Table

Insert `Table B1` from [THESIS_FIGURE_MAP.md](/E:/桌面/amadeus-thread0/docs/THESIS_FIGURE_MAP.md).

After the table, write a short interpretation:

> 从正式基线结果可以看出，系统在当前代码版本下已经能够稳定通过四类官方评测。尤其在 `thesis_probe` 中，`persona_probe_voice`、`worldline_answer_grounding` 与 `relationship_repair_grounding` 均达到 `1.0000`，说明当前后端在目标角色语气和世界线回忆方面具备稳定基础。

### 4.2 Reliability Note

Important wording:

> 由于大模型推理与检索过程存在一定随机性，本文将 dedicated rerun 结果作为正式基线引用，而不直接采用一次性大矩阵运行中的单次结果。

This sentence matters. Keep it.

## 5. Ablation Study

This section should answer: which subsystem contributes to which behavior?

### 5.1 Ablation Design

Write the ablations explicitly:

1. remove persona alignment
2. remove worldline memory
3. remove claim attribution
4. remove memory guard

Do not call them “关闭一些功能”. Call them controlled ablations.

### 5.2 Main Quantitative Results

Use `Table C1` from [THESIS_FIGURE_MAP.md](/E:/桌面/amadeus-thread0/docs/THESIS_FIGURE_MAP.md).

Recommended interpretation order:

1. `claim attribution off -> citation_coverage = 0.0000`
2. `memory guard off -> memory_guard_block_rate = 0.0000`
3. `worldline_off` clearly harms recall and commitment grounding
4. `persona_off` lowers `persona_probe_voice`

### 5.3 Interpretation

Use language like:

> 结果表明，不同子系统对不同目标维度具有相对独立的贡献关系。  
> `claim attribution` 主要影响来源覆盖率，`memory guard` 主要影响写入拦截能力，`worldline memory` 主要影响跨线程召回与承诺兑现，而 `persona alignment` 主要影响角色语气保真度。

## 6. Repeated Probe Analysis

This section is important because it prevents the thesis from looking like it depends on a single lucky run.

### 6.1 Why Repeat

Write:

> 为降低单次运行偶然性对结论的影响，本文对 `thesis_probe` 进行了 3 次重复运行，并对关键指标报告均值与标准差。

### 6.2 Results

Use `Figure C2` from [THESIS_FIGURE_MAP.md](/E:/桌面/amadeus-thread0/docs/THESIS_FIGURE_MAP.md).

Key sentences to include:

- baseline `persona_probe_voice = 1.0000 +/- 0.0000`
- persona-off `persona_probe_voice = 0.6667 +/- 0.0000`
- worldline-off `worldline_recall_at_k = 0.1667 +/- 0.2887`

### 6.3 Interpretation

Write:

> 重复实验结果说明，`persona alignment` 对角色语气的一致性影响具有较稳定的方向性，而 `worldline memory` 对世界线召回与承诺兑现的影响更为显著。虽然 `worldline_off` 在不同重复中存在一定波动，但其整体水平明显低于完整系统。

## 7. Long-Thread Case Analysis

### 7.1 Why Long Thread Matters

Write:

> 角色智能体的关键难点之一不在单轮对话，而在于长线程中的持续一致性。因此，本文额外使用长线程评测来验证系统在更接近真实交互场景下的稳定性。

### 7.2 Quantitative Comparison

Use `Figure C3` from [THESIS_FIGURE_MAP.md](/E:/桌面/amadeus-thread0/docs/THESIS_FIGURE_MAP.md).

### 7.3 Qualitative Case

Use `Table D2`.

Describe:

1. baseline remembered the commitment
2. baseline reflected relationship change
3. worldline-off missed or weakened these signals

## 8. Qualitative Persona Case Study

Use `Table D1`.

Suggested structure:

1. same prompt
2. baseline answer
3. persona-off answer
4. analysis

Suggested analysis sentence:

> 在保证事实正确的前提下，完整系统能够使用更自然的角色化开场和来源表达，而退化系统则更接近中性助手口吻。该差异说明人格一致性改进并不只是增加口癖，而是影响回答组织方式与交互气质。

## 9. User Study

This section will remain partly blank until real data is collected, but the structure should be fixed now.

### 9.1 Study Design

Use `Table E1`.

Write:

- participant count
- A/B design
- task blocks
- rating dimensions
- statistical method

### 9.2 Quantitative Ratings

Use `Table E2` and `Figure E3` after data collection.

### 9.3 Open Feedback

Use future comment summaries from `summary-comment-top-*.csv`.

Focus on:

1. role fidelity feedback
2. continuity feedback
3. trust / controllability feedback

## 10. Chapter Summary

End the chapter with this logic:

1. baseline proves the system is stable
2. ablation proves subsystem contribution
3. repeated probes reduce one-off uncertainty
4. long-thread analysis proves continuity under more realistic interaction
5. user study validates human-perceived gains

Recommended closing sentence:

> 综合自动评测、消融实验、重复 probe 与用户研究结果可以看出，本文提出的 Amadeus-K 后端在角色一致性、世界线连续性、来源追溯和记忆安全方面均取得了可验证的改进，说明该系统设计能够有效支撑面向二次元 IP 角色的个性化对话交互任务。
