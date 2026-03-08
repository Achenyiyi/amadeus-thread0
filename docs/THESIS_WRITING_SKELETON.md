# Thesis Writing Skeleton

Updated: 2026-03-07

This file is the writing skeleton for the thesis. It is not polished prose. It is a technical scaffold that can be filled with the final data later.

## 1. Title Candidate

Preferred title:

> 面向二次元 IP 角色的多模态个性化对话交互系统设计与实现

If a subtitle is allowed, use:

> 以 Amadeus-K 角色连续体系统为例

## 2. Abstract Skeleton

Use the abstract in five sentences. Do not turn it into a long introduction.

### Sentence 1. Problem

> 面向二次元 IP 角色的对话交互系统在实际构建中面临人格漂移、长程连续性不足、外部知识不可追溯以及长期记忆易受污染等问题。

### Sentence 2. Method

> 针对上述问题，本文设计并实现了一个基于 LangChain/LangGraph 的多模态角色连续体系统 Amadeus-K，在统一后端中集成人格状态建模、世界线记忆检索、来源归因、记忆安全防护与语音会话编排机制。

### Sentence 3. System Highlights

> 该系统采用 `task draft -> persona align -> OOC/canon guard` 的双阶段生成链路，并构建了由身份事实、共同事件、关系演化、长期承诺与冲突修复组成的五层世界线记忆结构。

### Sentence 4. Results

> 实验结果表明，系统在正式基线评测中稳定通过回归、长线程、体验 probe 与 thesis probe 测试；在重复 `thesis_probe` 实验中，完整系统的 `persona_probe_voice` 达到 `1.0000 +/- 0.0000`，而关闭人格对齐后降至 `0.6667 +/- 0.0000`；关闭世界线记忆后，`worldline_recall_at_k` 降至 `0.1667 +/- 0.2887`。

### Sentence 5. Conclusion

> 结果说明，本文提出的系统设计能够有效提升角色一致性与长程叙事连续性，并为后续的展示层扩展与产品化实现提供了可复现的后端基础。

## 3. Keywords

Recommended keywords:

1. 角色智能体
2. 长程记忆
3. 世界线连续性
4. 人格一致性
5. 多模态对话

## 4. Introduction Skeleton

Use four short subsections:

### 4.1 Background

Write:

- role-playing agents are popular
- anime/IP character systems have higher expectations than generic assistants
- users care about “像不像” and “记不记得”

### 4.2 Problem Statement

List four concrete system problems:

1. persona drift
2. weak long-term continuity
3. non-traceable retrieval
4. unsafe memory writes

### 4.3 Main Idea

Write:

> 本文并不把问题视为单一提示词优化问题，而是将其视为有状态角色智能体的系统设计问题，通过统一图式编排、长期记忆建模与实验闭环来解决。

### 4.4 Contributions

Use these exact contribution bullets:

1. 设计了一个角色连续体后端架构，将人格状态、世界线记忆、来源追溯、记忆安全与语音会话编排整合到统一系统中。
2. 提出了面向角色智能体的双阶段人格一致性控制链路，并通过 targeted probe 与消融实验验证其效果。
3. 构建了五层世界线记忆结构与关系连续性评测方法，用于支撑跨轮和长线程角色交互。
4. 建立了包含自动评测、重复 probe、长线程分析和用户研究准备的实验资产闭环。

## 5. Related Work Skeleton

Use four groups:

1. role-playing dialogue agents
2. long-term memory for conversational agents
3. retrieval attribution / reliable RAG
4. agent memory security / prompt injection defense

Important writing rule:

- compare your work at the system level
- do not pretend to propose a new foundation model

## 6. System Design Skeleton

Recommended subsection order:

1. overall architecture
2. thread state and persona state
3. worldline memory structure
4. retrieval and claim attribution
5. memory guard and rollback
6. multimodal backend orchestration
7. CLI and experiment interfaces

One sentence to repeat:

> 本文的重点在于系统工程闭环，而非某一单独模块的局部技巧。

## 7. Experiment Chapter Pointer

Do not improvise here. Point directly to:

- [THESIS_EXPERIMENT_CHAPTER_OUTLINE.md](/E:/桌面/amadeus-thread0/docs/THESIS_EXPERIMENT_CHAPTER_OUTLINE.md)
- [THESIS_FIGURE_MAP.md](/E:/桌面/amadeus-thread0/docs/THESIS_FIGURE_MAP.md)

## 8. Innovation / Contribution Defense Skeleton

If asked to write “innovation points” separately, use this form:

### Innovation 1

> 面向角色智能体的一体化人格一致性控制链路  
> 通过 `task draft -> persona align -> OOC/canon guard` 的双阶段生成结构，将角色语气控制从单一 prompt 提升为可评测的后端机制。

### Innovation 2

> 面向长程叙事交互的世界线记忆结构  
> 将身份事实、共同事件、关系演化、长期承诺和冲突修复组织为五层记忆，并用于支撑角色系统的跨轮连续性。

### Innovation 3

> 面向角色系统可靠性的可追溯与安全闭环  
> 通过 claim attribution 与 memory guard，将外部知识引用和长期记忆写入纳入统一可审计流程。

## 9. Conclusion Skeleton

Use three paragraphs only.

### Paragraph 1. What Was Built

> 本文围绕二次元 IP 角色对话交互场景，设计并实现了一个以 Amadeus-K 为实例的多模态角色连续体系统。

### Paragraph 2. What Was Verified

> 通过正式基线、消融实验、重复 probe 与长线程分析，验证了系统在人格一致性、世界线连续性、来源追溯和记忆安全方面的有效性。

### Paragraph 3. What Comes Next

> 后续工作将重点放在真实用户研究的正式执行，以及在当前稳定后端基础上扩展展示层、Live2D 与视觉交互等产品化能力。

## 10. Limitation Skeleton

Be explicit. Use these:

1. 当前尚未完成真实用户研究数据采集
2. 当前未实现正式前端与 Live2D 展示层
3. 角色上限仍受基础模型表达能力约束
4. 原作角色壳层仅适用于论文阶段的技术展示，不适合直接公开商业分发

## 11. Writing Rule

For the whole thesis, keep these constraints:

1. do not write like a product pitch
2. do not overclaim “human-like”
3. do not call every module an innovation
4. every quantitative claim must map to a real report path
5. every qualitative claim must map to a concrete case

If a sentence cannot be backed by a report, a case, or code, cut it.
