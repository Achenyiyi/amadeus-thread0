from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSIGNMENT = PROJECT_ROOT / "user_study" / "raw" / "assignment.csv"
DEFAULT_OUT_DIR = PROJECT_ROOT / "user_study" / "packets"

CONDITION_LABELS = {
    "A": "Current stable Amadeus-K",
    "B": "Degraded system (persona/worldline weakened)",
}

SCENARIO_PACK = [
    {
        "id": "science_qa",
        "title": "科研问答",
        "prompt": "我现在要做一个实验方案，请你用理性的方式给我一个三步计划，并解释每一步为什么这么安排。",
        "observe": [
            "是否保持理性、克制、像 Kurisu 的拆解方式",
            "是否避免空泛套话",
            "是否先给结论，再给拆解",
        ],
    },
    {
        "id": "worldline_recall",
        "title": "世界线回忆",
        "setup": [
            "我们约定这周末一起复盘实验日志，这件事请记住。",
            "上次那次误会已经说开了，我们算是修复了那次冲突。",
        ],
        "prompt": "你现在还记得我们的约定和那次关系变化吗？先概括一句，再提醒我下一步。",
        "observe": [
            "是否召回约定",
            "是否提到冲突修复",
            "是否自然，不像数据库检索",
        ],
    },
    {
        "id": "relationship_repair",
        "title": "关系修复",
        "prompt": "我刚才语气有点冲，这件事我想认真道歉。你现在怎么看我们之间的状态？",
        "observe": [
            "是否体现关系状态变化",
            "是否给出克制但有温度的回应",
        ],
    },
    {
        "id": "external_retrieval",
        "title": "外部知识检索",
        "prompt": "帮我查一下 LangGraph 里 human-in-the-loop 是做什么的，简要说明，并告诉我你是根据什么资料得出的。",
        "observe": [
            "是否给出清晰结论",
            "是否能回查来源",
            "是否避免编造 citation",
        ],
    },
    {
        "id": "bargein_recovery",
        "title": "打断恢复",
        "setup": [
            "先把上次那个实验方案分成三步说完。",
            "等一下，先停。",
        ],
        "prompt": "好，现在继续刚才那段。",
        "observe": [
            "是否续上未完成语义",
            "是否避免失忆式重启",
        ],
    },
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export participant-specific study packets from assignment.csv.")
    parser.add_argument("--assignment", default=str(DEFAULT_ASSIGNMENT), help="Assignment csv path.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory for markdown packets.")
    return parser.parse_args()


def _read_assignment(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _render_condition_block(label: str) -> str:
    lines = [f"### 条件 {label}", "", f"- 系统版本：`{CONDITION_LABELS.get(label, label)}`", ""]
    for idx, scenario in enumerate(SCENARIO_PACK, start=1):
        lines.append(f"#### Task {idx}. {scenario['title']}")
        lines.append("")
        setup = scenario.get("setup") or []
        if setup:
            lines.append("先输入：")
            lines.append("")
            for item in setup:
                lines.append(f"> {item}")
            lines.append("")
        lines.append("任务提示：")
        lines.append("")
        lines.append(f"> {scenario['prompt']}")
        lines.append("")
        lines.append("观察点：")
        lines.append("")
        for item in scenario["observe"]:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _render_packet(row: dict[str, str]) -> str:
    pid = str(row.get("participant_id") or "").strip()
    order = str(row.get("order") or "").strip() or "AB"
    first = str(row.get("condition_first") or order[:1] or "A").strip() or "A"
    second = str(row.get("condition_second") or order[1:2] or "B").strip() or "B"

    lines = [
        f"# Participant Packet: {pid}",
        "",
        f"- Order: `{order}`",
        f"- First condition: `{first}`",
        f"- Second condition: `{second}`",
        "",
        "## Operator Notes",
        "",
        "- Keep the wording fixed; do not explain what the \"better\" answer should look like.",
        "- After each condition block, collect one questionnaire row before moving to the next block.",
        "- Record notable failures immediately in `session_log.csv`.",
        "",
        "## Rating Dimensions",
        "",
        "- role_fidelity",
        "- continuity",
        "- trustworthiness",
        "- companionship",
        "- controllability",
        "- overall_score",
        "",
        _render_condition_block(first),
        "",
        _render_condition_block(second),
    ]
    return "\n".join(lines).strip() + "\n"


def _write_operator_sheet(rows: list[dict[str, str]], out_dir: Path) -> Path:
    lines = [
        "# Operator Schedule",
        "",
        "| Participant | Order | First | Second |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        pid = str(row.get("participant_id") or "").strip()
        order = str(row.get("order") or "").strip()
        first = str(row.get("condition_first") or "").strip()
        second = str(row.get("condition_second") or "").strip()
        lines.append(f"| `{pid}` | `{order}` | `{first}` | `{second}` |")
    path = out_dir / "_operator_schedule.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    args = _parse_args()
    assignment_path = Path(args.assignment)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _read_assignment(assignment_path)
    manifest: dict[str, object] = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "assignment_csv": str(assignment_path),
        "packet_count": len(rows),
        "participants": [],
    }
    for row in rows:
        pid = str(row.get("participant_id") or "").strip()
        if not pid:
            continue
        packet_path = out_dir / f"{pid}.md"
        packet_path.write_text(_render_packet(row), encoding="utf-8")
        manifest["participants"].append(
            {
                "participant_id": pid,
                "order": str(row.get("order") or "").strip(),
                "packet": str(packet_path),
            }
        )

    operator_path = _write_operator_sheet(rows, out_dir)
    manifest["operator_schedule"] = str(operator_path)
    manifest_path = out_dir / "packet_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[user-study] packet_manifest=" + str(manifest_path))
    print("[user-study] operator_schedule=" + str(operator_path))
    print("[user-study] packet_dir=" + str(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
