import argparse
import os
import subprocess
import sys
from pathlib import Path


BASELINE_SUITES = [
    "daily_persona_probe",
    "open_evolution_eval",
    "transfer_probe",
    "natural_long_thread",
]

SUPPORTING_SUITES = [
    "selfhood_probe",
    "behavior_layer_probe",
    "dialogue_mode_counterpart_probe",
    "behavior_agenda_probe",
    "behavior_queue_probe",
    "behavior_queue_conflict_probe",
    "agenda_conflict_probe",
    "proactive_checkin_probe",
    "counterpart_assessment_probe",
    "scheduled_life_probe",
    "commitment_life_probe",
    "commitment_maturity_probe",
    "relationship_life_timing_probe",
    "self_activity_probe",
    "self_activity_maturity_probe",
    "perception_probe",
    "perception_appraisal_probe",
]


def _build_commands(*, local_only: bool, include_subjective: bool, include_supporting: bool) -> list[list[str]]:
    commands: list[list[str]] = []
    suite_names = list(BASELINE_SUITES)
    if include_supporting:
        suite_names.extend(SUPPORTING_SUITES)
    for suite in suite_names:
        cmd = [sys.executable, "evals/run_langsmith_evals.py"]
        if local_only:
            cmd.append("--local-only")
        cmd.extend(["--suite", suite])
        commands.append(cmd)
    if include_subjective:
        commands.append([sys.executable, "evals/run_subjective_review_pack.py"])
    return commands


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the current canonical Amadeus-K evaluation baseline.")
    parser.add_argument(
        "--include-subjective",
        action="store_true",
        help="Also run the current subjective review pack after the scripted baseline suites.",
    )
    parser.add_argument(
        "--with-langsmith",
        action="store_true",
        help="Upload tracing and results to LangSmith instead of forcing local-only mode.",
    )
    parser.add_argument(
        "--include-supporting",
        action="store_true",
        help="Also run the last-known green supporting behavior/perception/selfhood suites.",
    )
    parser.add_argument(
        "--respect-env",
        action="store_true",
        help="Do not override tracing/TTS environment variables.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    if not args.respect_env:
        env.setdefault("LANGSMITH_TRACING", "false")
        env.setdefault("LANGCHAIN_TRACING_V2", "false")
        env.setdefault("AMADEUS_TTS_ENABLED", "0")

    commands = _build_commands(
        local_only=not args.with_langsmith,
        include_subjective=args.include_subjective,
        include_supporting=args.include_supporting,
    )
    print(f"[baseline] cwd={repo_root}")
    print(f"[baseline] suites={', '.join(BASELINE_SUITES)}")
    if args.include_supporting:
        print(f"[baseline] supporting={', '.join(SUPPORTING_SUITES)}")
    if args.include_subjective:
        print("[baseline] subjective_review=on")
    if not args.respect_env:
        print(
            "[baseline] env overrides: "
            f"LANGSMITH_TRACING={env.get('LANGSMITH_TRACING')} "
            f"LANGCHAIN_TRACING_V2={env.get('LANGCHAIN_TRACING_V2')} "
            f"AMADEUS_TTS_ENABLED={env.get('AMADEUS_TTS_ENABLED')}"
        )

    for index, command in enumerate(commands, start=1):
        rendered = " ".join(command)
        print(f"\n[baseline {index}/{len(commands)}] {rendered}")
        completed = subprocess.run(command, cwd=repo_root, env=env)
        if completed.returncode != 0:
            print(f"[baseline] failed at step {index} with exit code {completed.returncode}")
            return completed.returncode
    print("\n[baseline] completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
