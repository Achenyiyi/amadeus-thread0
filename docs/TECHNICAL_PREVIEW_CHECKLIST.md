# 技术预发布检查表

## 演示前

- `.env` 已配置主模型参数（`AMADEUS_MODEL_PROVIDER / AMADEUS_MODEL_NAME / AMADEUS_MODEL_API_KEY`）
- 如需语音，已配置 `DASHSCOPE_API_KEY`
- `python -m py_compile amadeus_thread0\*.py evals\*.py` 通过
- `python evals\run_technical_preview_rc_phase1_audit.py --run-tag rc-phase1-dev` 通过，并输出 `technical_preview_rc_phase1_ready`
- `python evals\run_operator_console_rc_phase1_audit.py --run-tag operator-console-rc-phase1-dev` 通过，并输出 `operator_console_rc_phase1_ready`
- `runtime_status_dashboard.NEXT_SPECS` 当前为空
- CLI 可启动
- `/help`、`/persona`、`/worldline`、`/bond`、`/sources` 正常
- 评测脚本可运行：`python evals\run_langsmith_evals.py --local-only --suite regression_isolated`
- 已准备 [ADVISOR_REPRO_RUNBOOK.md](/E:/桌面/amadeus-thread0/docs/ADVISOR_REPRO_RUNBOOK.md)
- 已准备 [DEFENSE_TALK_TRACK.md](/E:/桌面/amadeus-thread0/docs/DEFENSE_TALK_TRACK.md)

## 演示机环境

- Python 版本与依赖已按 `requirements.txt` 安装
- 网络可访问 DeepSeek / DashScope / LangSmith
- 麦克风和扬声器状态已确认（如果要演示语音）
- `data/` 不包含敏感真实用户内容
- 不演示 live microphone / camera / background screen capture；当前 RC 只承认 consent-bound artifact 与 approved precomputed result 路径

## 演示时重点

- 先展示系统能力，再解释架构
- 每个场景都用 `/worldline`、`/bond`、`/sources` 或 `/persona` 给出证据
- 如果展示 operator/readback 状态，优先展示 `operator_console_rc.v1`、`technical_preview_rc.v1`、`runtime_status_dashboard.v1` 和 `operator_readback.v2`
- 避免现场临时发挥大段闲聊，按脚本走

## 演示后留档

- 保留本次 `evals/reports/*.json` 与 `*.md`
- 特别保留 `technical-preview-rc-phase1-audit-*.json` 与 `technical-preview-rc-phase1-audit-*.md`
- 特别保留 `operator-console-rc-phase1-audit-*.json` 与 `operator-console-rc-phase1-audit-*.md`
- 记录演示使用的 thread_id
- 记录任何异常、失真回复、TTS 问题和来源追溯缺失
- 按 [FINAL_DELIVERY_MANIFEST.md](/E:/桌面/amadeus-thread0/docs/FINAL_DELIVERY_MANIFEST.md) 归档交付物
