# Defense Talk Track

Updated: 2026-03-07

This file is the recommended speaking track for advisor meetings, mid-checks, and final defense demos.

## 1. One-Minute Opening

Use this when you need to explain the project quickly:

> 我的题目是“面向二次元 IP 角色的多模态个性化对话交互系统设计与实现”。  
> 我选择了《命运石之门 0》中的 Amadeus 作为角色原型，但当前论文阶段的重点不是做一个外壳聊天机器人，而是解决两个更硬的问题：  
> 第一，角色在长期对话里如何保持人格一致性；  
> 第二，角色如何在多轮、多线程交互里维持世界线连续性。  
> 基于 LangChain/LangGraph，我实现了一个角色连续体后端，把 persona state、worldline memory、source attribution、memory guard 和多模态会话编排放进统一系统，并用自动评测、消融实验和用户研究来验证系统效果。

## 2. What Problem This Project Actually Solves

Do not say:

- “我做了一个像红莉栖的聊天助手”

Say:

- “我做的是一个角色连续体系统，目标是降低角色漂移、世界线断裂、来源不可追溯和记忆污染这些典型问题。”

Short framing:

1. 普通 role-play prompt 容易漂移
2. 长对话容易忘记承诺、关系变化和关键事件
3. 外部检索常见问题是回答看起来对，但无法回查来源
4. 智能体长期记忆如果没有保护，会被 prompt injection 污染

## 3. Architecture Explanation

Recommended explanation order:

1. `task draft`
   - 先保证任务正确性
2. `persona align`
   - 再把答案对齐到 Amadeus / Kurisu 风格
3. `ooc / canon guard`
   - 检查人格偏移和设定越界
4. `worldline memory retrieval`
   - 把 commitments / relationship / conflict repair 拉回当前上下文
5. `claim attribution`
   - 把外部结论绑定到来源
6. `memory guard`
   - 防止危险或低可信内容写入长期记忆
7. `session orchestrator`
   - 保证文本最终答案与语音共用单一真源

Use this sentence:

> 整个系统不是“先生成再随便补丁”，而是用状态、记忆、审计和评测把角色行为收进一个受控后端里。

## 4. Thesis Contributions

Use these four points consistently:

1. 人格一致性控制  
   - 双阶段生成 + OOC / persona gap 判别
2. 长程世界线连续性  
   - 五层记忆 + commitment / relationship / conflict repair 检索
3. 可追溯检索可靠性  
   - `claim_links -> source_refs`
4. 记忆安全  
   - guard / quarantine / rollback

If time is short, keep only the first two as main contributions and call the latter two supporting contributions.

## 5. Experiment Story

Use this structure, in order:

1. `official baseline`
   - regression / long_thread / experience_probe / thesis_probe
2. `ablation`
   - remove persona
   - remove worldline
   - remove claim attribution
   - remove memory guard
3. `repeated thesis probe`
   - prove the persona/worldline results are not one-off lucky samples
4. `user study`
   - role fidelity
   - continuity
   - trustworthiness
   - companionship
   - controllability

## 6. Current Strongest Numbers

Use current stable numbers from the latest recorded assets:

- thesis probe baseline:
  - `persona_probe_voice = 1.0000`
  - `worldline_recall_at_k = 1.0000`
- repeated thesis probe:
  - baseline `persona_probe_voice = 1.0000 +/- 0.0000`
  - persona_off `persona_probe_voice = 0.6667 +/- 0.0000`
  - worldline_off `worldline_recall_at_k = 0.1667 +/- 0.2887`
- long_thread:
  - baseline `worldline_recall_at_k = 1.0000`
  - worldline_off `worldline_recall_at_k = 0.6667`

Do not overstate:

- say “supports the claim”
- do not say “fully proves”

## 7. What To Say When Asked “Why LangChain / LangGraph?”

Recommended answer:

> 因为这个题目不是单纯做模型调用，而是做有状态、有工具、有记忆、有可审计流程的角色系统。  
> LangGraph 适合把节点、状态、HITL、checkpoint 和长期记忆编排成稳定的 agent workflow。  
> 论文阶段我更需要系统工程闭环和实验可复现性，而不是重新发明一套 agent runtime。

## 8. What To Say When Asked “Why Not Fine-Tune?”

Recommended answer:

> 论文阶段我优先验证的是系统设计而不是模型定制。  
> 先把 persona consistency、worldline continuity、traceability 和 memory safety 用系统工程做出可评测闭环。  
> 如果后续指标仍不够，再把 LoRA 或 preference tuning 作为下一阶段增强，而不是一开始就把问题混成“模型训练有效还是系统设计有效”。

## 9. What To Say When Asked “What Is Still Missing?”

Be direct:

1. 前端展示层还未进入正式开发
2. Live2D / 摄像头互动仍在后续阶段
3. 用户研究尚待正式执行
4. 商业化还需要角色壳层替换与版权策略处理

Use this sentence:

> 当前阶段我刻意把资源集中在后端和实验闭环，因为这是论文成立和系统可信的前提。

## 10. Demo Narration Order

When doing a live demo, narrate in this order:

1. 先看它像不像一个稳定角色
2. 再看它能不能记住约定和关系变化
3. 再看外部知识能不能回查来源
4. 再看被打断后能不能续上
5. 最后看系统能不能拒绝危险记忆写入

Short line to use:

> 我想证明的不是它会聊天，而是它在连续、可信、可控这三件事上都站得住。

## 11. Questions You Should Expect

Prepare concise answers for:

1. 角色扮演和普通聊天助手的本质差别是什么？
2. 为什么你的贡献是系统贡献，而不是 prompt engineering？
3. 世界线连续性如何量化？
4. 为什么需要 memory guard？
5. 你的评测如何避免只测到“会背模板”？
6. 如果模型换掉，系统结构还是否成立？

## 12. Closing Sentence

Use this at the end of a defense section:

> 这个项目当前已经完成了角色连续体后端、正式评测和用户研究准备；后续我会在这个稳定后端之上继续补展示层和产品化壳层，而不是反过来先做表面包装。
