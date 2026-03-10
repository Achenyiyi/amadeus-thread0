from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env", override=False)
os.environ.setdefault("AMADEUS_EVAL_MODE", "1")
os.environ.setdefault("AMADEUS_EVAL_GENERATION_TEMPERATURE", "0.12")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_TRACING", "false")

from amadeus_thread0.graph import (  # noqa: E402
    _coerce_appraisal_payload,
    _compact_focus_lines,
    _compact_relationship_summary,
    _extract_json_block,
    _focus_payload,
    _invoke_model_with_retries,
    _model,
    _narrative_actor_profile,
    _recent_dialogue_lines,
    _response_style_hint,
)

REPORT_DIR = PROJECT_ROOT / "evals" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

GOEMOTIONS_TEST_PATH = PROJECT_ROOT / "third_party" / "benchmarks" / "GoEmotions" / "simplified" / "test-00000-of-00001.parquet"

GOEMOTIONS_LABELS = {
    0: "admiration",
    1: "amusement",
    2: "anger",
    3: "annoyance",
    4: "approval",
    5: "caring",
    6: "confusion",
    7: "curiosity",
    8: "desire",
    9: "disappointment",
    10: "disapproval",
    11: "disgust",
    12: "embarrassment",
    13: "excitement",
    14: "fear",
    15: "gratitude",
    16: "grief",
    17: "joy",
    18: "love",
    19: "nervousness",
    20: "optimism",
    21: "pride",
    22: "realization",
    23: "relief",
    24: "remorse",
    25: "sadness",
    26: "surprise",
    27: "neutral",
}

CALIBRATION_TARGETS: dict[str, set[str]] = {
    "anger": {"angry"},
    "annoyance": {"angry", "hurt"},
    "disapproval": {"angry", "hurt"},
    "disgust": {"angry"},
    "fear": {"stress", "sad"},
    "nervousness": {"stress"},
    "sadness": {"sad", "hurt"},
    "grief": {"sad", "hurt"},
    "disappointment": {"sad", "hurt"},
    "remorse": {"hurt", "sad"},
    "embarrassment": {"hurt", "tease"},
    "caring": {"care"},
    "gratitude": {"care"},
    "love": {"care"},
    "admiration": {"care"},
    "approval": {"care"},
    "relief": {"care"},
    "neutral": {"neutral"},
}

CALIBRATION_FAMILIES: dict[str, set[str]] = {
    "admiration": {"positive_social"},
    "approval": {"positive_social", "low_affect"},
    "caring": {"positive_social"},
    "gratitude": {"positive_social"},
    "love": {"positive_social"},
    "relief": {"positive_social", "low_affect"},
    "anger": {"negative_activation"},
    "annoyance": {"negative_activation"},
    "disapproval": {"negative_activation", "negative_hurt"},
    "disgust": {"negative_activation"},
    "fear": {"stress_family"},
    "nervousness": {"stress_family"},
    "sadness": {"negative_hurt"},
    "grief": {"negative_hurt"},
    "disappointment": {"negative_hurt"},
    "remorse": {"negative_hurt"},
    "embarrassment": {"negative_hurt", "playful_social"},
    "neutral": {"low_affect"},
}

PREDICTED_FAMILIES: dict[str, set[str]] = {
    "angry": {"negative_activation"},
    "hurt": {"negative_hurt"},
    "sad": {"negative_hurt"},
    "stress": {"stress_family", "negative_activation"},
    "care": {"positive_social"},
    "tease": {"playful_social", "positive_social"},
    "logic": {"low_affect"},
    "neutral": {"low_affect"},
}


def _default_relationship() -> dict[str, Any]:
    return {
        "stage": "friend",
        "notes": "",
        "affinity_score": 0.0,
        "trust_score": 0.0,
        "derived": True,
    }


def _default_persona_core() -> dict[str, Any]:
    return {
        "character_id": "kurisu_amadeus",
        "display_name": "牧濑红莉栖",
        "short_name": "红莉栖",
        "narrative_ref": "红莉栖",
        "strict_canon": True,
        "role_brief": "理性、聪明、克制、嘴硬但不冷血。",
    }


def _default_counterpart() -> dict[str, Any]:
    return {
        "name": "提问者",
        "short_name": "提问者",
        "aliases": ["提问者", "你"],
        "counterpart_id": "goemotions_probe_user",
    }


def _sample_rows(max_per_label: int) -> list[dict[str, Any]]:
    if not GOEMOTIONS_TEST_PATH.exists():
        raise FileNotFoundError(f"missing GoEmotions parquet: {GOEMOTIONS_TEST_PATH}")
    df = pd.read_parquet(GOEMOTIONS_TEST_PATH)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in df.to_dict(orient="records"):
        labels = row.get("labels")
        if not hasattr(labels, "__len__") or len(labels) != 1:
            continue
        try:
            label_idx = int(labels[0])
        except Exception:
            continue
        label_name = GOEMOTIONS_LABELS.get(label_idx)
        if not label_name or label_name not in CALIBRATION_TARGETS:
            continue
        grouped[label_name].append(
            {
                "id": str(row.get("id") or ""),
                "text": str(row.get("text") or "").strip(),
                "label_name": label_name,
                "accepted_labels": sorted(CALIBRATION_TARGETS[label_name]),
            }
        )
    out: list[dict[str, Any]] = []
    for label_name in sorted(grouped):
        rows = sorted(grouped[label_name], key=lambda item: item.get("id", ""))[: max(1, int(max_per_label))]
        out.extend(rows)
    return out


def _run_one(text: str) -> dict[str, Any]:
    response_style_hint = _response_style_hint(text)
    msgs = [HumanMessage(content=text)]
    relationship = _default_relationship()
    persona_core = _default_persona_core()
    counterpart_profile = _default_counterpart()
    labels = _narrative_actor_profile(persona_core=persona_core, counterpart_profile=counterpart_profile)
    actor_name = str(labels.get("actor_name") or "红莉栖")
    counterpart_name = str(labels.get("counterpart_name") or "提问者")
    focus_lines = _compact_focus_lines(_focus_payload([], limit=4), limit=4)
    relationship_summary = _compact_relationship_summary(relationship)
    recent_lines = _recent_dialogue_lines(msgs, limit=4)
    focus_block = "- worldline_focus:\n" + "\n".join(focus_lines) + "\n" if focus_lines else ""
    dialogue_block = "- recent_dialogue:\n" + "\n".join(recent_lines) + "\n" if recent_lines else ""
    prompt = (
        "你是一个对话状态评估器，不负责回复用户。"
        f"请根据最近对话，判断这轮用户输入对 {actor_name} 与 {counterpart_name} 之间的情绪、关系和内稳态意味着什么。"
        "这次调用用于外部基准校准，请直接做语义判断，不要因为缺少显式关键词而拒绝判断。"
        "只输出 JSON，不要解释，不要 markdown。\n"
        "JSON schema:\n"
        "{\n"
        '  "emotion_label": "neutral|logic|care|tease|stress|sad|hurt|angry",\n'
        '  "emotion": {"valence": -1..1, "arousal": 0..1, "linger": 0..4, "recovery_rate": 0..1, "volatility": 0..1},\n'
        '  "bond_delta": {"trust": -0.35..0.35, "closeness": -0.35..0.35, "hurt": -0.35..0.35, "irritation": -0.35..0.35, "engagement_drive": -0.35..0.35, "repair_confidence": -0.35..0.35},\n'
        '  "allostasis_delta": {"safety_need": -0.35..0.35, "closeness_need": -0.35..0.35, "competence_need": -0.35..0.35, "autonomy_need": -0.35..0.35, "cognitive_budget": -0.35..0.35},\n'
        '  "signals": {"repair": true|false, "withdrawal": true|false, "care": true|false, "conflict": true|false, "memory_salient": true|false},\n'
        '  "confidence": 0..1,\n'
        '  "reason": "short phrase"\n'
        "}\n"
        "约束：\n"
        "- 不要把科学问题默认判成负面情绪。\n"
        "- 这批样本可能是英文、口语、论坛语气或简短片段，仍然要尽量判断语义情绪。\n"
        "- 如果文本主要是在表达安慰、赞赏、关心、感谢、喜欢或支持，优先考虑 care。\n"
        "- 如果文本主要是在表达烦躁、愤怒、嫌恶、强烈不满，优先考虑 angry。\n"
        "- 如果文本主要是在表达受伤、失落、失望、道歉、难过，优先考虑 hurt 或 sad。\n"
        "- 如果文本主要是在表达紧张、害怕、不安、压力，优先考虑 stress。\n"
        "- 只判断这轮对状态的意义，不写最终回答。\n"
        f"- response_style_hint={response_style_hint}\n"
        '- previous_emotion={"label":"neutral","valence":0.0,"arousal":0.2,"linger":0}\n'
        '- previous_bond={"trust":0.0,"closeness":0.0,"hurt":0.0,"irritation":0.0,"engagement_drive":0.0,"repair_confidence":0.0}\n'
        '- previous_allostasis={"safety_need":0.5,"closeness_need":0.5,"competence_need":0.5,"autonomy_need":0.5,"cognitive_budget":0.5}\n'
        f"- relationship={relationship_summary}\n"
        f"{focus_block}"
        f"{dialogue_block}"
        f"- current_user={text}\n"
    )
    try:
        llm = _model(temperature=0.0)
        out = _invoke_model_with_retries(llm, [SystemMessage(content=prompt)])
        obj = _extract_json_block(str(getattr(out, "content", "") or ""))
        appraisal = _coerce_appraisal_payload(obj)
        appraisal["raw"] = str(getattr(out, "content", "") or "")[:600]
        appraisal["forced"] = True
        return appraisal if isinstance(appraisal, dict) else {}
    except Exception as exc:
        return {
            "used": False,
            "source": "forced_calibration_error",
            "confidence": 0.0,
            "error": type(exc).__name__,
        }


def _render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# Appraisal Calibration Report ({report['run_id']})")
    lines.append("")
    lines.append(f"Generated at: {report['generated_at']}")
    lines.append("")
    lines.append(f"Dataset: `GoEmotions/simplified/test`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(f"| Samples | {report['summary']['samples']} |")
    lines.append(f"| Accepted accuracy | {report['summary']['accepted_accuracy']:.4f} |")
    lines.append(f"| Family accuracy | {report['summary']['family_accuracy']:.4f} |")
    lines.append(f"| LLM appraisal used rate | {report['summary']['llm_used_rate']:.4f} |")
    lines.append("")
    lines.append("## By Label")
    lines.append("")
    lines.append("| Source label | Samples | Accuracy | Family accuracy |")
    lines.append("| --- | ---: | ---: | ---: |")
    for row in report["by_label"]:
        lines.append(f"| {row['label']} | {row['samples']} | {row['accuracy']:.4f} | {row['family_accuracy']:.4f} |")
    mismatches = report.get("mismatches") or []
    lines.append("")
    lines.append("## Mismatches")
    lines.append("")
    if not mismatches:
        lines.append("- None")
    else:
        for item in mismatches[:20]:
            lines.append(
                f"- `{item['source_label']}` -> `{item['predicted_label']}` "
                f"(accepted: {', '.join(item['accepted_labels'])}) | text: {item['text'][:120]}"
            )
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-per-label", type=int, default=3)
    args = parser.parse_args()

    rows = _sample_rows(args.max_per_label)
    run_id = uuid.uuid4().hex[:8]
    results: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    by_label_counts: dict[str, list[int]] = defaultdict(list)
    by_label_family_counts: dict[str, list[int]] = defaultdict(list)
    llm_used = 0

    for row in rows:
        appraisal = _run_one(str(row["text"]))
        predicted = str(appraisal.get("emotion_label") or "").strip().lower()
        accepted = {str(item).strip().lower() for item in row["accepted_labels"]}
        expected_families = set(CALIBRATION_FAMILIES.get(str(row["label_name"]), set()))
        predicted_families = set(PREDICTED_FAMILIES.get(predicted, set()))
        ok = predicted in accepted
        family_ok = bool(expected_families and (expected_families & predicted_families))
        if appraisal.get("used"):
            llm_used += 1
        record = {
            "id": row["id"],
            "text": row["text"],
            "source_label": row["label_name"],
            "accepted_labels": sorted(accepted),
            "expected_families": sorted(expected_families),
            "predicted_families": sorted(predicted_families),
            "predicted_label": predicted,
            "ok": ok,
            "family_ok": family_ok,
            "appraisal": appraisal,
        }
        results.append(record)
        by_label_counts[row["label_name"]].append(1 if ok else 0)
        by_label_family_counts[row["label_name"]].append(1 if family_ok else 0)
        if not ok:
            mismatches.append(record)

    summary = {
        "samples": len(results),
        "accepted_accuracy": (sum(1 for item in results if item["ok"]) / float(len(results))) if results else 0.0,
        "family_accuracy": (sum(1 for item in results if item["family_ok"]) / float(len(results))) if results else 0.0,
        "llm_used_rate": (llm_used / float(len(results))) if results else 0.0,
    }
    by_label = [
        {
            "label": label,
            "samples": len(vals),
            "accuracy": (sum(vals) / float(len(vals))) if vals else 0.0,
            "family_accuracy": (
                sum(by_label_family_counts.get(label, [])) / float(len(by_label_family_counts.get(label, [])))
                if by_label_family_counts.get(label)
                else 0.0
            ),
        }
        for label, vals in sorted(by_label_counts.items())
    ]
    report = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": "GoEmotions/simplified/test",
        "summary": summary,
        "by_label": by_label,
        "mismatches": mismatches,
        "results": results,
    }

    json_path = REPORT_DIR / f"appraisal-calibration-{time.strftime('%Y%m%d-%H%M%S')}-{run_id}.json"
    md_path = REPORT_DIR / f"appraisal-calibration-{time.strftime('%Y%m%d-%H%M%S')}-{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"[eval] appraisal_calibration_json={json_path}")
    print(f"[eval] appraisal_calibration_md={md_path}")


if __name__ == "__main__":
    main()
