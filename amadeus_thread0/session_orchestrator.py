from __future__ import annotations

from typing import Any


def emotion_to_tts_profile(label: str) -> dict[str, float]:
    l = str(label or "neutral").strip().lower()
    if l == "logic":
        return {"min_chunk": 28.0, "min_interval": 0.16, "post_sleep": 0.04}
    if l == "care":
        return {"min_chunk": 18.0, "min_interval": 0.10, "post_sleep": 0.06}
    if l == "tease":
        return {"min_chunk": 20.0, "min_interval": 0.11, "post_sleep": 0.05}
    if l == "stress":
        return {"min_chunk": 16.0, "min_interval": 0.09, "post_sleep": 0.05}
    return {"min_chunk": 22.0, "min_interval": 0.12, "post_sleep": 0.05}


def derive_pending_fragment(
    *,
    user_text: str,
    previous_excerpt: str,
    pending_fragment: str,
) -> str:
    text = str(user_text or "").strip()
    prev = str(previous_excerpt or "").strip()
    pending = str(pending_fragment or "").strip()

    continue_markers = ["继续", "接着", "别停", "刚才", "续上", "继续刚才", "打断"]
    clear_markers = ["重来", "另一个话题", "换个话题", "先不聊这个"]

    if any(m in text for m in clear_markers):
        return ""
    if any(m in text for m in continue_markers):
        if prev:
            return prev[:240]
        if pending:
            return pending[:240]
    return pending[:240] if pending else ""


def build_claim_attribution(answer_text: str, evidence_pack: list[dict[str, Any]]) -> list[dict[str, Any]]:
    text = str(answer_text or "").strip()
    if not text or not isinstance(evidence_pack, list) or not evidence_pack:
        return []

    src_ids: list[int] = []
    for it in evidence_pack:
        try:
            sid = int(it.get("source_id") or 0)
        except Exception:
            sid = 0
        if sid > 0 and sid not in src_ids:
            src_ids.append(sid)

    if not src_ids:
        return []

    claim_excerpt = text[:220]
    return [{"claim_excerpt": claim_excerpt, "source_ids": src_ids}]
