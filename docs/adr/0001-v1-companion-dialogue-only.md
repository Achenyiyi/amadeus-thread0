# 第一版只做陪伴对话

旧架构把陪伴对话、自主、数字身体三块能力一起织进了每一轮，代码涨到 8.3 万行，改一点就要过一堆 gate、改一堆测试。重构后的第一版只做陪伴对话、只用 CLI；自主和数字身体只留扩展点，以后再接回来。代价是第一版的她不会主动开口，也不能替你做事；换来的是核心代码能压到 2 万行以内，开发重新推得动。

第一版的边界：

- 每轮固定调用两次模型：先生成回复，再在回复之后评估这一问一答，把心情和关系的变化、值得记住的事写回，从下一轮开始生效。
- 生成时不绑定工具，不分模式，也不做改写。
- 不用中文短语表判断场景，也不用它修改回复，回复只做结构性清洗。你看到的回复，就是历史里存下的那一句。
- 人格设定是一份只读的文本文件，也是人格的唯一出处。
- 她只和你一个人相处。你就是你本人，不是剧中的冈部伦太郎。
- 心情会随真实时间平复；关系只随相处变化，不随时间变淡。
- 没有 backend API、TTS、感知层和 gate 体系。

## 被推翻的旧决策

`docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`：

- **P0-2 Perception Event Is The Canonical Input Contract**：第一版的输入只有你的一条消息，也就是文字和发送时间。
- **P0-3 Persona Core Is Fixed; Self Model Evolves**：人格固定不变这一半保留。会变的只剩心情、关系和记忆；自我叙事、动机/目标、own rhythm 归自主。
- **P0-5 Counterpart Model Is A First-Class Runtime State**：7 维的 counterpart model 换成一个维度尽量少、长期累积的关系状态。
- **P0-6 Own Rhythm Is A Core Engine**：归自主，第一版不做。
- **P1-8 Presence Layer Becomes Formal Runtime Infrastructure**：打字状态、沉默、延迟续说、主动重新开口，第一版都没有。主动开口归自主。
- **P1-9 Relational Boundary Guard Is Separate From Generic Safety**：第一版没有单独的守卫层。
- **P1-10 Traceability Must Cover The Full Persona Loop**：降为 CLI 里可选的逐轮追踪开关。
- **P2-14 Chinese Semantic De-Scaffolding Is Unlocked**：第一版不用中文短语规则，也就没有要拆的脚手架。
- **否决项 3 Reject Prompt-Heavy Behavioral Repair As The Main Strategy**：第一版的回复质量主要靠人格文本和示例对话。
- **否决项 5 Reject "Memory = Retrieval Store" Reduction**：部分推翻。记忆仍然记录关系的变化、没解开的别扭，以及吵架后是怎么和好的，但不再记录 selfhood 和 own rhythm 的痕迹。

P1-7 系列（capability bus、action packet、需审批的变更、digital body、skills）没有被推翻，只是第一版不实现，留作扩展点。

`CLAUDE.md`：

- **canonical loop**（Perception → Appraisal → … → Self-Narrative Update）：第一版的一轮是：你的消息 → 回复 → 评估 → 写回心情、关系、记忆。
- **Do not expand prompt constraints casually**：理由同否决项 3。
- **Preserve backward-compatible imports when moving code between modules**：第一版不保留兼容壳。
- **Chinese semantic de-scaffolding is its own bounded phase**：理由同 P2-14。
- **The frontend is a backend.v1 contract consumer only**：backend.v1 砍掉，前端重做时再定契约。
- **Text and TTS share one final utterance**：TTS 砍掉，这条由「你看到的回复，就是历史里存下的那一句」取代。
