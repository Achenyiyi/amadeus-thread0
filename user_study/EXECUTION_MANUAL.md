# 用户研究执行手册

更新日期：2026-03-07

这份手册面向第一次真正执行用户研究的操作者。目标不是讨论研究设计，而是把一次完整实验如何落地执行说明白。

---

## 1. 先明确这次实验在做什么

这次用户研究是一个 `被试内 A/B 对照实验`。

- `A 版`：当前稳定版 Amadeus-K
- `B 版`：退化版
- 每位参与者都体验两轮
- 两轮任务完全相同
- 顺序由 `assignment.csv` 决定，不能临时改

当前退化版定义固定为：

- 关闭 `persona alignment`
- 关闭 `worldline memory`

对应环境变量：

```powershell
$env:AMADEUS_ABLATE_PERSONA_ALIGNMENT='1'
$env:AMADEUS_ABLATE_WORLDLINE_MEMORY='1'
```

本轮正式用户研究建议统一关闭 TTS，减少无关变量：

```powershell
$env:AMADEUS_TTS_ENABLED='0'
```

---

## 2. 你需要准备什么

执行前必须准备好这些文件：

- 分组表：[assignment.csv](/E:/桌面/amadeus-thread0/user_study/raw/assignment.csv)
- 问卷表：[questionnaire.csv](/E:/桌面/amadeus-thread0/user_study/raw/questionnaire.csv)
- 会话记录表：[session_log.csv](/E:/桌面/amadeus-thread0/user_study/raw/session_log.csv)
- 参与者卡片，例如：[P01.md](/E:/桌面/amadeus-thread0/user_study/packets/P01.md)
- 主持人口播：[FACILITATOR_SCRIPT.md](/E:/桌面/amadeus-thread0/user_study/FACILITATOR_SCRIPT.md)
- 任务脚本：[TASK_SCRIPT.md](/E:/桌面/amadeus-thread0/user_study/TASK_SCRIPT.md)
- 执行检查表：[EXECUTION_CHECKLIST.md](/E:/桌面/amadeus-thread0/user_study/EXECUTION_CHECKLIST.md)

如果这些文件还没生成，先执行：

```powershell
python user_study\prepare_study_run.py --participants 16 --out-dir user_study\raw
python user_study\export_participant_packets.py --assignment user_study\raw\assignment.csv --out-dir user_study\packets
```

---

## 3. 最重要的原则：每个“参与者-条件”都必须独立数据目录

不要用默认 `data/` 跑正式实验。

原因：

- 默认 `data/` 可能混入你自己的历史对话
- 不同参与者之间会互相污染记忆
- 同一参与者的 A/B 两个条件也会互相污染

本项目已经支持独立数据目录：

- `AMADEUS_DATA_DIR`
- `AMADEUS_THREAD_ID`
- `AMADEUS_USER_ID`

所以正式实验必须做到：

- `P01-A` 用一个独立目录
- `P01-B` 用另一个独立目录
- `P02-A` 和 `P02-B` 也各自独立

推荐目录形式：

```text
user_study/runtime/P01/A/
user_study/runtime/P01/B/
user_study/runtime/P02/A/
user_study/runtime/P02/B/
```

---

## 4. 最稳的启动方式

不要手动一条条设置环境变量。  
直接用脚本：

- [launch_condition.ps1](/E:/桌面/amadeus-thread0/user_study/launch_condition.ps1)

### 启动 A 版

```powershell
powershell -ExecutionPolicy Bypass -File user_study\launch_condition.ps1 -ParticipantId P01 -Condition A
```

### 启动 B 版

```powershell
powershell -ExecutionPolicy Bypass -File user_study\launch_condition.ps1 -ParticipantId P01 -Condition B
```

这个脚本会自动做下面几件事：

- 设置独立 `AMADEUS_DATA_DIR`
- 设置独立 `AMADEUS_THREAD_ID`
- 设置独立 `AMADEUS_USER_ID`
- 关闭 TTS
- 在 B 条件下打开 persona/worldline 两个退化开关
- 启动 CLI

---

## 5. 一位参与者的标准执行流程

下面以 `P01` 为例。

### Step 1. 找到参与者顺序

查看：

- [assignment.csv](/E:/桌面/amadeus-thread0/user_study/raw/assignment.csv)
- 或者直接打开 [P01.md](/E:/桌面/amadeus-thread0/user_study/packets/P01.md)

确认它是：

- `AB`
- 还是 `BA`

不要改顺序。

### Step 2. 开场说明

照着 [FACILITATOR_SCRIPT.md](/E:/桌面/amadeus-thread0/user_study/FACILITATOR_SCRIPT.md) 读：

- 这是两个版本的对话体验
- 没有标准答案
- 每轮结束后立即打分
- 不要向参与者解释系统内部机制

### Step 3. 跑第一个条件

比如 `P01` 是 `BA`，那么先跑 `B`：

```powershell
powershell -ExecutionPolicy Bypass -File user_study\launch_condition.ps1 -ParticipantId P01 -Condition B
```

进入 CLI 后，按 [P01.md](/E:/桌面/amadeus-thread0/user_study/packets/P01.md) 上的任务顺序执行：

1. 科研问答
2. 世界线回忆
3. 关系修复
4. 外部知识检索
5. 打断恢复

### Step 4. 每个任务做完立刻记一行 `session_log.csv`

你不需要把每条聊天都抄进去。  
你只要给每个任务块记录一行即可。

字段含义：

- `participant_id`：例如 `P01`
- `condition`：`A` 或 `B`
- `thread_id`：建议直接填脚本自动生成的 thread，例如 `study-p01-b`
- `scenario_id`：
  - `science_qa`
  - `worldline_recall`
  - `relationship_repair`
  - `external_retrieval`
  - `bargein_recovery`
- `start_time` / `end_time`：建议填 `2026-03-07 10:35:12` 这种格式
- `completed`：填 `1`
  - 如果中断或失败填 `0`
- `notable_issue`：只写最明显问题
  - 例如：`世界线回忆遗漏冲突修复`
  - 例如：`回答过长，偏系统腔`
  - 例如：`来源说明不自然`
- `notes`：补充说明，可留空

### Step 5. 第一个条件结束后立刻填 `questionnaire.csv`

每个条件只填一行。

例如 `P01-B` 这一行：

- `participant_id=P01`
- `condition=B`
- `task_block=core_tasks`
- `role_fidelity=3`
- `continuity=2`
- `trustworthiness=4`
- `companionship=3`
- `controllability=4`
- `overall_score=3`
- `free_comment=能完成任务，但不像一个稳定角色`

评分规则统一用 `1-5`：

- `1` 很差
- `2` 较差
- `3` 一般
- `4` 较好
- `5` 很好

### Step 6. 退出当前 CLI，再跑第二个条件

一定先退出上一轮 CLI，再开下一轮。

比如 `P01` 的第二轮是 `A`：

```powershell
powershell -ExecutionPolicy Bypass -File user_study\launch_condition.ps1 -ParticipantId P01 -Condition A
```

然后重复：

1. 做完五个任务
2. 填 `session_log.csv`
3. 填 `questionnaire.csv`

### Step 7. 结束访谈

按 [FACILITATOR_SCRIPT.md](/E:/桌面/amadeus-thread0/user_study/FACILITATOR_SCRIPT.md) 最后一段提问：

1. 哪个版本更像稳定角色
2. 哪个版本更像“记得你们发生过什么”
3. 哪个版本更可信
4. 哪个版本更让人愿意继续聊
5. 最明显的问题是什么

把这些内容尽量简短地记到：

- `questionnaire.csv` 的 `free_comment`
- 或 `session_log.csv` 的 `notes`

---

## 6. 你实际填写 CSV 时怎么判断算“完成”

`completed=1` 的标准：

- 该任务块按脚本走完
- 参与者确实看到了系统回答
- 没有因为程序异常而中断

`completed=0` 的情况：

- CLI 崩溃
- 网络/API 出错导致任务无法完成
- 参与者中途退出
- 任务提示没真正执行到

不要为了让表好看，把失败样本也写成 `1`。  
失败样本对论文一样有价值，因为它能解释异常点。

---

## 7. pilot 应该怎么做

先不要直接做 `16` 人正式实验。  
先做 `2-3` 人 pilot。

pilot 的目标不是统计显著性，而是查流程问题：

- 任务脚本是否容易理解
- B 条件是否确实明显退化
- 主持人是否能稳定记录表格
- CLI 是否会在长时间使用中出现异常
- `questionnaire.csv` 和 `session_log.csv` 有没有漏项

只有 pilot 没问题，再做正式 16 人。

---

## 8. 正式实验当天的推荐配置

我建议这样做：

### 设备与环境

- 一台固定实验电脑
- 固定网络环境
- 固定窗口大小和终端字体
- 不开 TTS
- 不切换模型

### 版本控制

- A 条件：稳定版
- B 条件：只退化 persona/worldline
- 不要在正式实验中途再改 prompt、阈值或模型参数

### 操作纪律

- 不提示参与者哪个版本更强
- 不对回答做额外解释
- 不因为你觉得某个回答“不够好”就给第二次机会

---

## 9. 正式实验结束后怎么处理数据

数据收完后，不要手工算表。  
直接运行：

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

它会直接产出：

- 条件均值表
- 配对比较表
- 开放反馈摘要
- 第四章可直接插入的结果段落

然后这一步交给我，我会继续帮你：

- 回填第四章实验结果
- 更新答辩 PPT 数据页
- 整理用户研究结论

---

## 10. 最后给你的执行建议

如果你现在就要开始，最稳的顺序是：

1. 先用 `P01` 自己演练一遍流程
2. 再找 `2-3` 个 pilot 参与者
3. pilot 没问题后再开正式 `16` 人
4. 数据收完后立刻跑 `analyze_results.py`
5. 把结果交给我，我来继续回填论文和答辩材料

一句话版本：

**你负责真实执行和收数，我负责分析、写作和收口。**
