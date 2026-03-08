from __future__ import annotations

import argparse
import csv
import json
import random
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = PROJECT_ROOT / "user_study" / "raw"
SCENARIOS = [
    "science_qa",
    "worldline_recall",
    "relationship_repair",
    "external_retrieval",
    "bargein_recovery",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare balanced user-study raw sheets for Amadeus-K.")
    parser.add_argument("--participants", type=int, default=16, help="Number of participants to generate.")
    parser.add_argument("--seed", type=int, default=20260307, help="Random seed for assignment shuffling.")
    parser.add_argument("--out-dir", default=str(DEFAULT_RAW_DIR), help="Output directory for raw csv files.")
    parser.add_argument("--prefix", default="P", help="Participant ID prefix.")
    return parser.parse_args()


def _participant_ids(prefix: str, count: int) -> list[str]:
    width = max(2, len(str(count)))
    return [f"{prefix}{idx:0{width}d}" for idx in range(1, count + 1)]


def _balanced_orders(count: int, rng: random.Random) -> list[str]:
    half = count // 2
    orders = ["AB"] * half + ["BA"] * (count - half)
    rng.shuffle(orders)
    return orders


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _assignment_rows(participants: list[str], orders: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for pid, order in zip(participants, orders):
        first, second = tuple(order)
        rows.append(
            {
                "participant_id": pid,
                "order": order,
                "condition_first": first,
                "condition_second": second,
                "familiar_with_ip": "",
                "notes": "",
            }
        )
    return rows


def _questionnaire_rows(participants: list[str], orders: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for pid, order in zip(participants, orders):
        for cond in order:
            rows.append(
                {
                    "participant_id": pid,
                    "condition": cond,
                    "task_block": "core_tasks",
                    "role_fidelity": "",
                    "continuity": "",
                    "trustworthiness": "",
                    "companionship": "",
                    "controllability": "",
                    "overall_score": "",
                    "free_comment": "",
                }
            )
    return rows


def _session_log_rows(participants: list[str], orders: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for pid, order in zip(participants, orders):
        for cond in order:
            thread_prefix = f"{pid.lower()}-{cond.lower()}"
            for scenario_id in SCENARIOS:
                rows.append(
                    {
                        "participant_id": pid,
                        "condition": cond,
                        "thread_id": f"{thread_prefix}-{scenario_id}",
                        "scenario_id": scenario_id,
                        "start_time": "",
                        "end_time": "",
                        "completed": "",
                        "notable_issue": "",
                        "notes": "",
                    }
                )
    return rows


def _manifest(participants: list[str], orders: list[str]) -> dict[str, object]:
    ab = sum(1 for item in orders if item == "AB")
    ba = sum(1 for item in orders if item == "BA")
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "participants": participants,
        "participant_count": len(participants),
        "orders": {"AB": ab, "BA": ba},
        "scenarios": list(SCENARIOS),
    }


def main() -> int:
    args = _parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    participants = _participant_ids(str(args.prefix), int(args.participants))
    orders = _balanced_orders(len(participants), rng)

    assignment_path = out_dir / "assignment.csv"
    questionnaire_path = out_dir / "questionnaire.csv"
    session_log_path = out_dir / "session_log.csv"
    manifest_path = out_dir / "study_manifest.json"

    _write_csv(
        assignment_path,
        _assignment_rows(participants, orders),
        ["participant_id", "order", "condition_first", "condition_second", "familiar_with_ip", "notes"],
    )
    _write_csv(
        questionnaire_path,
        _questionnaire_rows(participants, orders),
        [
            "participant_id",
            "condition",
            "task_block",
            "role_fidelity",
            "continuity",
            "trustworthiness",
            "companionship",
            "controllability",
            "overall_score",
            "free_comment",
        ],
    )
    _write_csv(
        session_log_path,
        _session_log_rows(participants, orders),
        [
            "participant_id",
            "condition",
            "thread_id",
            "scenario_id",
            "start_time",
            "end_time",
            "completed",
            "notable_issue",
            "notes",
        ],
    )
    manifest_path.write_text(json.dumps(_manifest(participants, orders), ensure_ascii=False, indent=2), encoding="utf-8")

    print("[user-study] assignment_csv=" + str(assignment_path))
    print("[user-study] questionnaire_csv=" + str(questionnaire_path))
    print("[user-study] session_log_csv=" + str(session_log_path))
    print("[user-study] manifest_json=" + str(manifest_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
