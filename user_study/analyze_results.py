from __future__ import annotations

import argparse
import csv
import re
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = PROJECT_ROOT / "user_study" / "raw"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "user_study" / "results"
DEFAULT_THESIS_EXPORT_DIR = DEFAULT_RESULTS_DIR / "thesis_exports"
METRICS = [
    "role_fidelity",
    "continuity",
    "trustworthiness",
    "companionship",
    "controllability",
    "overall_score",
]
COMMENT_STOPWORDS = {
    "这个",
    "那个",
    "就是",
    "感觉",
    "觉得",
    "比较",
    "有点",
    "还是",
    "因为",
    "所以",
    "如果",
    "然后",
    "但是",
    "而且",
    "我们",
    "你们",
    "他们",
    "一个",
    "不是",
    "可以",
    "版本",
    "系统",
    "角色",
    "对话",
    "回复",
    "回答",
    "真的",
    "有些",
    "非常",
    "thing",
    "really",
    "very",
}
METRIC_LABELS = {
    "role_fidelity": "角色还原度",
    "continuity": "连续性",
    "trustworthiness": "可信度",
    "companionship": "陪伴感",
    "controllability": "可控性",
    "overall_score": "总体评分",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize Amadeus-K user-study questionnaire and session logs.")
    parser.add_argument("--questionnaire", default=str(DEFAULT_RAW_DIR / "questionnaire.csv"))
    parser.add_argument("--session-log", default=str(DEFAULT_RAW_DIR / "session_log.csv"))
    parser.add_argument("--assignment", default=str(DEFAULT_RAW_DIR / "assignment.csv"))
    parser.add_argument("--out-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--thesis-out-dir", default=str(DEFAULT_THESIS_EXPORT_DIR))
    parser.add_argument("--system-a-label", default="当前稳定版")
    parser.add_argument("--system-b-label", default="退化版")
    return parser.parse_args()


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _to_float(value: Any) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        return float(text)
    except Exception:
        return None


def _mean_std(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return float(values[0]), 0.0
    return float(statistics.mean(values)), float(statistics.stdev(values))


def _paired_arrays(rows: list[dict[str, str]], metric: str) -> tuple[list[float], list[float]]:
    buckets: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        pid = str(row.get("participant_id") or "").strip()
        cond = str(row.get("condition") or "").strip()
        value = _to_float(row.get(metric))
        if not pid or cond not in {"A", "B"} or value is None:
            continue
        buckets[pid][cond] = value
    a_vals: list[float] = []
    b_vals: list[float] = []
    for pid, pair in buckets.items():
        if "A" in pair and "B" in pair:
            a_vals.append(pair["A"])
            b_vals.append(pair["B"])
    return a_vals, b_vals


def _paired_stats(a_vals: list[float], b_vals: list[float]) -> dict[str, Any]:
    if not a_vals or not b_vals or len(a_vals) != len(b_vals):
        return {"n": 0, "mean_delta": None, "test": "", "p_value": None}

    deltas = [a - b for a, b in zip(a_vals, b_vals)]
    mean_delta = statistics.mean(deltas)
    result = {
        "n": len(deltas),
        "mean_delta": round(float(mean_delta), 4),
        "test": "",
        "p_value": None,
    }
    try:
        from scipy.stats import shapiro, ttest_rel, wilcoxon  # type: ignore

        normal = False
        if len(deltas) >= 3:
            try:
                normal = bool(shapiro(deltas).pvalue >= 0.05)
            except Exception:
                normal = False
        if normal:
            stat = ttest_rel(a_vals, b_vals, nan_policy="omit")
            result["test"] = "paired_t_test"
            result["p_value"] = round(float(stat.pvalue), 6)
        else:
            stat = wilcoxon(a_vals, b_vals)
            result["test"] = "wilcoxon"
            result["p_value"] = round(float(stat.pvalue), 6)
    except Exception:
        pass
    return result


def _summarize_questionnaire(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_condition: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        cond = str(row.get("condition") or "").strip()
        if not cond:
            continue
        for metric in METRICS:
            value = _to_float(row.get(metric))
            if value is not None:
                by_condition[cond][metric].append(value)

    condition_rows: list[dict[str, Any]] = []
    for cond in sorted(by_condition.keys()):
        for metric in METRICS:
            mean, std = _mean_std(by_condition[cond].get(metric, []))
            condition_rows.append(
                {
                    "metric": metric,
                    "condition": cond,
                    "n": len(by_condition[cond].get(metric, [])),
                    "mean": round(mean, 4) if mean is not None else None,
                    "std": round(std, 4) if std is not None else None,
                }
            )

    paired_rows: list[dict[str, Any]] = []
    for metric in METRICS:
        a_vals, b_vals = _paired_arrays(rows, metric)
        stats = _paired_stats(a_vals, b_vals)
        paired_rows.append(
            {
                "metric": metric,
                "paired_n": stats["n"],
                "mean_delta_a_minus_b": stats["mean_delta"],
                "test": stats["test"],
                "p_value": stats["p_value"],
            }
        )
    return condition_rows, paired_rows


def _summarize_session_log(rows: list[dict[str, str]]) -> dict[str, Any]:
    completed = 0
    total = 0
    issue_counter: Counter[str] = Counter()
    for row in rows:
        total += 1
        completed_flag = str(row.get("completed") or "").strip().lower()
        if completed_flag in {"1", "true", "yes", "y"}:
            completed += 1
        issue = str(row.get("notable_issue") or "").strip()
        if issue:
            issue_counter[issue] += 1
    return {
        "rows": total,
        "completed": completed,
        "completion_rate": round(completed / total, 4) if total else None,
        "top_issues": issue_counter.most_common(10),
    }


def _summarize_assignment(rows: list[dict[str, str]]) -> dict[str, Any]:
    orders = Counter(str(row.get("order") or "").strip() for row in rows if str(row.get("order") or "").strip())
    familiar = Counter(str(row.get("familiar_with_ip") or "").strip() for row in rows if str(row.get("familiar_with_ip") or "").strip())
    return {
        "rows": len(rows),
        "orders": dict(orders),
        "familiar_with_ip": dict(familiar),
    }


def _tokenize_comment(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z_-]{2,}|[\u4e00-\u9fff]{2,}", str(text or ""))
    out: list[str] = []
    for token in tokens:
        norm = token.strip().lower()
        if not norm or norm in COMMENT_STOPWORDS:
            continue
        out.append(norm)
    return out


def _summarize_comments(questionnaire_rows: list[dict[str, str]], session_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for row in questionnaire_rows:
        for field in ("free_comment",):
            counter.update(_tokenize_comment(str(row.get(field) or "")))
    for row in session_rows:
        for field in ("notable_issue", "notes"):
            counter.update(_tokenize_comment(str(row.get(field) or "")))
    return [{"token": token, "count": count} for token, count in counter.most_common(20)]


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _build_markdown(
    *,
    questionnaire_rows: int,
    condition_rows: list[dict[str, Any]],
    paired_rows: list[dict[str, Any]],
    session_summary: dict[str, Any],
    assignment_summary: dict[str, Any],
    comment_rows: list[dict[str, Any]],
) -> str:
    lines = [
        "# User Study Summary",
        "",
        f"- Generated: `{time.strftime('%Y-%m-%d %H:%M:%S')}`",
        f"- Questionnaire rows: `{questionnaire_rows}`",
        "",
        "## Condition Means",
        "",
        "| Metric | Condition | N | Mean | Std |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in condition_rows:
        lines.append(
            f"| `{row['metric']}` | `{row['condition']}` | `{row['n']}` | `{row['mean'] if row['mean'] is not None else '-'}` | `{row['std'] if row['std'] is not None else '-'}` |"
        )

    lines.extend([
        "",
        "## Paired Comparison (A - B)",
        "",
        "| Metric | Paired N | Mean Delta | Test | P Value |",
        "| --- | ---: | ---: | --- | ---: |",
    ])
    for row in paired_rows:
        lines.append(
            f"| `{row['metric']}` | `{row['paired_n']}` | `{row['mean_delta_a_minus_b'] if row['mean_delta_a_minus_b'] is not None else '-'}` | `{row['test'] or '-'}` | `{row['p_value'] if row['p_value'] is not None else '-'}` |"
        )

    lines.extend([
        "",
        "## Session Log",
        "",
        f"- Rows: `{session_summary.get('rows', 0)}`",
        f"- Completed: `{session_summary.get('completed', 0)}`",
        f"- Completion rate: `{session_summary.get('completion_rate', '-')}`",
        "",
        "Top issues:",
    ])
    issues = session_summary.get("top_issues") or []
    if not issues:
        lines.append("- None")
    else:
        for issue, count in issues:
            lines.append(f"- `{issue}`: `{count}`")

    lines.extend([
        "",
        "## Assignment Balance",
        "",
        f"- Rows: `{assignment_summary.get('rows', 0)}`",
        f"- Orders: `{assignment_summary.get('orders', {})}`",
        f"- Familiar with IP: `{assignment_summary.get('familiar_with_ip', {})}`",
        "",
        "## Open Feedback Tokens",
        "",
    ])
    if not comment_rows:
        lines.append("- None")
    else:
        for row in comment_rows:
            lines.append(f"- `{row['token']}`: `{row['count']}`")
    lines.append("")
    return "\n".join(lines)


def _pivot_condition_rows(condition_rows: list[dict[str, Any]], *, system_a_label: str, system_b_label: str) -> list[dict[str, Any]]:
    by_metric: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in condition_rows:
        metric = str(row.get("metric") or "")
        condition = str(row.get("condition") or "")
        by_metric[metric][condition] = row

    out: list[dict[str, Any]] = []
    for metric in METRICS:
        a_row = by_metric.get(metric, {}).get("A", {})
        b_row = by_metric.get(metric, {}).get("B", {})
        out.append(
            {
                "metric": metric,
                "metric_label": METRIC_LABELS.get(metric, metric),
                "system_a_label": system_a_label,
                "system_a_n": a_row.get("n"),
                "system_a_mean": a_row.get("mean"),
                "system_a_std": a_row.get("std"),
                "system_b_label": system_b_label,
                "system_b_n": b_row.get("n"),
                "system_b_mean": b_row.get("mean"),
                "system_b_std": b_row.get("std"),
            }
        )
    return out


def _build_thesis_paired_rows(
    paired_rows: list[dict[str, Any]],
    *,
    system_a_label: str,
    system_b_label: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in paired_rows:
        delta = _to_float(row.get("mean_delta_a_minus_b"))
        if delta is None:
            preferred = ""
        elif delta > 0:
            preferred = system_a_label
        elif delta < 0:
            preferred = system_b_label
        else:
            preferred = "tie"
        metric = str(row.get("metric") or "")
        out.append(
            {
                "metric": metric,
                "metric_label": METRIC_LABELS.get(metric, metric),
                "paired_n": row.get("paired_n"),
                "mean_delta_a_minus_b": row.get("mean_delta_a_minus_b"),
                "preferred_condition": preferred,
                "test": row.get("test"),
                "p_value": row.get("p_value"),
            }
        )
    return out


def _build_thesis_condition_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Thesis User Study Condition Summary",
        "",
        "This file is a thesis-ready condition summary table for Section 4.8.",
        "",
        "| 指标 | 系统 A | A 样本数 | A 平均分 | A 标准差 | 系统 B | B 样本数 | B 平均分 | B 标准差 |",
        "| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {metric_label} | {system_a_label} | {system_a_n} | {system_a_mean} | {system_a_std} | {system_b_label} | {system_b_n} | {system_b_mean} | {system_b_std} |".format(
                metric_label=row["metric_label"],
                system_a_label=row["system_a_label"],
                system_a_n=row["system_a_n"] if row["system_a_n"] is not None else "-",
                system_a_mean=row["system_a_mean"] if row["system_a_mean"] is not None else "-",
                system_a_std=row["system_a_std"] if row["system_a_std"] is not None else "-",
                system_b_label=row["system_b_label"],
                system_b_n=row["system_b_n"] if row["system_b_n"] is not None else "-",
                system_b_mean=row["system_b_mean"] if row["system_b_mean"] is not None else "-",
                system_b_std=row["system_b_std"] if row["system_b_std"] is not None else "-",
            )
        )
    lines.append("")
    return "\n".join(lines)


def _build_thesis_paired_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Thesis User Study Paired Summary",
        "",
        "This file is a thesis-ready paired comparison table for Section 4.8.",
        "",
        "| 指标 | 配对样本数 | A-B 平均差 | 偏优系统 | 统计检验 | p 值 |",
        "| --- | ---: | ---: | --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {metric_label} | {paired_n} | {delta} | {preferred} | {test} | {p_value} |".format(
                metric_label=row["metric_label"],
                paired_n=row["paired_n"] if row["paired_n"] is not None else "-",
                delta=row["mean_delta_a_minus_b"] if row["mean_delta_a_minus_b"] is not None else "-",
                preferred=row["preferred_condition"] or "-",
                test=row["test"] or "-",
                p_value=row["p_value"] if row["p_value"] is not None else "-",
            )
        )
    lines.append("")
    return "\n".join(lines)


def _build_thesis_insert_markdown(
    *,
    condition_rows: list[dict[str, Any]],
    paired_rows: list[dict[str, Any]],
    session_summary: dict[str, Any],
    assignment_summary: dict[str, Any],
    comment_rows: list[dict[str, Any]],
    system_a_label: str,
    system_b_label: str,
) -> str:
    top_tokens = "、".join(row["token"] for row in comment_rows[:5]) if comment_rows else "无明显高频反馈"
    strongest_metric = None
    strongest_delta = None
    for row in paired_rows:
        delta = _to_float(row.get("mean_delta_a_minus_b"))
        if delta is None:
            continue
        if strongest_delta is None or abs(delta) > abs(strongest_delta):
            strongest_delta = delta
            strongest_metric = row["metric_label"]
    strongest_line = "暂无配对差异数据。"
    if strongest_metric is not None and strongest_delta is not None:
        preferred = system_a_label if strongest_delta > 0 else system_b_label if strongest_delta < 0 else "两者持平"
        strongest_line = f"当前配对差异最大的维度是“{strongest_metric}”，平均差值为 {strongest_delta:.4f}，偏优系统为 {preferred}。"

    return "\n".join(
        [
            "# CH4 User Study Insert Draft",
            "",
            "以下内容用于直接回填到第四章 4.8 节，在获得真实用户研究数据后替换原有“设计说明”段落。",
            "",
            "## 建议插入段落",
            "",
            f"本研究共纳入 `{assignment_summary.get('rows', 0)}` 名参与者，条件顺序分配为 `{assignment_summary.get('orders', {})}`。会话记录共 `{session_summary.get('rows', 0)}` 条，其中完成率为 `{session_summary.get('completion_rate', '-')}`。参与者分别体验 `{system_a_label}` 与 `{system_b_label}`，并围绕角色还原度、连续性、可信度、陪伴感、可控性和总体评分进行量表评价。",
            "",
            strongest_line,
            "",
            f"开放式反馈中出现频率较高的关键词包括：{top_tokens}。这些反馈可与自动评测中的人格一致性、世界线连续性和可控性结论交叉分析，用于解释系统的主观体验差异。",
            "",
            "## 插图与表格引用顺序",
            "",
            "1. 先插入 `thesis-user-study-condition-*.md/csv` 对应的条件均值表",
            "2. 再插入 `thesis-user-study-paired-*.md/csv` 对应的配对比较表",
            "3. 最后用本段文字总结主观体验结论，并与自动评测结果对应",
            "",
        ]
    )


def main() -> int:
    args = _parse_args()
    questionnaire_path = Path(args.questionnaire)
    session_log_path = Path(args.session_log)
    assignment_path = Path(args.assignment)
    out_dir = Path(args.out_dir)
    thesis_out_dir = Path(args.thesis_out_dir) if str(args.thesis_out_dir or "").strip() else None
    out_dir.mkdir(parents=True, exist_ok=True)

    questionnaire_rows = _load_csv(questionnaire_path)
    session_rows = _load_csv(session_log_path)
    assignment_rows = _load_csv(assignment_path)

    condition_rows, paired_rows = _summarize_questionnaire(questionnaire_rows)
    session_summary = _summarize_session_log(session_rows)
    assignment_summary = _summarize_assignment(assignment_rows)
    comment_rows = _summarize_comments(questionnaire_rows, session_rows)

    ts = time.strftime("%Y%m%d-%H%M%S")
    condition_csv = out_dir / f"summary-condition-{ts}.csv"
    paired_csv = out_dir / f"summary-paired-{ts}.csv"
    comment_csv = out_dir / f"summary-comment-top-{ts}.csv"
    md_path = out_dir / f"summary-report-{ts}.md"

    _write_csv(condition_csv, condition_rows, ["metric", "condition", "n", "mean", "std"])
    _write_csv(paired_csv, paired_rows, ["metric", "paired_n", "mean_delta_a_minus_b", "test", "p_value"])
    _write_csv(comment_csv, comment_rows, ["token", "count"])
    md_path.write_text(
        _build_markdown(
            questionnaire_rows=len(questionnaire_rows),
            condition_rows=condition_rows,
            paired_rows=paired_rows,
            session_summary=session_summary,
            assignment_summary=assignment_summary,
            comment_rows=comment_rows,
        ),
        encoding="utf-8",
    )

    thesis_condition_csv = None
    thesis_paired_csv = None
    thesis_insert_md = None
    if thesis_out_dir is not None:
        thesis_out_dir.mkdir(parents=True, exist_ok=True)
        thesis_condition_rows = _pivot_condition_rows(
            condition_rows,
            system_a_label=args.system_a_label,
            system_b_label=args.system_b_label,
        )
        thesis_paired_rows = _build_thesis_paired_rows(
            paired_rows,
            system_a_label=args.system_a_label,
            system_b_label=args.system_b_label,
        )
        thesis_condition_csv = thesis_out_dir / f"thesis-user-study-condition-{ts}.csv"
        thesis_condition_md = thesis_out_dir / f"thesis-user-study-condition-{ts}.md"
        thesis_paired_csv = thesis_out_dir / f"thesis-user-study-paired-{ts}.csv"
        thesis_paired_md = thesis_out_dir / f"thesis-user-study-paired-{ts}.md"
        thesis_insert_md = thesis_out_dir / f"ch4-user-study-insert-{ts}.md"
        _write_csv(
            thesis_condition_csv,
            thesis_condition_rows,
            [
                "metric",
                "metric_label",
                "system_a_label",
                "system_a_n",
                "system_a_mean",
                "system_a_std",
                "system_b_label",
                "system_b_n",
                "system_b_mean",
                "system_b_std",
            ],
        )
        thesis_condition_md.write_text(_build_thesis_condition_markdown(thesis_condition_rows), encoding="utf-8")
        _write_csv(
            thesis_paired_csv,
            thesis_paired_rows,
            ["metric", "metric_label", "paired_n", "mean_delta_a_minus_b", "preferred_condition", "test", "p_value"],
        )
        thesis_paired_md.write_text(_build_thesis_paired_markdown(thesis_paired_rows), encoding="utf-8")
        thesis_insert_md.write_text(
            _build_thesis_insert_markdown(
                condition_rows=thesis_condition_rows,
                paired_rows=thesis_paired_rows,
                session_summary=session_summary,
                assignment_summary=assignment_summary,
                comment_rows=comment_rows,
                system_a_label=args.system_a_label,
                system_b_label=args.system_b_label,
            ),
            encoding="utf-8",
        )

    print("[user-study] condition_csv=" + str(condition_csv))
    print("[user-study] paired_csv=" + str(paired_csv))
    print("[user-study] comment_csv=" + str(comment_csv))
    print("[user-study] report_md=" + str(md_path))
    if thesis_condition_csv is not None:
        print("[user-study] thesis_condition_csv=" + str(thesis_condition_csv))
    if thesis_paired_csv is not None:
        print("[user-study] thesis_paired_csv=" + str(thesis_paired_csv))
    if thesis_insert_md is not None:
        print("[user-study] thesis_insert_md=" + str(thesis_insert_md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
