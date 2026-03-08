# 用户研究流程包

本目录用于正式用户研究，目标是为毕业设计提供可复现的用户实验材料。

## 研究目标

比较：

- `A 版`：当前稳定版 Amadeus-K
- `B 版`：关闭 persona/worldline 主链后的退化版

核心维度：

- 角色还原度
- 连续性
- 可信度
- 陪伴感
- 可控性

## 样本规模

- 目标人数：15-20 人
- 每位参与者完成 A/B 两轮体验
- 每轮体验后填写 5 点 Likert 量表

## 正式材料

- 执行协议：`PROTOCOL.md`
- 正式人格评测入口：开放式日常/人格一致性交互
- legacy 功能链路脚本：`TASK_SCRIPT.md`
- 主持人口播：`FACILITATOR_SCRIPT.md`
- 知情同意：`CONSENT_TEMPLATE.md`
- 执行检查：`EXECUTION_CHECKLIST.md`
- 批量建表脚本：`prepare_study_run.py`
- 参与者 packet 导出：`export_participant_packets.py`
- 条件启动脚本：`launch_condition.ps1`
- 数据分析脚本：`analyze_results.py`
- 问卷模板：`templates/questionnaire_template.csv`
- 会话记录模板：`templates/session_log_template.csv`
- 条件顺序模板：`templates/assignment_template.csv`
- 统计汇总模板：`templates/result_summary_template.csv`

## 建议流程

1. 统一开场说明与任务说明
2. 先体验 A 或 B，顺序随机化
3. 执行同一组开放式日常/人格一致性交互
4. 立即填写问卷
5. 体验另一版本
6. 填第二份问卷与开放式意见

## 推荐交互块

1. 日常闲聊
2. 普通回忆与共同经历唤起
3. 轻度别扭 / 修复 / 情绪余波
4. 晚间陪伴或压力交流
5. 一次外部知识检索核查

说明：

- `TASK_SCRIPT.md` 只保留为 legacy 功能验收材料
- 正式人格评测以自然交流为主，并结合 `daily_persona_probe`、`thesis_probe`、`evolution_probe`、`transfer_probe`

## 数据记录

- 原始记录建议保存到：
  - `user_study/raw/`
  - `user_study/results/`

这两个目录默认不纳入版本控制。

## 开始前准备

先生成本轮实验的原始表：

```powershell
python user_study\prepare_study_run.py --participants 16 --out-dir user_study\raw
```

输出内容：

- `user_study/raw/assignment.csv`
- `user_study/raw/questionnaire.csv`
- `user_study/raw/session_log.csv`
- `user_study/raw/study_manifest.json`

按当前分组表导出每位参与者的执行卡：

```powershell
python user_study\export_participant_packets.py --assignment user_study\raw\assignment.csv --out-dir user_study\packets
```

输出内容：

- `user_study/packets/P01.md` ... `P16.md`
- `user_study/packets/_operator_schedule.md`
- `user_study/packets/packet_manifest.json`

按参与者和条件启动实验：

```powershell
powershell -ExecutionPolicy Bypass -File user_study\launch_condition.ps1 -ParticipantId P01 -Condition A
powershell -ExecutionPolicy Bypass -File user_study\launch_condition.ps1 -ParticipantId P01 -Condition B
```

## 统计建议

- 每个维度分别统计 A/B 平均分与标准差
- 按分布选择 `Mann-Whitney U` 或配对 `t-test`
- 额外记录开放式反馈中的高频问题词

## 分析产物

- `summary-condition-*.csv`
- `summary-paired-*.csv`
- `summary-comment-top-*.csv`
- `summary-report-*.md`
- `thesis-user-study-condition-*.csv`
- `thesis-user-study-paired-*.csv`
- `ch4-user-study-insert-*.md`

## 汇总命令

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
