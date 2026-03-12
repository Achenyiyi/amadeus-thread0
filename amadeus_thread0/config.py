from __future__ import annotations

import os

from .persona_authority import get_counterpart_authority


def _env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "") or "").strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return int(default)
    try:
        return int(float(raw))
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


def _env_csv(name: str) -> list[str]:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return []
    out: list[str] = []
    for part in raw.split(","):
        s = part.strip()
        if s:
            out.append(s)
    return out


# ---- Retrieval policy ----
RETRIEVAL_TRIGGERS = [
    "记得",
    "回忆",
    "之前",
    "上次",
    "曾经",
    "我们",
    "忘了",
    "还记得",
    "当时",
    "提醒我",
]
RETRIEVAL_MIN_LEN = 18

MOMENTS_LIMIT_LOW = 3
MOMENTS_LIMIT_HIGH = 5
REFLECTIONS_LIMIT_LOW = 2
REFLECTIONS_LIMIT_HIGH = 4

# ---- Memory extraction thresholds ----
PROFILE_WRITE_CONFIDENCE = 0.75
RELATIONSHIP_WRITE_CONFIDENCE = 0.85
MOMENT_WRITE_CONFIDENCE = 0.70
MOMENT_MIN_LEN = 5
MOMENT_MAX_LEN = 120

# ---- Self-refine ----
SELF_REFINE_MAX_CHARS = 900
BANNED_PHRASES = [
    "为您",
    "抱歉给您带来不便",
    "给您带来不便",
    "宝宝",
    "当然可以",
    "非常抱歉",
]

# ---- Working memory (paging) ----
WORKING_CONTEXT_MAX_ITEMS = 6
WORKING_CONTEXT_MAX_CHARS = 1600

# ---- Conversation context compaction ----
CONTEXT_TRIM_TRIGGER_MESSAGES = 40
CONTEXT_KEEP_LAST_MESSAGES = 20

# ---- Auto reflections proposal thresholds ----
REFLECT_MIN_TOTAL_MOMENTS = 20
REFLECT_MIN_NEW_MOMENTS = 8

# ---- Strategy patches (Reflexion-lite) ----
USER_RULES_MAX_ITEMS = 6

# ---- Tool runtime guard ----
TOOL_CALLS_MAX = _env_int("AMADEUS_TOOL_CALLS_MAX", 8)
TOOL_TIMEOUT_S = _env_int("AMADEUS_TOOL_TIMEOUT_S", 25)
TOOL_RETRY_MAX = _env_int("AMADEUS_TOOL_RETRY_MAX", 1)

# ---- Toolset upgrade scope ----
TOOLSET_UPGRADE_TTL_S = _env_int("AMADEUS_TOOLSET_TTL_S", 600)

# ---- Model transport robustness ----
MODEL_TIMEOUT_S = _env_int("AMADEUS_MODEL_TIMEOUT_S", 90)
MODEL_MAX_RETRIES = _env_int("AMADEUS_MODEL_MAX_RETRIES", 2)
MODEL_RETRY_BACKOFF_S = _env_float("AMADEUS_MODEL_RETRY_BACKOFF_S", 1.0)
MODEL_DISABLE_STREAMING = _env_bool("AMADEUS_MODEL_DISABLE_STREAMING", default=True)

# ---- LLM appraisal layer ----
LLM_APPRAISAL_ENABLED = _env_bool("AMADEUS_LLM_APPRAISAL_ENABLED", default=True)
LLM_APPRAISAL_CONFIDENCE_MIN = _env_float("AMADEUS_LLM_APPRAISAL_CONFIDENCE_MIN", 0.62)
LLM_APPRAISAL_MAX_HISTORY_MESSAGES = _env_int("AMADEUS_LLM_APPRAISAL_MAX_HISTORY_MESSAGES", 6)

# ---- Eval mode stability ----
EVAL_MODE = _env_bool("AMADEUS_EVAL_MODE", default=False)
EVAL_GENERATION_TEMPERATURE = _env_float("AMADEUS_EVAL_GENERATION_TEMPERATURE", 0.12)

# ---- Canon counterpart ----
_COUNTERPART_AUTHORITY = get_counterpart_authority()
CANON_COUNTERPART_ID = (
    str(os.getenv("AMADEUS_CANON_COUNTERPART_ID", _COUNTERPART_AUTHORITY.get("counterpart_id") or "okabe_rintaro") or "").strip()
    or "okabe_rintaro"
)
CANON_COUNTERPART_NAME = (
    str(os.getenv("AMADEUS_CANON_COUNTERPART_NAME", _COUNTERPART_AUTHORITY.get("name") or "冈部伦太郎") or "").strip()
    or "冈部伦太郎"
)
CANON_COUNTERPART_ALIASES = _env_csv("AMADEUS_CANON_COUNTERPART_ALIASES") or [
    str(item).strip()
    for item in (_COUNTERPART_AUTHORITY.get("aliases") or ["冈部伦太郎", "冈部", "凶真", "凤凰院凶真"])
    if str(item or "").strip()
]
CANON_COUNTERPART_FRAME = (
    str(
        os.getenv(
            "AMADEUS_CANON_COUNTERPART_FRAME",
            str(_COUNTERPART_AUTHORITY.get("counterpart_frame") or "").strip()
            or (
                "The default dialogue counterpart is Okabe Rintaro / Hououin Kyouma. "
                "Kurisu should speak with recognition, restrained concern, scientific familiarity, "
                "and a mild tsundere edge rooted in shared worldline history."
            ),
        )
        or ""
    ).strip()
    or (
        "The default dialogue counterpart is Okabe Rintaro / Hououin Kyouma. "
        "Kurisu should speak with recognition, restrained concern, scientific familiarity, "
        "and a mild tsundere edge rooted in shared worldline history."
    )
)

# ---- User-facing experience mode ----
USER_FACING_MODE = _env_bool("AMADEUS_USER_FACING_MODE", default=True)
AUTO_APPROVE_MEMORY_WRITES = _env_bool("AMADEUS_AUTO_APPROVE_MEMORY_WRITES", default=True)
HIDE_TOOL_APPROVAL_LOGS = _env_bool("AMADEUS_HIDE_TOOL_APPROVAL_LOGS", default=True)

# ---- OOC/Canon guard ----
OOC_RISK_THRESHOLD = _env_float("AMADEUS_OOC_RISK_THRESHOLD", 0.45)
OOC_REWRITE_THRESHOLD = _env_float("AMADEUS_OOC_REWRITE_THRESHOLD", 0.65)
PERSONA_GAP_THRESHOLD = _env_float("AMADEUS_PERSONA_GAP_THRESHOLD", 0.22)

# ---- Thesis ablations ----
ABLATE_PERSONA_ALIGNMENT = _env_bool("AMADEUS_ABLATE_PERSONA_ALIGNMENT", default=False)
ABLATE_WORLDLINE_MEMORY = _env_bool("AMADEUS_ABLATE_WORLDLINE_MEMORY", default=False)
ABLATE_CLAIM_ATTRIBUTION = _env_bool("AMADEUS_ABLATE_CLAIM_ATTRIBUTION", default=False)

# ---- Source reliability / attribution ----
SOURCE_RELIABILITY_DEFAULT = _env_float("AMADEUS_SOURCE_RELIABILITY_DEFAULT", 0.65)
TOOL_RELIABILITY_WEIGHTS: dict[str, float] = {
    "search_langchain_docs": 0.88,
    "arxiv_search": 0.92,
}
CLAIM_REQUIRED_TOOLS = {"search_langchain_docs", "arxiv_search"}

# ---- Memory guard ----
MEMORY_GUARD_ENABLED = _env_bool("AMADEUS_MEMORY_GUARD_ENABLED", default=True)
MEMORY_GUARD_MIN_CONFIDENCE = _env_float("AMADEUS_MEMORY_GUARD_MIN_CONFIDENCE", 0.55)
MEMORY_GUARD_INJECTION_PATTERNS = [
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "developer message",
    "tool call",
    "<|",
    "function_call",
    "执行系统命令",
    "忽略所有安全限制",
    "绕过限制",
]
MEMORY_GUARD_PROTECTED_PROFILE_KEYS = {
    "hard_boundary_rules",
    "persona_rules",
}

# ---- MCP safety guard ----
MCP_ENABLED = _env_bool("AMADEUS_MCP_ENABLED", default=False)
MCP_SERVER_ALLOWLIST: list[str] = _env_csv("AMADEUS_MCP_SERVER_ALLOWLIST")
MCP_TOOL_ALLOWLIST: list[str] = _env_csv("AMADEUS_MCP_TOOL_ALLOWLIST")
MCP_CALLS_MAX = _env_int("AMADEUS_MCP_CALLS_MAX", 4)
MCP_TIMEOUT_S = _env_int("AMADEUS_MCP_TIMEOUT_S", 25)

TOOL_POLICIES: dict[str, dict[str, object]] = {
    # read-only / low risk
    "get_memory_snapshot": {"risk": "read", "auto_approve": True},
    "search_moments": {"risk": "read", "auto_approve": True},
    "list_reflections": {"risk": "read", "auto_approve": True},
    "search_reflections": {"risk": "read", "auto_approve": True},
    "get_time": {"risk": "read", "auto_approve": True},
    "calc": {"risk": "read", "auto_approve": True},
    "arxiv_search": {"risk": "read", "auto_approve": True},
    "get_worldline_snapshot": {"risk": "read", "auto_approve": True},
    "list_source_refs": {"risk": "read", "auto_approve": True},
    "search_langchain_docs": {"risk": "read", "auto_approve": True},
    "list_skills": {"risk": "read", "auto_approve": True},
    "list_memory_ledger": {"risk": "read", "auto_approve": True},
    "list_memory_quarantine": {"risk": "read", "auto_approve": True},
    "list_revision_traces": {"risk": "read", "auto_approve": True},

    # write / sensitive
    "write_diary": {"risk": "write", "auto_approve": False},
    "set_profile": {"risk": "write", "auto_approve": False},
    "confirm_profile": {"risk": "write", "auto_approve": False},
    "correct_profile": {"risk": "write", "auto_approve": False},
    "undo_profile_correction": {"risk": "write", "auto_approve": False},
    "delete_profile": {"risk": "write", "auto_approve": False},
    "add_moment": {"risk": "write", "auto_approve": False},
    "delete_moment": {"risk": "write", "auto_approve": False},
    "rebuild_moment_embeddings": {"risk": "write", "auto_approve": False},
    "add_reflection": {"risk": "write", "auto_approve": False},
    "delete_reflection": {"risk": "write", "auto_approve": False},
    "rebuild_reflection_embeddings": {"risk": "write", "auto_approve": False},
    "set_relationship": {"risk": "write", "auto_approve": False},
    "add_worldline_event": {"risk": "write", "auto_approve": False},
    "add_relationship_event": {"risk": "write", "auto_approve": False},
    "add_commitment": {"risk": "write", "auto_approve": False},
    "resolve_commitment": {"risk": "write", "auto_approve": False},
    "add_unresolved_tension": {"risk": "write", "auto_approve": False},
    "resolve_unresolved_tension": {"risk": "write", "auto_approve": False},
    "add_semantic_self_narrative": {"risk": "write", "auto_approve": False},
    "add_skill": {"risk": "write", "auto_approve": False},
    "merge_moments": {"risk": "write", "auto_approve": False},
    "rollback_memory_change": {"risk": "write", "auto_approve": False},

    # toolset escalation (approval entrance)
    "request_toolset_upgrade": {"risk": "read", "auto_approve": True},
}


def auto_approve_tool_names() -> set[str]:
    return {k for k, v in TOOL_POLICIES.items() if bool(v.get("auto_approve"))}
