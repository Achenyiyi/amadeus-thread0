# Defense Slide Final

Updated: 2026-03-07

This file is the final recommended version of the 10-slide defense deck. Each slide is written for direct use in a thesis defense, with tighter on-slide text and a stricter speaking objective than the draft version.

## Slide 1. 题目与目标

Slide goal:

- 先把课题定位说准

On-slide text:

- Amadeus-K：面向二次元 IP 角色的多模态个性化对话交互系统
- 后端优先的技术预发布版
- 主问题：人格一致性 + 世界线连续性

45-second script:

> 我的课题是面向二次元 IP 角色的多模态个性化对话交互系统设计与实现。当前实现的是一个后端优先的技术预发布版，核心不是做一个套了角色 prompt 的聊天壳，而是解决角色智能体在长期交互中的人格一致性和世界线连续性问题。

## Slide 2. 问题定义

Slide goal:

- 让评委知道你在解决什么硬问题

On-slide text:

- role-play prompt 容易人格漂移
- 长对话容易忘记承诺、关系与关键事件
- RAG 结论常常无法回查来源
- 长期记忆可能被注入污染

45-second script:

> 我把问题拆成四类。第一，普通 role-play prompt 很容易漂移成通用助手腔。第二，长对话会忘记承诺、关系变化和关键事件。第三，外部检索的结论常常无法回查来源。第四，长期记忆如果没有保护，会成为新的攻击面。

## Slide 3. 系统总览

Slide goal:

- 用一页讲清主链，而不是罗列模块

On-slide text:

- `task draft -> persona align -> ooc/canon guard`
- `worldline retrieval -> claim attribution -> final text`
- 文本与 TTS 共用单一最终文本

50-second script:

> 系统主链先生成任务正确的草稿，再做人格对齐，然后通过 OOC 和 canon guard 检查偏移风险。与此同时，系统从世界线记忆里检索承诺、关系和冲突修复，再把外部知识结论绑定到来源。最后输出统一最终文本，语音链路只朗读这一份最终文本，避免文本和 TTS 分叉。

## Slide 4. 人格一致性

Slide goal:

- 证明你的人格一致性不是靠口癖

On-slide text:

- 线程状态：`persona / emotion / science_mode / tsundere_intensity`
- 双阶段生成：先任务正确，后角色对齐
- repeated probe 验证 persona 主线

45-second script:

> 这里的人格一致性不是看有没有某个口癖，而是看回答是否持续符合角色的表达方式、理性风格和关系语境。为此，我把 persona state 和 emotion state 纳入线程状态，再通过双阶段生成和 targeted thesis probe 来验证人格主线。

Must-show number:

- `persona_probe_voice: 1.0000 -> 0.6667` when `persona_off`

## Slide 5. 世界线连续性

Slide goal:

- 证明角色能“记得过去”，而不是只会当前轮生成

On-slide text:

- 五层记忆：身份事实、共同事件、关系时间线、承诺、冲突修复
- commitments / repair / relationship 显式参与检索
- 关系状态由历史轨迹自动推导

50-second script:

> 世界线连续性的关键不是存更多记忆，而是让系统在需要的时候把关键事件、长期承诺和关系修复拉回当前上下文。当前系统用五层记忆组织世界线信息，并让 commitments、relationship 和 conflict repair 显式参与检索排序。

Must-show numbers:

- baseline `long_thread worldline_recall_at_k = 1.0000`
- `worldline_off long_thread worldline_recall_at_k = 0.6667`

## Slide 6. 可追溯检索与记忆安全

Slide goal:

- 强调这两条是可测的系统能力

On-slide text:

- `claim_links -> source_refs`
- `memory_guard -> quarantine -> rollback`
- 两条能力都有独立消融

45-second script:

> 这两条能力不是提示词层面的装饰，而是独立的后端子系统。回答中的 claim 会绑定到 source refs；长期记忆在写入前经过 memory guard、隔离区和回滚链。关闭它们以后，指标会直接掉下来。

Must-show numbers:

- `claim attribution off -> citation_coverage = 0.0000`
- `memory guard off -> memory_guard_block_rate = 0.0000`

## Slide 7. 官方基线

Slide goal:

- 用一页把系统“站稳”

On-slide text:

- 四套官方 suite 全绿
- `regression_isolated`
- `long_thread`
- `experience_probe`
- `thesis_probe`

40-second script:

> 为了避免一次性大矩阵里的采样波动，我把 dedicated single-suite rerun 作为正式 baseline。当前四套官方 suite 都已经通过，这说明系统不仅能演示，而且已经具备稳定评测基线。

## Slide 8. 消融与 repeated probe

Slide goal:

- 说明主张不是一次幸运结果

On-slide text:

- `persona_off` 先伤角色语气
- `worldline_off` 先伤跨线程回忆和承诺兑现
- repeated probe 用均值和标准差压随机性

45-second script:

> 消融实验的目的不是证明某个模块必须存在，而是识别不同子系统分别影响什么。当前结果显示，去掉 persona alignment 主要伤角色语气，去掉 worldline memory 主要伤回忆和承诺兑现；而 repeated probe 证明这种差异不是一次幸运采样。

## Slide 9. 用户研究与论文资产

Slide goal:

- 证明项目已经进入正式实验阶段

On-slide text:

- `16` 人 A/B 平衡分组
- 量表：角色还原度、连续性、可信度、陪伴感、可控性
- 已完成建表、packet、分析脚本、论文初稿骨架

40-second script:

> 当前用户研究执行包已经准备完成，包括分组表、参与者 packet、分析脚本和论文初稿骨架。也就是说，项目已经从单纯工程实现推进到了正式实验可执行状态。

## Slide 10. 结论与下一阶段

Slide goal:

- 收到“已经做成什么、下一步做什么”

On-slide text:

- 已完成：后端、评测、消融、用户研究包、论文与答辩资产
- 未完成：正式前端、Live2D、摄像头互动
- 下一阶段是在现有后端之上叠加展示层

45-second script:

> 当前项目已经达到可答辩、可复现、可写论文、可继续产品化的状态。接下来的工作不是推翻系统，而是在这套已经站稳的后端之上叠加最终展示层和角色外壳。
