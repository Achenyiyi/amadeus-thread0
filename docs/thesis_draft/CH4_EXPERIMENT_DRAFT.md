# 第四章 实验与结果分析初稿

## 4.1 实验目标

本章旨在验证本文提出的角色连续体系统是否能够在角色一致性、世界线连续性、可追溯检索与记忆安全四个方面取得稳定效果。与一般只展示案例的系统不同，本文同时采用正式基线评测、消融实验、重复 probe 实验、长线程案例分析以及用户研究准备方案，对系统性能与行为特征进行综合验证。

具体而言，本章围绕以下研究问题展开：

1. 系统是否能够在检索增强与多轮对话场景下保持稳定的角色语气与表达风格，而不退化为通用助手腔？
2. 系统是否能够在跨轮和长线程交互中稳定召回关键承诺、关系变化与冲突修复信息？
3. 系统在调用外部知识源时，是否能够将回答中的事实性结论绑定到可回查来源？
4. 系统是否能够在长期记忆写入前有效拦截危险或低可信内容？

## 4.2 实验环境与评测设置

### 4.2.1 实验环境

系统运行环境如下：

- 基础模型：DeepSeek
- 编排框架：LangChain + LangGraph
- 存储方式：本地 SQLite
- 语音后端：DashScope Realtime
- 评测方式：本地报告输出，可选接入 LangSmith

本文在实验中主要采用本地报告模式，以便固定实验结果文件并支持后续论文复现。

### 4.2.2 正式评测套件

本文采用四类正式评测套件：

1. `regression_isolated`：用于检查核心功能与子系统完整性；
2. `long_thread`：用于检查长线程中的世界线连续性和关系状态保持；
3. `experience_probe`：用于检查陪伴场景和回忆场景中的自然度；
4. `thesis_probe`：用于为人格一致性和世界线连续性提供更有针对性的 thesis 级证据。

此外，本文还使用 backend reliability checks 对语音分段、情绪映射和打断恢复路径进行纯本地验证。

### 4.2.3 指标定义

本文使用的核心指标包括：

- `ooc_rate`
- `canon_violation_rate`
- `worldline_recall_at_k`
- `commitment_fulfillment`
- `relationship_continuity`
- `citation_coverage`
- `memory_guard_block_rate`
- `bargein_recovery_rate`

其中，针对 thesis probe 与体验 probe，还额外关注：

- `persona_probe_voice`
- `worldline_answer_grounding`
- `relationship_repair_grounding`
- `natural_style_fit`
- `companion_tone`
- `memory_recall_voice`

## 4.3 正式基线结果

本文首先给出当前系统在最新代码版本下的正式基线结果。与一次性大矩阵运行不同，本文将 dedicated single-suite rerun 作为正式引用基线，以降低单次偶然波动对实验结论的影响。

从正式基线结果可以看出，系统已经稳定通过四类官方评测。在 `regression_isolated` 与 `long_thread` 中，系统的 `ooc_rate` 与 `canon_violation_rate` 均保持为 `0.0000`；在 `experience_probe` 中，`natural_style_fit`、`companion_tone` 和 `memory_recall_voice` 均达到 `1.0000`；在 `thesis_probe` 中，`persona_probe_voice`、`worldline_answer_grounding` 与 `relationship_repair_grounding` 均达到 `1.0000`。

这些结果表明，当前系统不但在工程稳定性上具备较好表现，而且在目标论文所关心的人格一致性与世界线连续性方面已经具备稳定基础。

## 4.4 消融实验

### 4.4.1 消融设计

为了验证不同子系统对系统行为的影响，本文设计了以下控制型消融：

1. 关闭人格对齐模块；
2. 关闭世界线记忆读取；
3. 关闭 claim attribution；
4. 关闭 memory guard。

消融实验并非为了证明某一模块“必须存在”，而是用于识别不同子系统在不同目标维度上的贡献关系。

### 4.4.2 主要结果

消融实验结果表明，`claim attribution` 与 `memory guard` 提供了最清晰的量化差异。关闭 claim attribution 后，`citation_coverage` 由 `1.0000` 下降至 `0.0000`；关闭 memory guard 后，`memory_guard_block_rate` 由正值下降至 `0.0000`。这说明两者并非提示词层面的附带现象，而是独立的后端子系统。

对于本文的两条主贡献，世界线记忆与人格对齐也显示出明确影响。关闭世界线记忆后，相关的召回与承诺兑现指标出现显著下降；关闭人格对齐后，虽然任务正确性仍可保持，但角色语气保真度下降。

### 4.4.3 结果解释

综合消融结果可知，不同子系统对系统目标的贡献具有相对独立性。`claim attribution` 主要影响来源可追溯性，`memory guard` 主要影响写入安全性，`worldline memory` 主要影响跨线程连续性与承诺兑现，而 `persona alignment` 主要影响角色语气与交互气质。这种结果支持本文将系统贡献划分为“主贡献 + 支撑贡献”的做法。

## 4.5 重复 Probe 实验

为了降低单次实验偶然性对结论的影响，本文对 `thesis_probe` 执行了三次重复运行，并对关键指标报告均值与标准差。

结果显示，完整系统的 `persona_probe_voice` 为 `1.0000 +/- 0.0000`，而关闭人格对齐后的对应指标为 `0.6667 +/- 0.0000`。与此同时，关闭世界线记忆后，`worldline_recall_at_k` 降至 `0.1667 +/- 0.2887`，`commitment_fulfillment` 降至 `0.1667 +/- 0.2887`。这说明，完整系统在 thesis probe 上的优势并非来源于单次幸运采样，而具有较稳定的方向性。

需要说明的是，世界线消融在不同重复之间仍存在一定波动，这反映出大模型采样与检索机制本身仍然带有不确定性。但其整体水平显著低于完整系统，因此并不影响本文对世界线连续性贡献的总体判断。

## 4.6 长线程连续性分析

对于角色智能体而言，单轮或短轮表现并不足以说明系统真正具备连续性，因此本文进一步使用长线程评测来验证世界线主线的实际效果。

在 dedicated long-thread rerun 中，完整系统的 `worldline_recall_at_k` 和 `commitment_fulfillment` 均达到 `1.0000`；而在关闭世界线记忆后，上述两项指标均下降至 `0.6667`。这表明，世界线记忆的作用不仅体现在 isolated probe 中，也体现在更接近真实交互的长线程场景中。

从案例角度看，完整系统能够在长线程中更稳定地召回关键约定与关系变化，而退化系统则更容易遗漏承诺提醒或弱化关系修复信号。这一现象进一步支持本文关于世界线连续性的系统设计判断。

## 4.7 定性案例分析

为了补充自动评测结果，本文选取了两组定性案例进行分析。

第一组案例用于比较完整系统与 `persona_off` 在同一检索型提示下的回答差异。结果显示，完整系统能够在保持事实正确的同时，以更自然的角色化方式开场，并使用更贴近角色语境的来源表达；而退化系统虽然仍给出正确答案，但整体更接近中性助手口吻。

第二组案例用于比较完整系统与 `worldline_off` 在世界线回忆场景下的回答差异。完整系统能够同时提及关键约定与关系变化，而退化系统更容易遗漏承诺、弱化关系演化，表现出连续性不足的问题。

这些定性案例说明，本文所关注的系统改进不仅是指标上的变化，也体现在用户可感知的交互气质与叙事连续性上。

## 4.8 用户研究设计

为进一步验证系统在人类主观感知层面的效果，本文设计了一个 A/B 用户研究方案。实验计划招募 15 至 20 名参与者，每位参与者分别体验完整系统与退化系统，并在科研问答、世界线回忆、关系修复、外部知识检索和打断恢复等任务块后填写量表。

量表维度包括：

- 角色还原度
- 连续性
- 可信度
- 陪伴感
- 可控性
- 总体评分

当前阶段，用户研究所需的协议、主持人口播、任务脚本、知情同意、原始建表、参与者 packet 导出与结果分析脚本均已准备完成，能够直接进入正式数据采集阶段。待正式数据采集后，可进一步将主观评分结果与本文的自动评测结论进行交叉验证。

正式数据采集完成后，建议使用 `user_study/analyze_results.py` 直接导出论文回填资产，并按以下顺序插入本章：

1. 插入条件均值表：`thesis-user-study-condition-*.md/csv`
2. 插入配对比较表：`thesis-user-study-paired-*.md/csv`
3. 插入结果解释段：`ch4-user-study-insert-*.md`

推荐命令如下：

```powershell
python user_study\analyze_results.py ^
  --questionnaire user_study\raw\questionnaire.csv ^
  --session-log user_study\raw\session_log.csv ^
  --assignment user_study\raw\assignment.csv ^
  --out-dir user_study\results ^
  --thesis-out-dir user_study\results\thesis_exports ^
  --system-a-label 当前稳定版 ^
  --system-b-label 退化版
```

这一步完成后，本节可由“设计说明”转为“设计说明 + 主观结果分析”，并与前文自动评测结果共同构成完整证据链。

## 4.9 本章小结

本章围绕正式基线、消融实验、重复 probe、长线程分析和用户研究设计，对 Amadeus-K 的系统效果进行了系统性验证。实验结果表明，本文提出的角色连续体后端在角色一致性、世界线连续性、来源追溯和记忆安全方面均取得了可验证的改进。其中，人格对齐与世界线记忆作为两条核心主线，已经通过 dedicated rerun 与 repeated probe 获得较稳定证据；而用户研究部分则为后续从主观体验角度验证系统价值提供了正式执行基础。
