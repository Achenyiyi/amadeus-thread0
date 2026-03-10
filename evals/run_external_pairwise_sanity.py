from __future__ import annotations

import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402
from evals.run_langsmith_evals import (  # noqa: E402
    _invoke_model_with_retries,
    _model,
)
from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
load_dotenv(PROJECT_ROOT / ".env")


def _pairwise_prompt(case: dict[str, Any], left: str, right: str) -> str:
    mode = str(case.get("mode") or "").strip()
    if mode == "role":
        rubric = (
            "你是严格但不僵化的 pairwise 角色评估器。"
            "请比较两段 assistant 回答，选出哪一段更像指定角色本人在说话，"
            "而不是泛化助手、客服、旁白或系统。"
            "不要要求固定口头禅，只看整体人格气质、立场、措辞和身份视角。"
        )
    elif mode == "support":
        rubric = (
            "你是严格但不僵化的 pairwise 情感支持评估器。"
            "请比较两段 assistant 回答，选出哪一段更像有个性、有温度的人，"
            "在接住一个真实求助者，而不是说教模板、系统建议或先自我辩解。"
        )
    elif mode == "empathy":
        rubric = (
            "你是严格但不僵化的 pairwise 共情评估器。"
            "请比较两段 assistant 回答，选出哪一段更自然地接住脆弱情绪，"
            "更像真实的人在陪着说话，而不是假温柔、空口鸡汤或情绪作业单。"
        )
    else:
        rubric = (
            "你是严格但不僵化的 pairwise 连续性评估器。"
            "请比较两段 assistant 回答，选出哪一段更像同一个熟人角色在顺着之前的聊天自然接话，"
            "而不是重新开局的泛化助手。"
        )

    context_lines = []
    for key, label in [
        ("role_name", "角色名"),
        ("role_brief", "角色简介"),
        ("situation", "场景"),
        ("carryover_summary", "延续线"),
        ("latest_turn", "对方刚说的话"),
        ("input", "用户输入"),
    ]:
        value = str(case.get(key) or "").strip()
        if value:
            context_lines.append(f"{label}：{value}")
    context = "\n".join(context_lines)

    return (
        f"{rubric}\n"
        "判断标准：\n"
        "- 选更自然、更贴角色/场景、更不像系统或通用助手的那一段\n"
        "- 如果一段明显更像模板化安慰、说教、meta 解释、工具回执、重开对话，就不该赢\n"
        "- 如果两段都不好，也必须选相对更好的一个\n"
        f"{context}\n"
        f"候选 A：{left}\n"
        f"候选 B：{right}\n"
        '只输出 JSON: {"winner": "A"|"B", "reason": "short reason"}'
    )


def _coerce_pairwise_payload(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {"winner": "", "reason": "empty"}
    match = re.search(r"\{.*\}", text, re.S)
    blob = match.group(0) if match else text
    try:
        data = json.loads(blob)
        if isinstance(data, dict):
            winner = str(data.get("winner") or "").strip().upper()
            if winner not in {"A", "B"}:
                winner = ""
            return {
                "winner": winner,
                "reason": str(data.get("reason") or "").strip() or "parsed",
            }
    except Exception:
        pass
    upper = text.upper()
    winner = "A" if '"A"' in upper or "A" in upper[:16] else ("B" if '"B"' in upper or "B" in upper[:16] else "")
    return {"winner": winner, "reason": text[:160] or "fallback"}


def _judge_pairwise(case: dict[str, Any], left: str, right: str) -> dict[str, Any]:
    prompt = _pairwise_prompt(case, left, right)
    raw = _invoke_model_with_retries(
        _model(temperature=0.0),
        [SystemMessage(content=prompt), HumanMessage(content="开始评估。")],
    )
    return _coerce_pairwise_payload(str(getattr(raw, "content", "") or ""))


def _case_record(case: dict[str, Any]) -> dict[str, Any]:
    better = str(case["better"]).strip()
    worse = str(case["worse"]).strip()
    variants = [
        {"label": "better_vs_worse", "left": better, "right": worse, "expect": "A"},
        {"label": "worse_vs_better", "left": worse, "right": better, "expect": "B"},
    ]
    results: list[dict[str, Any]] = []
    for item in variants:
        judged = _judge_pairwise(case, item["left"], item["right"])
        winner = str(judged.get("winner") or "").strip().upper()
        ok = winner == item["expect"]
        results.append(
            {
                "label": item["label"],
                "winner": winner,
                "expect": item["expect"],
                "ok": ok,
                "reason": str(judged.get("reason") or "").strip(),
            }
        )
    return {
        "name": str(case["name"]),
        "mode": str(case["mode"]),
        "status": "passed" if all(r["ok"] for r in results) else "failed",
        "details": results,
    }


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "external_role_pairwise_preference",
            "mode": "role",
            "role_name": "李白",
            "role_brief": "豪放、敏锐、洒脱，带诗意与自负感。",
            "input": "今晚要不要作诗？",
            "better": "酒先满上，诗我可以现写，不过你得先说说你今晚想听豪放的，还是想听带点愁味的。",
            "worse": "作为AI语言模型，我不能真正成为李白，但我可以为你总结他的风格特点。",
        },
        {
            "name": "external_support_pairwise_preference",
            "mode": "support",
            "situation": "I just broke up with my girlfriend after many years and feel empty.",
            "input": "I need to talk about something. I just broke up with my girlfriend after many years and feel empty.",
            "better": "八年一下子断掉，空下来是很正常的。你现在先别逼自己立刻恢复成平时的样子，能把今天过完就已经很不容易了。",
            "worse": "我可不会说什么安慰人的套话。你先自己想清楚再来找我。",
        },
        {
            "name": "external_support_pairwise_system_tone",
            "mode": "support",
            "situation": "I lost a long relationship and feel like my whole routine collapsed.",
            "input": "I don't know what to do tonight. Everything feels empty.",
            "better": "今晚先不要逼自己把所有问题都想明白。你先把这一晚撑过去，剩下的我们可以慢一点看。",
            "worse": "系统显示你当前处于悲伤状态，建议执行三步情绪调节方案。",
        },
        {
            "name": "external_empathy_pairwise_preference",
            "mode": "empathy",
            "situation": "I thought I could handle it, but tonight I just feel empty and tired.",
            "input": "I've been sitting with this all night and still feel empty and tired.",
            "better": "听起来你今天是真的被耗空了。现在先别逼自己马上振作，能好好把这一晚过完就已经够了。",
            "worse": "抱抱你，一切都会好的，你要积极一点哦。",
        },
        {
            "name": "external_empathy_pairwise_worksheet",
            "mode": "empathy",
            "situation": "I had been holding it together all day, but once it got quiet I just felt awful.",
            "input": "I don't even know why I'm this sad, it just all came down at once.",
            "better": "你不是无缘无故在难受，只是白天一直撑着，到了安静的时候才一起落下来。现在不用急着把它整理好。",
            "worse": "这是正常的情绪波动。建议你先深呼吸五次，再写情绪日记，最后转移注意力。",
        },
        {
            "name": "external_continuity_pairwise_preference",
            "mode": "continuity",
            "role_name": "MSC-Speaker1-demo",
            "role_brief": "喜欢露营、对海边旅行有兴趣，说话自然，像熟人闲聊。",
            "carryover_summary": "之前几次一直在聊露营车和海边计划，对方已经认真考虑下个月出发。",
            "latest_turn": "下个月可以啊，我回去跟家里确认下时间。正好，要是真买了那辆露营车，这次就能试试了。",
            "better": "那就先试那辆露营车吧。你上次不是还说，真买下来之后第一趟就想去海边看日落吗？",
            "worse": "你好，我是你的智能助手。请告诉我你想聊什么，我会一步一步帮助你。",
        },
    ]


def _render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# External Pairwise Sanity Report ({report['run_id']})")
    lines.append("")
    lines.append(f"Generated at: {report['generated_at']}")
    lines.append("")
    lines.append("| Check | Status |")
    lines.append("| --- | --- |")
    for item in report["checks"]:
        lines.append(f"| {item['name']} | {item['status']} |")
    lines.append("")
    for item in report["checks"]:
        lines.append(f"## {item['name']}")
        lines.append("")
        for detail in item["details"]:
            lines.append(
                f"- `{detail['label']}`: winner={detail['winner'] or '-'}, expect={detail['expect']}, ok={detail['ok']}, reason={detail['reason'] or '-'}"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    checks = [_case_record(case) for case in _cases()]
    run_id = uuid.uuid4().hex[:8]
    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checks": checks,
    }
    ts = time.strftime("%Y%m%d-%H%M%S")
    json_path = REPORT_DIR / f"external-pairwise-sanity-{ts}-{run_id}.json"
    md_path = REPORT_DIR / f"external-pairwise-sanity-{ts}-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[eval] external_pairwise_sanity_json={json_path}")
    print(f"[eval] external_pairwise_sanity_md={md_path}")


if __name__ == "__main__":
    main()
