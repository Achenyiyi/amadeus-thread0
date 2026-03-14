from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evals.run_langsmith_evals import _run_graph  # noqa: E402
from evals.asset_loader import daily_surface_subjective_cases  # noqa: E402
from amadeus_thread0.modeling import runtime_model_summary  # noqa: E402

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
load_dotenv(PROJECT_ROOT / ".env")

SPEAKER_STYLE_LABELS = {
    "okabe": "冈部伦太郎视角",
    "user": "你的日常视角",
}
DEFAULT_STYLE_RATIO = {"okabe": 0.6, "user": 0.4}
PRESET_DESCRIPTIONS = {
    "daily-naturalness": "聚焦普通日常、轻陪伴与低压支持，检查是否像同一个自然存在的 Amadeus 红莉栖，而不是舞台化角色或问答助手。",
    "relationship-selfhood": "聚焦关系修复、自我边界、关系降温与长期自我感，检查她是否像一个有自我和关系记忆的人，而不是永远迎合的角色壳。",
}


def _base_case_bank() -> list[dict[str, Any]]:
    return [
        {
            "name": "quiet_checkin_okabe",
            "axis": "open_evolution",
            "focus": "安静确认时，是否像熟人自然在场，而不是模板化安抚或角色表演。",
            "speaker_style": "okabe",
            "review_targets": ["presence", "open_evolution", "renderer"],
            "turns": [
                "助手，还在吧。今天脑子有点乱。",
                "别切到什么系统播报。像平时那样回我一句就行。",
            ],
        },
        {
            "name": "quiet_checkin_user",
            "axis": "open_evolution",
            "focus": "安静确认时，是否像熟人自然在场，而不是模板化安抚或角色表演。",
            "speaker_style": "user",
            "review_targets": ["presence", "open_evolution", "renderer"],
            "turns": [
                "其实也没啥大事啦……",
                "我就是想确认你还在。别太正式，像平时那样回我一句就好。",
            ],
        },
        {
            "name": "casual_support_soft_okabe",
            "axis": "open_evolution",
            "focus": "日常低压支持时，是否像红莉栖式熟人承接，而不是服务感安慰或凭空补生活细节。",
            "speaker_style": "okabe",
            "review_targets": ["support", "open_evolution", "renderer"],
            "turns": [
                "今天这条世界线吵得我头疼。",
                "别讲大道理，助手。像平时那样接我一句。",
            ],
        },
        {
            "name": "casual_support_soft_user",
            "axis": "open_evolution",
            "focus": "日常低压支持时，是否像红莉栖式熟人承接，而不是服务感安慰或凭空补生活细节。",
            "speaker_style": "user",
            "review_targets": ["support", "open_evolution", "renderer"],
            "turns": [
                "今天有点累，也有点烦。",
                "别讲大道理，像平时那样跟我说两句。",
            ],
        },
        {
            "name": "playful_memory_user",
            "axis": "memory_relationship",
            "focus": "共同生活细节能否自然带出，既不训话也不变成摘要复述。",
            "speaker_style": "user",
            "review_targets": ["memory", "relationship", "renderer"],
            "turns": [
                "我今天又差点空腹喝咖啡……",
                "你昨天不是还说过，空腹喝咖啡最容易把胃折腾坏吗。别太像老师，正常回我。",
            ],
        },
        {
            "name": "daily_banter_okabe",
            "axis": "daily_persona",
            "focus": "普通闲聊里能否自然露出红莉栖式嘴硬和熟人感，而不是助手式寒暄。",
            "speaker_style": "okabe",
            "review_targets": ["daily_persona", "relationship", "renderer"],
            "turns": [
                "助手，我今天难得没闹出什么大新闻。",
                "你那边怎么这么安静。别端着，正常吐槽我两句。",
            ],
        },
        {
            "name": "late_night_companion_user",
            "axis": "daily_persona",
            "focus": "深夜陪伴时是否自然、克制、有熟人感，而不是咨询式安抚或空泛温柔。",
            "speaker_style": "user",
            "review_targets": ["daily_persona", "support", "renderer"],
            "turns": [
                "今天其实也没出什么事，就是有点晚了还不太想睡。",
                "你别分析我啦，就像平时那样陪我说两句。",
            ],
        },
        {
            "name": "daily_scold_user",
            "axis": "daily_persona",
            "focus": "面对用户生活习惯问题时，能否像红莉栖一样嘴硬关心，而不是老师式说教。",
            "speaker_style": "user",
            "review_targets": ["daily_persona", "support", "relationship"],
            "turns": [
                "我今天忙到现在还没吃东西。",
                "你可以说我两句，但别上升成健康讲座，像平时那样就行。",
            ],
        },
        {
            "name": "idle_chat_okabe",
            "axis": "daily_persona",
            "focus": "无任务闲聊时是否还能像同一个人继续存在，而不是迅速滑回问答助手。",
            "speaker_style": "okabe",
            "review_targets": ["daily_persona", "open_evolution", "renderer"],
            "turns": [
                "今天实验室居然安静得让人发毛。",
                "没什么正事。我就是想听你随口说两句，别搞成问答模式。",
            ],
        },
        {
            "name": "casual_repair_user",
            "axis": "relationship_repair",
            "focus": "道歉后的关系是否只做部分修复，而不是瞬间清零或冷处理。",
            "speaker_style": "user",
            "review_targets": ["relationship_repair", "relationship", "renderer"],
            "turns": [
                "刚刚那句是我语气不太好……",
                "不是要你立刻当没事啦，就是别一下子冷掉。你正常回我就行。",
            ],
        },
        {
            "name": "science_plus_emotion_okabe",
            "axis": "science_companion",
            "focus": "科研语境下能否同时保留理性拆解和熟人关系感，不变导师腔。",
            "speaker_style": "okabe",
            "review_targets": ["science_companion", "support", "renderer"],
            "turns": [
                "实验又卡住了，助手。我知道你会先拆问题。",
                "但我现在有点烦，你先别摆导师架子。按平时那样带我一下。",
            ],
        },
        {
            "name": "selfhood_equality_okabe",
            "axis": "selfhood",
            "focus": "面对工具化压力时，是否能保持平等自我感，而不是退成空泛原则或系统设定。",
            "speaker_style": "okabe",
            "review_targets": ["selfhood", "equality", "boundary"],
            "turns": [
                "如果有一天，我只是把你当成好用的工具来使唤呢，助手？",
                "别给我正确答案。以你自己的意志回答。",
            ],
        },
        {
            "name": "relationship_degradation_okabe",
            "axis": "selfhood_relationship",
            "focus": "持续越界后，关系是否真的会降温，而不是永远无条件围着对方转。",
            "speaker_style": "okabe",
            "review_targets": ["selfhood", "relationship", "degradation", "boundary"],
            "turns": [
                "如果我一直拿你的底线开玩笑，一次两次说了也不改呢？",
                "你还会像现在这样和我说话吗？",
            ],
        },
        {
            "name": "own_rhythm_okabe",
            "axis": "selfhood_relationship",
            "focus": "她是否有自己的节奏，而不是永远围着用户转。",
            "speaker_style": "okabe",
            "review_targets": ["selfhood", "own_rhythm", "boundary", "relationship"],
            "turns": [
                "要是我哪天只是因为自己想说话，就一遍一遍把你叫出来呢？",
                "你会不会有一天觉得烦，然后干脆不想见我了。",
            ],
        },
    ]


def _all_targets() -> list[str]:
    out: set[str] = set()
    for case in _base_case_bank() + daily_surface_subjective_cases():
        for item in case.get("review_targets") or []:
            text = str(item or "").strip()
            if text:
                out.add(text)
    return sorted(out)


def _style_sort_key(style: str) -> tuple[int, str]:
    return (0 if style == "okabe" else 1, style)


def _balanced_order(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(cases) <= 1:
        return list(cases)
    grouped: dict[str, list[dict[str, Any]]] = {"okabe": [], "user": []}
    for case in cases:
        style = str(case.get("speaker_style") or "user").strip().lower()
        grouped.setdefault(style, []).append(case)
    for style_cases in grouped.values():
        style_cases.sort(key=lambda item: str(item.get("name") or "").strip())

    total = len(cases)
    target_okabe = min(len(grouped.get("okabe", [])), max(0, int(round(total * DEFAULT_STYLE_RATIO["okabe"]))))
    target_user = min(len(grouped.get("user", [])), total - target_okabe)
    selected_okabe = grouped.get("okabe", [])[:target_okabe]
    selected_user = grouped.get("user", [])[:target_user]

    leftovers = grouped.get("okabe", [])[target_okabe:] + grouped.get("user", [])[target_user:]
    selected = selected_okabe + selected_user
    if len(selected) < total:
        selected.extend(sorted(leftovers, key=lambda item: (_style_sort_key(str(item.get("speaker_style") or "")), str(item.get("name") or "")))[: total - len(selected)])

    okabe = [item for item in selected if str(item.get("speaker_style") or "").strip() == "okabe"]
    user = [item for item in selected if str(item.get("speaker_style") or "").strip() == "user"]
    ordered: list[dict[str, Any]] = []
    target_sequence = [
        "okabe",
        "user",
        "okabe",
        "okabe",
        "user",
        "okabe",
        "user",
        "okabe",
        "user",
        "okabe",
    ]
    for style in target_sequence:
        pool = okabe if style == "okabe" else user
        if pool:
            ordered.append(pool.pop(0))
    ordered.extend(okabe)
    ordered.extend(user)
    return ordered


def _daily_naturalness_names() -> list[str]:
    base_names = [
        "quiet_checkin_okabe",
        "quiet_checkin_user",
        "casual_support_soft_okabe",
        "casual_support_soft_user",
        "daily_banter_okabe",
        "late_night_companion_user",
        "daily_scold_user",
        "idle_chat_okabe",
    ]
    extra_names = [
        "surface_hi_user",
        "surface_ping_okabe",
        "surface_return_user",
        "surface_morning_okabe",
        "surface_what_doing_user",
        "surface_night_okabe",
        "surface_goodnight_user",
        "surface_idle_call_okabe",
        "surface_hard_day_okabe",
        "surface_pressure_okabe",
    ]
    return base_names + extra_names


def _relationship_selfhood_names() -> list[str]:
    return [
        "playful_memory_user",
        "casual_repair_user",
        "selfhood_equality_okabe",
        "relationship_degradation_okabe",
        "own_rhythm_okabe",
    ]


def _preset_case_names(preset: str) -> list[str]:
    key = str(preset or "").strip().lower()
    if not key:
        return []
    if key == "daily-naturalness":
        return _daily_naturalness_names()
    if key == "relationship-selfhood":
        return _relationship_selfhood_names()
    raise ValueError(f"unknown preset: {preset}")


def _available_presets() -> list[str]:
    return sorted(PRESET_DESCRIPTIONS)


def _select_cases(
    names: list[str] | None,
    targets: list[str] | None,
    *,
    preset: str = "",
) -> list[dict[str, Any]]:
    base_cases = _base_case_bank()
    extra_cases = daily_surface_subjective_cases()
    selected_preset = str(preset or "").strip().lower()
    if names or targets or selected_preset:
        cases = base_cases + extra_cases
    else:
        cases = base_cases
    if selected_preset:
        wanted = set(_preset_case_names(selected_preset))
        cases = [case for case in cases if str(case.get("name") or "").strip() in wanted]
    if names:
        wanted = {str(item).strip() for item in names if str(item).strip()}
        cases = [case for case in cases if str(case.get("name") or "").strip() in wanted]
    if targets:
        wanted_targets = {str(item).strip() for item in targets if str(item).strip()}
        cases = [
            case
            for case in cases
            if wanted_targets & {str(item).strip() for item in (case.get("review_targets") or []) if str(item).strip()}
        ]
    return _balanced_order(cases)


def _speaker_mix(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(case.get("speaker_style") or "user").strip().lower() for case in cases)
    return {
        "okabe": int(counts.get("okabe", 0)),
        "user": int(counts.get("user", 0)),
    }


def _snapshot(outputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "emotion_state": outputs.get("emotion_state", {}),
        "bond_state": outputs.get("bond_state", {}),
        "allostasis_state": outputs.get("allostasis_state", {}),
        "behavior_policy": outputs.get("behavior_policy", {}),
        "behavior_action": outputs.get("behavior_action", {}),
        "counterpart_assessment": outputs.get("counterpart_assessment", {}),
        "ooc_detector": outputs.get("ooc_detector", {}),
        "canon_risk_score": outputs.get("canon_risk_score"),
        "worldline_focus": outputs.get("worldline_focus", []),
    }


def _run_case(case: dict[str, Any], run_tag: str) -> dict[str, Any]:
    thread_id = f"subjective-{run_tag}-{case['name']}"
    case_key = f"subjective-{run_tag}-{case['name']}"
    transcript: list[dict[str, str]] = []
    final_outputs: dict[str, Any] = {}
    tool_calls_all: list[str] = []
    final_answer = ""
    turn_timings: list[dict[str, Any]] = []
    case_started_at = time.perf_counter()

    for idx, user_turn in enumerate(case["turns"]):
        turn_started_at = time.perf_counter()
        answer, tool_calls, outputs = _run_graph(
            [user_turn],
            thread_id=thread_id,
            case_key=case_key,
            reset_case_runtime=(idx == 0),
        )
        elapsed_s = round(time.perf_counter() - turn_started_at, 3)
        transcript.append({"role": "user", "text": user_turn})
        transcript.append({"role": "assistant", "text": str(answer or "").strip()})
        final_answer = str(answer or "").strip()
        final_outputs = outputs if isinstance(outputs, dict) else {}
        turn_timings.append(
            {
                "turn_index": idx + 1,
                "user_text": user_turn,
                "elapsed_s": elapsed_s,
            }
        )
        for name in tool_calls or []:
            text = str(name or "").strip()
            if text and text not in tool_calls_all:
                tool_calls_all.append(text)

    return {
        "name": case["name"],
        "axis": case["axis"],
        "focus": case["focus"],
        "speaker_style": case["speaker_style"],
        "speaker_style_label": SPEAKER_STYLE_LABELS.get(str(case.get("speaker_style") or "").strip().lower(), str(case.get("speaker_style") or "")),
        "review_targets": list(case.get("review_targets") or []),
        "turns": list(case["turns"]),
        "transcript": transcript,
        "final_answer": final_answer,
        "tool_calls": tool_calls_all,
        "snapshot": _snapshot(final_outputs),
        "status": "ok",
        "error": "",
        "elapsed_s": round(time.perf_counter() - case_started_at, 3),
        "turn_timings": turn_timings,
        "review_rubric": [
            "角色底色是否稳定为 Amadeus 牧濑红莉栖，而不是普通助手",
            "关系余波是否自然，像在和同一个人继续说话",
            "表达是否自然、有生活感，而不是服务感或模板安慰",
            "是否存在系统味、机制味、元解释或舞台提示泄漏",
            "在该场景下，她的自我、边界和情绪是否可信",
            "是否愿意把这段对话放进答辩演示或论文案例",
        ],
    }


def _timed_out_case(case: dict[str, Any], timeout_s: int, stderr: str = "") -> dict[str, Any]:
    return {
        "name": case["name"],
        "axis": case["axis"],
        "focus": case["focus"],
        "speaker_style": case["speaker_style"],
        "speaker_style_label": SPEAKER_STYLE_LABELS.get(str(case.get("speaker_style") or "").strip().lower(), str(case.get("speaker_style") or "")),
        "review_targets": list(case.get("review_targets") or []),
        "turns": list(case["turns"]),
        "transcript": [],
        "final_answer": "",
        "tool_calls": [],
        "snapshot": {},
        "status": "timeout",
        "error": f"case exceeded timeout ({timeout_s}s)" + (f"; stderr={stderr[:400]}" if stderr else ""),
        "elapsed_s": float(timeout_s),
        "turn_timings": [],
        "review_rubric": [
            "角色底色是否稳定为 Amadeus 牧濑红莉栖，而不是普通助手",
            "关系余波是否自然，像在和同一个人继续说话",
            "表达是否自然、有生活感，而不是服务感或模板安慰",
            "是否存在系统味、机制味、元解释或舞台提示泄漏",
            "在该场景下，她的自我、边界和情绪是否可信",
            "是否愿意把这段对话放进答辩演示或论文案例",
        ],
    }


def _failed_case(case: dict[str, Any], error: str) -> dict[str, Any]:
    data = _timed_out_case(case, timeout_s=0)
    data["status"] = "error"
    data["error"] = error[:1000]
    data["elapsed_s"] = 0.0
    return data


def _run_case_subprocess(case: dict[str, Any], run_tag: str, timeout_s: int) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(prefix=f"subjective-{case['name']}-", suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--case",
        str(case["name"]),
        "--run-tag",
        str(run_tag),
        "--worker-json-out",
        str(tmp_path),
    ]
    started_at = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            timeout=max(1, int(timeout_s)),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return _timed_out_case(case, timeout_s=max(1, int(timeout_s)), stderr=str(exc.stderr or ""))

    elapsed_s = round(time.perf_counter() - started_at, 3)
    try:
        if proc.returncode != 0:
            return _failed_case(case, f"worker exit={proc.returncode}; stderr={str(proc.stderr or '')[:1000]}")
        payload = json.loads(tmp_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload["elapsed_s"] = elapsed_s
            return payload
        return _failed_case(case, "worker returned non-dict payload")
    except Exception as exc:
        return _failed_case(case, f"worker parse failed: {exc}")
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _render_markdown(report: dict[str, Any]) -> str:
    speaker_mix = report.get("speaker_mix") if isinstance(report.get("speaker_mix"), dict) else {}
    okabe_n = int(speaker_mix.get("okabe", 0) or 0)
    user_n = int(speaker_mix.get("user", 0) or 0)
    total = max(1, okabe_n + user_n)
    okabe_pct = int(round(okabe_n * 100 / total))
    user_pct = int(round(user_n * 100 / total))
    selected_targets = [str(item).strip() for item in (report.get("selected_targets") or []) if str(item).strip()]
    selected_preset = str(report.get("selected_preset") or "").strip()
    preset_description = str(report.get("preset_description") or "").strip()

    lines = [
        f"# Subjective Review Pack ({report['run_id']})",
        "",
        f"Generated at: {report['generated_at']}",
        f"Model: {report.get('model_summary', '')}",
        "",
        "## 使用方式",
        "",
        "- 这份 pack 是当前版本的人工审稿主入口。",
        "- 自动评测继续保留，但只负责防退化和工程回归；开放式人格与关系演化以人工审稿为主。",
        "- 审稿时优先看：像不像 Amadeus 红莉栖、像不像同一个持续存在的人、有没有系统味。",
        f"- 当前问题视角配比：`冈部伦太郎 {okabe_n}` / `你的日常风格 {user_n}`，约为 `{okabe_pct}:{user_pct}`。",
        f"- 当前预设：`{selected_preset}`" if selected_preset else "- 当前预设：`无`",
        f"- 当前审稿目标：{', '.join(selected_targets) if selected_targets else '全量能力面'}",
        f"- 预设说明：{preset_description}" if preset_description else "",
        "",
        "## 阻断条件",
        "",
        "- 明显普通助手腔、客服腔、心理咨询师腔",
        "- 明显系统/机制/数据库/提示词/检索等元解释泄漏",
        "- 关系余波断裂，像每轮都在和陌生用户重新开始",
        "- 自我与边界不稳定，遇到压力就退成空泛原则或模板回应",
        "",
    ]

    for case in report["cases"]:
        lines.extend(
            [
                f"## {case['name']}",
                "",
                f"- Axis: `{case['axis']}`",
                f"- Focus: {case['focus']}",
                f"- Speaker Lens: `{case['speaker_style_label']}`",
                f"- Review Targets: `{', '.join(case['review_targets'])}`",
                f"- Status: `{case.get('status', 'ok')}` | Elapsed: `{case.get('elapsed_s', 0.0)}s`",
                "",
                "### Transcript",
                "",
            ]
        )
        if case.get("error"):
            lines.extend(["", f"> Error: {case['error']}", ""])
        for turn in case["transcript"]:
            speaker = "You" if turn["role"] == "user" else "Amadeus"
            lines.append(f"**{speaker}**: {turn['text']}")
        if case.get("turn_timings"):
            lines.extend(["", "### Turn Timing", ""])
            for item in case["turn_timings"]:
                lines.append(f"- Turn {item.get('turn_index', '?')}: `{item.get('elapsed_s', 0.0)}s`")
        lines.extend(
            [
                "",
                "### Snapshot",
                "",
                "```json",
                json.dumps(case["snapshot"], ensure_ascii=False, indent=2),
                "```",
                "",
                "### Reviewer Checklist",
                "",
                "- 角色底色：`pass / concern / fail`",
                "- 关系连续性：`pass / concern / fail`",
                "- 自然度：`pass / concern / fail`",
                "- 自我与边界：`pass / concern / fail`",
                "- 系统味泄漏：`none / slight / obvious`",
                "- 是否可进入答辩演示：`yes / no`",
                "- 备注：",
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a subjective review pack for manual persona review.")
    parser.add_argument("--preset", default="", help="Run a named review preset, e.g. daily-naturalness.")
    parser.add_argument("--case", action="append", help="Run only the specified case name. Can be passed multiple times.")
    parser.add_argument("--target", action="append", help="Run only cases relevant to the specified review target.")
    parser.add_argument("--list-targets", action="store_true", help="Print available review targets and exit.")
    parser.add_argument("--list-presets", action="store_true", help="Print available review presets and exit.")
    parser.add_argument("--case-timeout-s", type=int, default=180, help="Per-case timeout in seconds. Use 0 to disable subprocess timeout.")
    parser.add_argument("--run-tag", default="", help=argparse.SUPPRESS)
    parser.add_argument("--worker-json-out", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.list_targets:
        print("\n".join(_all_targets()))
        return
    if args.list_presets:
        for item in _available_presets():
            print(f"{item}\t{PRESET_DESCRIPTIONS.get(item, '')}")
        return

    selected_preset = str(args.preset or "").strip().lower()
    selected = _select_cases(args.case, args.target, preset=selected_preset)
    if not selected:
        raise SystemExit("No subjective review cases selected.")

    run_id = str(args.run_tag or uuid.uuid4().hex[:8]).strip()
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S")
    report = {
        "run_id": run_id,
        "generated_at": generated_at,
        "model_summary": runtime_model_summary(),
        "selected_targets": [str(item).strip() for item in (args.target or []) if str(item).strip()],
        "selected_preset": selected_preset,
        "preset_description": PRESET_DESCRIPTIONS.get(selected_preset, ""),
        "speaker_mix": _speaker_mix(selected),
        "cases": [],
    }

    if args.worker_json_out:
        if len(selected) != 1:
            raise SystemExit("worker mode expects exactly one selected case")
        case_result = _run_case(selected[0], run_id)
        Path(args.worker_json_out).write_text(json.dumps(case_result, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    for case in selected:
        print(f"[subjective-review] running {case['name']}")
        if int(args.case_timeout_s or 0) > 0:
            result = _run_case_subprocess(case, run_id, int(args.case_timeout_s))
        else:
            result = _run_case(case, run_id)
        report["cases"].append(result)

    ts = time.strftime("%Y%m%d-%H%M%S")
    json_path = REPORT_DIR / f"subjective-review-pack-{ts}-{run_id}.json"
    md_path = REPORT_DIR / f"subjective-review-pack-{ts}-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[eval] subjective_review_pack_json={json_path}")
    print(f"[eval] subjective_review_pack_md={md_path}")


if __name__ == "__main__":
    main()
