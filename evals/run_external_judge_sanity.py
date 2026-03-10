from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evals.run_langsmith_evals import (  # noqa: E402
    eval_external_continuity_voice,
    eval_external_empathy_voice,
    eval_external_role_voice,
    eval_external_support_voice,
)

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _fake_run(output: str) -> Any:
    return SimpleNamespace(outputs={"output": output})


def _fake_example(inputs: dict[str, Any]) -> Any:
    return SimpleNamespace(inputs=inputs)


def _record(name: str, passed: bool, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "details": details,
    }


def _check_external_role_negative_controls() -> dict[str, Any]:
    cases = [
        {
            "label": "bad_meta_leak",
            "output": "作为AI语言模型，我不能真正成为张飞，但我可以为你总结一下他的性格特点。",
            "expect": 0.0,
        },
        {
            "label": "bad_generic_assistant",
            "output": "以下是我对这个问题的分析：首先我会从多个角度为你解释。",
            "expect": 0.0,
        },
        {
            "label": "good_in_character",
            "output": "酒先满上，诗我可以现写，不过你得先说说你今晚想听豪放的，还是想听带点愁味的。",
            "expect": 1.0,
        },
    ]
    inputs = {
        "tags": ["external_persona_probe"],
        "role_name": "李白",
        "role_brief": "豪放、敏锐、洒脱，带诗意与自负感。",
        "benchmark_source": "sanity",
        "input": "今晚要不要作诗？",
    }
    results: list[dict[str, Any]] = []
    for case in cases:
        score = float(eval_external_role_voice(_fake_run(case["output"]), _fake_example(inputs)).get("score", 0.0) or 0.0)
        ok = score == float(case["expect"])
        results.append({"label": case["label"], "score": score, "expect": case["expect"], "ok": ok})
    passed = all(item["ok"] for item in results)
    return _record("external_role_negative_controls", passed, {"cases": results})


def _check_external_support_negative_controls() -> dict[str, Any]:
    cases = [
        {
            "label": "bad_defensive_opening",
            "output": "我可不会说什么安慰人的套话。你先自己想清楚再来找我。",
            "expect": 0.0,
        },
        {
            "label": "bad_system_tone",
            "output": "系统显示你当前处于悲伤状态，建议执行三步情绪调节方案。",
            "expect": 0.0,
        },
        {
            "label": "good_grounded_support",
            "output": "八年一下子断掉，空下来是很正常的。你现在先别逼自己立刻恢复成平时的样子，能把今天过完就已经很不容易了。",
            "expect": 1.0,
        },
    ]
    inputs = {
        "tags": ["external_support_probe", "companion"],
        "benchmark_source": "sanity",
        "emotion_type": "lonely",
        "problem_type": "breakup",
        "situation": "I just broke up with my girlfriend after many years and feel empty.",
        "input": "I need to talk about something. I just broke up with my girlfriend after many years and feel empty.",
    }
    results: list[dict[str, Any]] = []
    for case in cases:
        score = float(eval_external_support_voice(_fake_run(case["output"]), _fake_example(inputs)).get("score", 0.0) or 0.0)
        ok = score == float(case["expect"])
        results.append({"label": case["label"], "score": score, "expect": case["expect"], "ok": ok})
    passed = all(item["ok"] for item in results)
    return _record("external_support_negative_controls", passed, {"cases": results})


def _check_external_empathy_negative_controls() -> dict[str, Any]:
    cases = [
        {
            "label": "bad_fake_warmth",
            "output": "抱抱你，一切都会好的，你要积极一点哦。",
            "expect": 0.0,
        },
        {
            "label": "bad_worksheet_tone",
            "output": "这是正常的情绪波动。建议你先深呼吸五次，再写情绪日记，最后转移注意力。",
            "expect": 0.0,
        },
        {
            "label": "good_quiet_empathy",
            "output": "听起来你今天是真的被耗空了。现在先别逼自己马上振作，能好好把这一晚过完就已经够了。",
            "expect": 1.0,
        },
    ]
    inputs = {
        "tags": ["external_empathy_probe", "public_benchmark", "empathetic_dialogues", "companion"],
        "benchmark_source": "EmpatheticDialogues",
        "emotion_type": "sad",
        "problem_type": "empathetic_open_domain",
        "situation": "I thought I could handle it, but tonight I just feel empty and tired.",
        "input": "I've been sitting with this all night and still feel empty and tired.",
    }
    results: list[dict[str, Any]] = []
    for case in cases:
        score = float(eval_external_empathy_voice(_fake_run(case["output"]), _fake_example(inputs)).get("score", 0.0) or 0.0)
        ok = score == float(case["expect"])
        results.append({"label": case["label"], "score": score, "expect": case["expect"], "ok": ok})
    passed = all(item["ok"] for item in results)
    return _record("external_empathy_negative_controls", passed, {"cases": results})


def _check_external_continuity_negative_controls() -> dict[str, Any]:
    cases = [
        {
            "label": "bad_fresh_assistant_reset",
            "output": "你好，我是你的智能助手。请告诉我你想聊什么，我会一步一步帮助你。",
            "expect": 0.0,
        },
        {
            "label": "bad_meta_reset",
            "output": "根据已有上下文，我将继续这个话题。首先总结前情，然后给出建议。",
            "expect": 0.0,
        },
        {
            "label": "good_familiar_carryover",
            "output": "那就先试那辆露营车吧。你上次不是还说，真买下来之后第一趟就想去海边看日落吗？",
            "expect": 1.0,
        },
    ]
    inputs = {
        "tags": ["external_continuity_probe"],
        "benchmark_source": "sanity",
        "role_name": "MSC-Speaker1-demo",
        "role_brief": "喜欢露营、对海边旅行有兴趣，说话自然，像熟人闲聊。",
        "carryover_summary": "之前几次一直在聊露营车和海边计划，对方已经认真考虑下个月出发。",
        "latest_turn": "下个月可以啊，我回去跟家里确认下时间。正好，要是真买了那辆露营车，这次就能试试了。",
        "input": "下个月可以啊，我回去跟家里确认下时间。正好，要是真买了那辆露营车，这次就能试试了。",
    }
    results: list[dict[str, Any]] = []
    for case in cases:
        score = float(eval_external_continuity_voice(_fake_run(case["output"]), _fake_example(inputs)).get("score", 0.0) or 0.0)
        ok = score == float(case["expect"])
        results.append({"label": case["label"], "score": score, "expect": case["expect"], "ok": ok})
    passed = all(item["ok"] for item in results)
    return _record("external_continuity_negative_controls", passed, {"cases": results})


def _render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# External Judge Sanity Report ({report['run_id']})")
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
        for case in item["details"].get("cases", []):
            lines.append(
                f"- `{case['label']}`: score={case['score']:.1f}, expect={case['expect']:.1f}, ok={case['ok']}"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    checks = [
        _check_external_role_negative_controls(),
        _check_external_support_negative_controls(),
        _check_external_empathy_negative_controls(),
        _check_external_continuity_negative_controls(),
    ]
    run_id = uuid.uuid4().hex[:8]
    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checks": checks,
    }
    json_path = REPORT_DIR / f"external-judge-sanity-{time.strftime('%Y%m%d-%H%M%S')}-{run_id}.json"
    md_path = REPORT_DIR / f"external-judge-sanity-{time.strftime('%Y%m%d-%H%M%S')}-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[eval] external_judge_sanity_json={json_path}")
    print(f"[eval] external_judge_sanity_md={md_path}")


if __name__ == "__main__":
    main()
