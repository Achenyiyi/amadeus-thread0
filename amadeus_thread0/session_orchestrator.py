from __future__ import annotations

import re
from typing import Any


_CONTINUE_MARKERS = ["继续", "接着", "别停", "续上", "继续刚才", "打断"]
_CLEAR_MARKERS = ["重来", "另一个话题", "换个话题", "先不聊这个"]
_LOW_SIGNAL_USER_TURNS = {
    "好",
    "好的",
    "嗯",
    "嗯嗯",
    "谢谢",
    "收到",
    "知道了",
    "明白",
    "ok",
    "OK",
}
_CLARIFICATION_MARKERS = [
    "哪一段",
    "哪部分",
    "哪一个",
    "需要你明确",
    "请提供",
    "告诉我",
    "先确认",
    "具体是什么",
]


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


def _split_tts_units(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    units = [m.group(0) for m in re.finditer(r".+?(?:[。！？!?；;，,\n]|$)", raw, flags=re.S)]
    units = [seg for seg in units if seg]
    return units or [raw]


def build_tts_render_plan(text: str, emotion_label: str) -> dict[str, Any]:
    final_text = str(text or "").strip()
    profile = emotion_to_tts_profile(emotion_label)
    if not final_text:
        return {
            "emotion_label": str(emotion_label or "neutral").strip().lower() or "neutral",
            "profile": profile,
            "segments": [],
            "segment_count": 0,
            "char_count": 0,
            "final_text": "",
        }

    target = max(10, int(round(float(profile.get("min_chunk", 22.0) or 22.0))))
    units = _split_tts_units(final_text)

    segments: list[str] = []
    buf = ""
    for unit in units:
        buf += unit
        if len(buf) >= target:
            segments.append(buf)
            buf = ""

    if buf:
        if segments and len(buf) < max(8, target // 2):
            segments[-1] += buf
        else:
            segments.append(buf)

    if not segments:
        segments = [final_text]

    joined = "".join(segments)
    if joined != final_text:
        segments = [final_text]

    return {
        "emotion_label": str(emotion_label or "neutral").strip().lower() or "neutral",
        "profile": profile,
        "segments": segments,
        "segment_count": len(segments),
        "char_count": len(final_text),
        "final_text": final_text,
    }


def push_tts_segments(
    session: Any,
    *,
    text: str,
    emotion_label: str,
    sleep_fn: Any | None = None,
) -> dict[str, Any]:
    plan = build_tts_render_plan(text, emotion_label)
    segments = plan.get("segments") if isinstance(plan.get("segments"), list) else []
    if not segments:
        plan["sent_text"] = ""
        plan["sent_ok"] = True
        return plan

    sleeper = sleep_fn if callable(sleep_fn) else None
    interval = max(0.0, float(plan["profile"].get("min_interval", 0.0) or 0.0))
    post_sleep = max(0.0, float(plan["profile"].get("post_sleep", 0.0) or 0.0))
    sent: list[str] = []

    for idx, seg in enumerate(segments):
        session.append_text(seg)
        sent.append(seg)
        if sleeper is not None and idx < len(segments) - 1 and interval > 0.0:
            sleeper(interval)

    if sleeper is not None and sent and post_sleep > 0.0:
        sleeper(post_sleep)

    sent_text = "".join(sent)
    plan["sent_text"] = sent_text
    plan["sent_ok"] = sent_text == plan.get("final_text")
    return plan


def derive_pending_fragment(
    *,
    user_text: str,
    previous_excerpt: str,
    pending_fragment: str,
) -> str:
    text = str(user_text or "").strip()
    prev = str(previous_excerpt or "").strip()
    pending = str(pending_fragment or "").strip()
    has_continue = is_continuation_request(text)
    has_clear = any(marker in text for marker in _CLEAR_MARKERS)

    if has_continue:
        if pending:
            return pending[:240]
        if prev and _looks_like_unfinished_assistant_reply(prev) and not _looks_like_clarification_request(prev):
            return prev[:240]
        return ""
    if has_clear:
        return ""
    return ""


def is_continuation_request(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False

    compact = re.sub(r"\s+", "", text)
    if re.search(r"(不是要你|不要|不用|先别|别继续|别接着|别再).{0,8}(继续|接着|续上|说完|讲完|补完|分析)", compact):
        return False
    if compact in {"继续", "接着", "续上", "别停", "继续说", "接着说", "继续讲", "接着讲"}:
        return True

    direct_patterns = [
        r"^(继续|接着|续上)(说|讲|来|一下|刚才|那段|那个|前面|往下)?",
        r"^(别停|不要停|别停下)",
        r"^(从)?(刚才|上次|前面|那段|那个).{0,10}(继续|接着|续上|说完|讲完|补完)",
        r"(刚才|上次|前面|那段|那个).{0,10}(被打断|打断了)",
        r"(继续|接着).{0,10}(刚才|上次|前面|那段|那个)",
    ]
    if any(re.search(pattern, compact) for pattern in direct_patterns):
        return True

    # Mentioning "刚才" alone is often just emotional carry-over, not a request to
    # resume the assistant's previous unfinished output.
    if "刚才" in compact and not re.search(r"(继续|接着|续上|说完|讲完|补完|打断)", compact):
        return False

    return any(marker in compact for marker in _CONTINUE_MARKERS)


def _looks_like_unfinished_assistant_reply(text: str) -> bool:
    t = str(text or "").strip()
    if not t:
        return False
    if _looks_like_clarification_request(t):
        return False
    if re.search(r"(因为|所以|但是|不过|然后|而且|如果|只是|先|等下|等一下|比如|像是|除非|要不)$", t):
        return True
    if re.search(r"(第[一二三四五六七八九十]|首先|然后|接着|最后)[，、:：]?$", t):
        return True
    if re.search(r"(……|\.{3,})$", t):
        return True
    if re.search(r"[，、:：;；（(【\[“‘\"'-]$", t):
        return True
    if re.search(r"[。！？!?）】」』”’\"']$", t):
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z0-9]$", t) and len(t) >= 12)


def has_pending_continuation(*, user_text: str, pending_fragment: str) -> bool:
    return is_continuation_request(user_text) and bool(str(pending_fragment or "").strip())


def _looks_like_resume_goal_reference(text: str) -> bool:
    t = str(text or "").strip()
    if not t:
        return False
    referential_markers = [
        "上次那个",
        "刚才那个",
        "前面那个",
        "那段",
        "那个实验方案",
        "那个方案",
        "那个计划",
        "原来那个",
    ]
    action_markers = [
        "说完",
        "讲完",
        "补完",
        "继续",
        "接着",
        "分成三步",
        "把它说完",
        "把那段说完",
    ]
    return any(marker in t for marker in referential_markers) and any(marker in t for marker in action_markers)


def derive_pending_user_goal(
    *,
    user_text: str,
    previous_user_text: str,
    pending_user_goal: str,
    pending_fragment: str = "",
) -> str:
    text = str(user_text or "").strip()
    prev_user = str(previous_user_text or "").strip()
    pending = str(pending_user_goal or "").strip()
    has_continue = is_continuation_request(text)
    has_clear = any(marker in text for marker in _CLEAR_MARKERS)
    active_continuation = has_pending_continuation(user_text=text, pending_fragment=pending_fragment)

    if has_continue:
        if not active_continuation:
            return ""
        if pending:
            return pending[:280]
        if prev_user and not is_continuation_request(prev_user):
            return prev_user[:280]
        return ""
    if has_clear:
        return ""
    if _looks_like_resume_goal_reference(text):
        if _looks_like_substantive_goal(text):
            return text[:280]
        if pending:
            return pending[:280]
        if prev_user and not is_continuation_request(prev_user):
            return prev_user[:280]
        return text[:280]
    if _looks_like_substantive_goal(text):
        return text[:280]
    return pending[:280] if pending else ""


def _looks_like_substantive_goal(text: str) -> bool:
    t = str(text or "").strip()
    if not t:
        return False
    if t in _LOW_SIGNAL_USER_TURNS:
        return False
    if any(marker in t for marker in _CLEAR_MARKERS):
        return False
    if is_continuation_request(t):
        return False
    if len(t) >= 10:
        return True
    goal_markers = ["请", "帮我", "告诉我", "分析", "解释", "方案", "步骤", "为什么", "怎么", "什么"]
    return any(marker in t for marker in goal_markers)


def _looks_like_clarification_request(text: str) -> bool:
    t = str(text or "").strip()
    if not t:
        return False
    return any(marker in t for marker in _CLARIFICATION_MARKERS)


def _split_claim_units(text: str) -> list[str]:
    chunks: list[str] = []
    for raw_line in str(text or "").replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        for part in re.split(r"(?<=[。！？!?；;])", line):
            seg = part.strip().strip("-").strip("•").strip()
            if seg:
                chunks.append(seg)
    return chunks


def _is_attributable_claim(text: str) -> bool:
    t = str(text or "").strip()
    if len(t) < 6:
        return False
    plain = re.sub(r"[*_`#>\-\s:：]+", "", t)
    if plain in {"结论", "解释", "说明", "步骤", "下一步", "建议"}:
        return False
    if t.endswith(":") or t.endswith("："):
        return False
    if "?" in t or "？" in t:
        return False
    if t.startswith("需要我") or t.startswith("要不要") or t.startswith("如果你要"):
        return False
    if "外部信息未形成可追溯证据链" in t:
        return False
    return True


def _text_units(text: str) -> set[str]:
    raw = str(text or "").strip().lower()
    if not raw:
        return set()
    units = set(re.findall(r"[a-z0-9_]{2,}", raw))
    for chunk in re.findall(r"[\u4e00-\u9fff]+", raw):
        if len(chunk) == 1:
            units.add(chunk)
            continue
        for i in range(len(chunk) - 1):
            units.add(chunk[i : i + 2])
    return units


def _overlap_score(a: str, b: str) -> float:
    au = _text_units(a)
    bu = _text_units(b)
    if not au or not bu:
        return 0.0
    overlap = len(au & bu)
    denom = max(1, min(len(au), 6))
    return max(0.0, min(1.0, float(overlap) / float(denom)))


def _pick_sources_for_claim(claim: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    claim_low = str(claim or "").strip().lower()
    needs_persistence = any(tok in claim_low for tok in {"persistence", "持久化", "checkpoint", "checkpointer", "thread", "线程"})
    needs_hitl = any(tok in claim_low for tok in {"human-in-the-loop", "human in the loop", "hitl", "人工", "审批", "审核", "监督", "中断"})
    for src in sources:
        title = str(src.get("title") or "").strip()
        snippet = str(src.get("snippet") or "").strip()
        query = str(src.get("query") or "").strip()
        span_hint = str(src.get("span_hint") or "").strip()
        url = str(src.get("url") or "").strip().lower()
        score = 0.0
        score += 0.42 * _overlap_score(claim, title)
        score += 0.32 * _overlap_score(claim, snippet)
        score += 0.10 * _overlap_score(claim, query)
        score += 0.08 * _overlap_score(claim, span_hint)
        try:
            reliability = float(src.get("reliability_score", 0.0) or 0.0)
        except Exception:
            reliability = 0.0
        score += 0.08 * max(0.0, min(1.0, reliability))
        if "/oss/python/" in url:
            score += 0.05
        elif "/oss/javascript/" in url:
            score += 0.02
        if needs_persistence:
            if "/langgraph/persistence" in url:
                score += 0.24
            elif any(tok in url for tok in {"/overview", "/releases/", "/contributing/", "/cli", "/test"}):
                score -= 0.12
        if needs_hitl:
            if "/human-in-the-loop" in url:
                score += 0.24
            elif any(tok in url for tok in {"/middleware/built-in", "/guardrails"}):
                score += 0.06
            elif any(tok in url for tok in {"/overview", "/releases/", "/contributing/", "/cli", "/test"}):
                score -= 0.10
        if score > 0.08:
            scored.append((score, src))

    if not scored:
        return sources[:2]

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score = scored[0][0]
    min_keep = max(0.12, best_score * 0.4)
    selected: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for score, src in scored:
        if score < min_keep and selected:
            continue
        try:
            sid = int(src.get("source_id") or 0)
        except Exception:
            sid = 0
        if sid > 0 and sid in seen_ids:
            continue
        row = dict(src)
        row["match_score"] = round(score, 4)
        selected.append(row)
        if sid > 0:
            seen_ids.add(sid)
        if len(selected) >= 2:
            break
    return selected


def build_claim_attribution(answer_text: str, evidence_pack: list[dict[str, Any]]) -> list[dict[str, Any]]:
    text = str(answer_text or "").strip()
    if not text or not isinstance(evidence_pack, list) or not evidence_pack:
        return []

    src_ids: list[int] = []
    sources: list[dict[str, Any]] = []
    for it in evidence_pack:
        try:
            sid = int(it.get("source_id") or 0)
        except Exception:
            sid = 0
        if sid <= 0 or sid in src_ids:
            continue
        src_ids.append(sid)
        sources.append(
            {
                "source_id": sid,
                "url": str(it.get("url") or "").strip(),
                "title": str(it.get("title") or "").strip(),
                "tool_name": str(it.get("tool_name") or "").strip(),
                "snippet": str(it.get("snippet") or "").strip(),
                "query": str(it.get("query") or "").strip(),
                "span_hint": str(it.get("span_hint") or "").strip(),
                "reliability_score": it.get("reliability_score"),
            }
        )

    if not src_ids:
        return []

    claim_units = [seg for seg in _split_claim_units(text) if _is_attributable_claim(seg)]
    if not claim_units:
        claim_units = [text[:160]]

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for seg in claim_units[:4]:
        excerpt = seg[:160].strip()
        if not excerpt or excerpt in seen:
            continue
        seen.add(excerpt)
        matched = _pick_sources_for_claim(excerpt, sources)
        matched_ids = [int(src.get("source_id") or 0) for src in matched if int(src.get("source_id") or 0) > 0]
        if not matched_ids:
            matched = sources[:2]
            matched_ids = [int(src.get("source_id") or 0) for src in matched if int(src.get("source_id") or 0) > 0]
        out.append(
            {
                "claim_excerpt": excerpt,
                "source_ids": matched_ids,
                "sources": matched,
            }
        )
    return out
