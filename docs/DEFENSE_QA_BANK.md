# Defense QA Bank

Updated: 2026-03-07

This file is the fallback bank for advisor meetings and defense Q&A. Use short, controlled answers first; expand only if the committee keeps digging.

## Q1. 你的项目和普通聊天机器人有什么本质区别？

Short answer:

> 区别不在于会不会聊天，而在于它是不是一个角色连续体系统。  
> 我这个系统把人格状态、世界线记忆、关系演化、来源追溯和记忆安全放进了统一后端，所以它的目标不是生成一句像样的话，而是在长对话里持续保持“像这个角色”。

Expanded points:

1. 普通聊天机器人依赖单轮生成
2. 角色连续体系统依赖状态、记忆和约束协同
3. 当前系统不仅生成回答，还维护承诺、关系和来源链

## Q2. 为什么这不是单纯的 prompt engineering？

Short answer:

> 因为关键能力不是写在 prompt 里，而是落在后端结构里。  
> 例如 `worldline memory`、`claim attribution`、`memory guard` 和 `rollback` 都是系统能力，不是换一句提示词就能得到的。

Evidence to mention:

1. `claim attribution off -> citation_coverage = 0.0000`
2. `memory guard off -> memory_guard_block_rate = 0.0000`
3. `worldline_off` 在 repeated probe 和 long-thread 里都显著退化

## Q3. 你为什么选 LangChain / LangGraph？

Short answer:

> 因为这个题目核心是有状态 agent system，而不是单次模型调用。  
> LangGraph 更适合把 checkpoint、memory、tool use、HITL 和多节点流程组织成稳定图结构。

Do not say:

- “因为它流行”

Say:

- “因为它适合做可复现的 agent workflow 编排”

## Q4. 你为什么不直接做模型微调？

Short answer:

> 论文阶段我优先验证系统设计，而不是把系统问题和模型训练问题混在一起。  
> 先证明在不微调的前提下，系统工程本身就能改善人格一致性和长程连续性。  
> 如果后续还要追更高上限，再把 LoRA 或 preference tuning 作为下一阶段。

## Q5. 你的主要贡献到底是哪几条？

Recommended answer:

Main contributions:

1. 人格一致性控制
2. 世界线连续性建模

Supporting contributions:

3. 可追溯检索可靠性
4. 记忆安全

## Q6. 你如何定义“人格一致性”？

Short answer:

> 我这里的人格一致性不是“有没有口癖”，而是回答是否持续符合角色的表达风格、理性方式和关系语境。  
> 所以我把它拆成 persona state、persona align、OOC risk 和 targeted persona probe 来验证。

## Q7. 你如何定义“世界线连续性”？

Short answer:

> 世界线连续性指的是系统能否在跨轮甚至跨线程的交互里，稳定召回关键事件、承诺、关系变化和冲突修复，并在回答里自然体现出来。

Key metrics:

1. `worldline_recall_at_k`
2. `commitment_fulfillment`
3. `relationship_continuity`
4. `worldline_answer_grounding`

## Q8. 为什么需要 `memory guard`？

Short answer:

> 因为长期记忆一旦被污染，角色系统会长期偏移。  
> `memory guard` 的作用就是在写入前挡住 prompt injection、保护字段覆盖和低可信内容沉淀。

Best supporting line:

> 对角色系统来说，错误写入往往比一次错误回答更危险，因为它会进入后续所有对话。

## Q9. 你如何证明来源追溯不是摆设？

Short answer:

> 因为回答里的 claim 和 source 之间是显式绑定的，不是只把几个链接贴在后面。  
> 关闭 claim attribution 之后，`citation_coverage` 会直接掉到 `0.0000`。

## Q10. 你如何证明角色不是“只会背模板”？

Short answer:

> 我没有只做单轮模板测试，而是用了三种互补路径：  
> 第一，正式 baseline suite；  
> 第二，ablation 和 repeated thesis probe；  
> 第三，长线程与用户研究。  
> 这样可以避免只在一个固定 prompt 上看起来好看。

## Q11. 你的实验有没有随机性问题？

Short answer:

> 有模型采样和检索波动，所以我没有只引用单次运行。  
> 我额外补了 repeated thesis probe，用均值和标准差报告关键指标，而不是拿一次幸运结果当结论。

Best current example:

1. baseline `persona_probe_voice = 1.0000 +/- 0.0000`
2. persona_off `persona_probe_voice = 0.6667 +/- 0.0000`

## Q12. 你的系统如果换模型，还成立吗？

Short answer:

> 系统结构成立，但指标会变化。  
> 我当前的论文贡献主要在后端设计和实验闭环，所以它不依赖某个单一 prompt，而是依赖状态、记忆、工具和评测结构。  
> 换模型后需要重新测，但整体框架不需要推翻。

## Q13. 为什么现在不做前端和 Live2D？

Short answer:

> 因为论文阶段最先要证明的是系统能不能站住，而不是展示层漂不漂亮。  
> 如果人格一致性、世界线连续性和实验闭环没有做好，前端越完整，越容易变成包装空心项目。

## Q14. 你的项目离产品化还有多远？

Short answer:

> 现在已经接近“技术预发布版”，但还不是最终产品。  
> 目前强的是后端和实验闭环，后续还需要前端、Live2D、摄像头互动、版权壳层替换和公开分发策略。

## Q15. 你现在最缺的是什么？

Short answer:

> 当前最缺的不是功能，而是真实用户研究数据和最后的论文图表整理。  
> 后端和实验资产已经基本够用，下一步是把用户研究跑起来，把数据接进论文。

## Q16. 如果导师说“这还是不够像红莉栖”，你怎么回应？

Recommended answer:

> 这个判断是合理的。  
> 当前版本已经把人格一致性从 prompt 提升到了系统层，但“像不像”仍然有两部分来源：  
> 一部分来自系统结构，另一部分来自模型表达上限。  
> 所以我论文阶段先证明系统结构有效，后续如果要继续逼近角色上限，再考虑更强的角色数据和模型定制。

## Q17. 如果被追问“创新性在哪里”？

Do not answer with a feature list.

Use this framing:

> 创新性不在单个功能，而在于我把角色一致性、世界线连续性、来源追溯和记忆安全放进了同一个可评测后端里，并且给出了自动评测、消融和用户研究的闭环。

## Q18. 最后一问：你希望评委记住什么？

Recommended closing line:

> 我希望评委记住的不是“我做了一个会聊天的角色”，而是“我把一个角色智能体最难站住的三件事：连续、可信、可控，做成了可以验证的系统”。
