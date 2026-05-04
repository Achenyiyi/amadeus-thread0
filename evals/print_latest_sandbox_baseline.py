from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "evals" / "reports"

_READY_STATUSES = {
    "sandbox_embodied_execution_phase2_ready",
    "sandbox_embodied_execution_phase1_ready",
}
_REPORT_PATTERNS = (
    "sandbox-phase2-audit-*.json",
    "sandbox-embodied-execution-audit-*.json",
)


def _load_payload(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _select_authoritative_report(reports: list[Path]) -> Path:
    latest = reports[-1]
    for path in reversed(reports):
        payload = _load_payload(path)
        if str(payload.get("overall_status") or "") == "passed" and str(payload.get("readiness_status") or "") in _READY_STATUSES:
            return path
    return latest


def _sandbox_reports(report_dir: Path = REPORT_DIR) -> list[Path]:
    reports: list[Path] = []
    for pattern in _REPORT_PATTERNS:
        reports.extend(Path(report_dir).glob(pattern))
    return sorted(set(reports))


def main() -> None:
    reports = _sandbox_reports()
    if not reports:
        raise SystemExit("No sandbox embodied execution audit reports found.")
    path = _select_authoritative_report(reports)
    payload = _load_payload(path)
    md_path = path.with_suffix(".md")
    print(f"[sandbox-embodied-execution] json={path}")
    print(f"[sandbox-embodied-execution] md={md_path}")
    print(f"[sandbox-embodied-execution] overall_status={payload.get('overall_status', '')}")
    print(f"[sandbox-embodied-execution] readiness={payload.get('readiness_status', '')}")


if __name__ == "__main__":
    main()
