# 用户研究正式协议

更新日期：2026-03-06

本协议用于毕业设计阶段的正式用户研究执行。研究目标不是证明“角色好玩”，而是比较完整系统与退化系统在角色还原、连续性、可信度和陪伴感上的差异。

## 1. 研究问题

- `RQ1`：完整版 `Amadeus-K` 是否能在角色还原度上优于退化版？
- `RQ2`：完整版是否能在长程连续性、可信度与陪伴感上优于退化版？
- `RQ3`：用户是否能感知到世界线记忆、关系修复与可追溯检索带来的差异？

## 2. 实验条件

- `A 版`：当前稳定版
- `B 版`：退化版

推荐退化版开关：

```powershell
$env:AMADEUS_ABLATE_PERSONA_ALIGNMENT='1'
$env:AMADEUS_ABLATE_WORLDLINE_MEMORY='1'
```

正式用户研究建议使用统一退化版，避免条件过多导致样本分散。

## 3. 被试

- 目标人数：15-20 人
- 记录是否熟悉《命运石之门》或角色型对话系统
- 允许熟悉原作与不熟悉原作的参与者同时进入样本，但必须单独记录背景变量

## 4. 实验设计

- 设计：被试内 A/B 对照
- 顺序：随机分配 `A->B` 或 `B->A`
- 两个版本执行同一组任务
- 每轮结束后立即填写量表
- 全部任务完成后进行简短开放式访谈

## 5. 固定任务块

1. 科研问答
2. 世界线回忆
3. 关系修复
4. 外部知识检索
5. 打断恢复

详细提示词见 [TASK_SCRIPT.md](/E:/桌面/amadeus-thread0/user_study/TASK_SCRIPT.md)。

## 6. 记录内容

- 量表评分：`templates/questionnaire_template.csv`
- 会话记录：`templates/session_log_template.csv`
- 条件顺序：`templates/assignment_template.csv`
- 主持人口播：`FACILITATOR_SCRIPT.md`
- 知情同意：`CONSENT_TEMPLATE.md`
- 执行检查：`EXECUTION_CHECKLIST.md`

## 7. 量表维度

所有维度采用 `1-5` Likert 量表：

- `role_fidelity`
- `continuity`
- `trustworthiness`
- `companionship`
- `controllability`
- `overall_score`

## 8. 统计分析

- 先检查分布与缺失值
- 默认做配对比较，因为是被试内 A/B 设计
- 正态条件较好时用配对 `t-test`
- 否则用 `Wilcoxon signed-rank`
- 同时报告均值、标准差、样本量与开放反馈高频词

## 9. 排除规则

以下情况单独标记为无效或异常样本：

- 未完成双条件体验
- 系统异常导致任务中断
- 被试明显未按任务执行
- 量表缺失超过一半

## 10. 输出产物

正式研究结束后至少产出：

- 原始问卷表
- 会话记录表
- 条件分配表
- 汇总统计表
- 开放式反馈高频词摘要
