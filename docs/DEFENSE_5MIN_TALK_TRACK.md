# Defense 5-Minute Talk Track

Updated: 2026-03-07

This file is the compressed version for a 5-minute mid-check, advisor update, or fast defense rehearsal.

## 时间分配

1. `0:00 - 0:40` 题目与问题定义
2. `0:40 - 1:30` 系统主链
3. `1:30 - 2:20` 人格一致性
4. `2:20 - 3:10` 世界线连续性
5. `3:10 - 3:50` 可追溯检索与记忆安全
6. `3:50 - 4:30` 实验结果
7. `4:30 - 5:00` 当前状态与后续工作

## 5 分钟口播

> 我的课题是面向二次元 IP 角色的多模态个性化对话交互系统设计与实现。当前实现的是一个后端优先的技术预发布版，目标不是做一个聊天壳，而是解决角色智能体在长期交互中的人格一致性和世界线连续性问题。  
>  
> 整个系统基于 LangChain 和 LangGraph 构建，主链可以概括为：先生成任务正确的 draft，再做 persona align，然后通过 OOC 和 canon guard 检查风险；同时系统从世界线记忆里检索承诺、关系和冲突修复，并把外部知识结论绑定到来源，最后输出统一最终文本给文本和 TTS 共享。  
>  
> 在人格一致性方面，我没有只做口癖 prompt，而是把 `persona_state`、`emotion_state`、`science_mode` 和 `tsundere_intensity` 纳入线程状态，再用 dedicated thesis probe 和 repeated probe 验证。当前 baseline 的 `persona_probe_voice` 是 `1.0000`，关闭 persona alignment 后降到 `0.6667`。  
>  
> 在世界线连续性方面，系统使用五层记忆组织身份事实、共同事件、关系时间线、长期承诺和冲突修复，并让 commitments、relationship 和 repair 显式进入检索排序。baseline 的 long-thread `worldline_recall_at_k` 是 `1.0000`，关闭 worldline memory 后下降到 `0.6667`。  
>  
> 此外，我还实现了两条支撑性能力：一是 `claim_links -> source_refs` 的可追溯检索，二是 `memory_guard -> quarantine -> rollback` 的记忆安全。关闭 claim attribution 后，`citation_coverage` 会降到 `0.0000`；关闭 memory guard 后，`memory_guard_block_rate` 会降到 `0.0000`。  
>  
> 当前系统已经通过四套官方评测，并完成了消融、repeated probe、用户研究执行包和论文初稿骨架。也就是说，这个项目已经达到可答辩、可复现、可继续做正式用户研究的阶段。下一步不是重写系统，而是在这套后端之上叠加最终前端、Live2D 和展示层。

## 必须记住的数字

- `persona_probe_voice: 1.0000 -> 0.6667`
- `worldline_recall_at_k: 1.0000 -> 0.6667` in `long_thread`
- `citation_coverage: 1.0000 -> 0.0000`
- `memory_guard_block_rate: positive -> 0.0000`

## 快速问答兜底

如果时间被压缩到只剩一句话，优先说：

> 这个项目的核心不是生成一句像样的话，而是在长对话中持续保持“像这个角色”，并且让这种连续性能够被评测、被消融、被复现。
