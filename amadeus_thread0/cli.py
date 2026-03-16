from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import time
import uuid
import warnings
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import io
import math

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("BITSANDBYTES_NOWELCOME", "1")
logging.getLogger("tensorflow").setLevel(logging.ERROR)
logging.getLogger("absl").setLevel(logging.ERROR)
logging.getLogger("bitsandbytes").setLevel(logging.ERROR)
logging.getLogger("bitsandbytes.cextension").setLevel(logging.ERROR)
warnings.filterwarnings(
    "ignore",
    message=r".*_register_pytree_node.*deprecated.*",
    category=FutureWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r".*resume_download.*deprecated.*",
    category=FutureWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r".*sparse_softmax_cross_entropy is deprecated.*",
)

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langgraph.types import Command

from .config import (
    AUTO_APPROVE_MEMORY_WRITES,
    HIDE_TOOL_APPROVAL_LOGS,
    TOOL_CALLS_MAX,
    TOOLSET_UPGRADE_TTL_S,
    USER_FACING_MODE,
)
from .utils.cli_views import (
    build_evolution_cli_summary,
    build_evolution_summary_line,
    render_behavior_queue_cli_text,
)
from .graph import build_graph, build_implicit_idle_state_update, reset_runtime_caches
from .memory_store import MemoryStore
from .runtime.modeling import build_chat_model, runtime_model_summary
from .utils.perception_events import (
    build_seed_event,
    build_sense_event,
    list_event_seed_rows,
    list_sense_rows,
)
from .utils.runtime_audit import audit_runtime_layout, render_runtime_audit_report
from .runtime.session_orchestrator import emotion_to_tts_profile, push_tts_segments
from .runtime.settings import configure_runtime_environment, get_settings
from .utils.tools import reset_tool_runtime_caches
from .runtime.tts_io import create_dashscope_realtime_session, get_tts_config


def _is_transient_runtime_error(exc: Exception) -> bool:
    transient_names = {
        "RemoteProtocolError",
        "ReadError",
        "WriteError",
        "PoolTimeout",
        "ReadTimeout",
        "ConnectTimeout",
        "TimeoutException",
        "ConnectError",
        "NetworkError",
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
    }
    cur: BaseException | None = exc
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if type(cur).__name__ in transient_names:
            return True
        cur = cur.__cause__ or cur.__context__
    return False


_SILENT_MEMORY_APPROVAL_TOOLS = {
    "set_profile",
    "confirm_profile",
    "correct_profile",
    "undo_profile_correction",
    "delete_profile",
    "add_moment",
    "delete_moment",
    "rebuild_moment_embeddings",
    "add_reflection",
    "delete_reflection",
    "rebuild_reflection_embeddings",
    "set_relationship",
    "add_worldline_event",
    "add_relationship_event",
    "add_commitment",
    "resolve_commitment",
    "merge_moments",
}


def _should_auto_resume_memory_approval(payload: dict[str, object]) -> bool:
    if not bool(USER_FACING_MODE) or not bool(AUTO_APPROVE_MEMORY_WRITES):
        return False
    source = str(payload.get("source") or "").strip().lower()
    if source != "memory":
        return False
    tool_calls = payload.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        return False
    for tc in tool_calls:
        if not isinstance(tc, dict):
            return False
        name = str(tc.get("name") or "").strip()
        if name not in _SILENT_MEMORY_APPROVAL_TOOLS:
            return False
    return True


def _normalize_cli_text(text: str) -> str:
    return str(text or "").encode("utf-8", "ignore").decode("utf-8").strip()


def _print_help() -> None:
    print(
        "\n[commands]\n"
        "/help                     查看命令总览\n"
        "/exit                     退出 CLI\n"
        "/newthread [thread_id]    切换到新世界线；留空则自动生成\n"
        "/threads                  列出已有 thread_id\n"
        "/history [n]              查看 checkpoint 历史\n"
        "/rewind <checkpoint_id>   从 checkpoint 分叉继续\n"
        "/where                    查看当前 thread / checkpoint\n"
        "/runtime                  查看 shared / isolated runtime 数据布局\n"
        "/env                      查看运行环境摘要\n"
        "/mem                      查看 profile / relationship / moments 快照\n"
        "/worldline                查看世界线事件 / 承诺 / 冲突修复\n"
        "/bond                     查看关系状态与关系时间线\n"
        "/sources                  查看来源与 claim->source 映射\n"
        "/persona                  查看角色状态快照\n"
        "/appraisal                查看最近一轮 appraisal 结果\n"
        "/agenda                   查看待成熟行为议程\n"
        "/queue                    查看待成熟行为队列（/agenda 别名）\n"
        "/idle [minutes] [| note]  模拟一段安静时间经过，让她决定是否主动开口\n"
        "/pulse [total] [step] [| note] 连续推进安静时间，观察她是否会主动靠近/延后/保持自己的节奏\n"
        "/events                   列出可注入的感知/生活事件种子\n"
        "/senses                   列出感知快捷入口\n"
        "/event <seed_id> [| note] 触发一个事件种子，让她按事件而非用户发言做行为选择\n"
        "/sense <ref> [| note]     注入一个感知事件，如 wave / busy / fish / scene / gesture / ambient\n"
        "/correct key=value        纠正 profile\n"
        "/undo key                 撤销最近一次纠错\n"
        "/set key=value            直接写入 profile\n"
        "/forget key               删除 profile 项\n"
        "/moments                  查看 moments\n"
        "/reflections              查看 reflections\n"
        "/reflect [n]              从最近 moments 生成 reflection 提案\n"
        "/tts on|off|status        控制语音输出\n"
        "/tts_ref <path.wav>       设置参考音频\n"
        "/tts_ref_text <text>      设置参考文本\n"
    )


def _sanitize_thread_id_seed(raw: str, *, fallback: str = "thread") -> str:
    seed = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(raw or "").strip()).strip("-._")
    return seed or fallback


def _generate_thread_id(
    *,
    prefix: str = "thread",
    now_ts: int | None = None,
    suffix: str | None = None,
) -> str:
    safe_prefix = _sanitize_thread_id_seed(prefix)
    clock = int(now_ts if now_ts is not None else time.time())
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(clock))
    token = _sanitize_thread_id_seed(suffix or uuid.uuid4().hex[:8], fallback="session")
    return f"{safe_prefix}-{stamp}-{token}"


def _resolve_startup_thread_id(
    *,
    default_thread_id: str,
    cli_thread_id: str | None,
    fresh_thread: bool,
    fresh_thread_prefix: str,
    now_ts: int | None = None,
    suffix: str | None = None,
) -> str:
    if cli_thread_id:
        return _sanitize_thread_id_seed(cli_thread_id, fallback=default_thread_id)
    if fresh_thread:
        return _generate_thread_id(prefix=fresh_thread_prefix, now_ts=now_ts, suffix=suffix)
    return default_thread_id


def _build_startup_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m amadeus_thread0.cli",
        description="Amadeus-K CLI",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--thread-id",
        dest="thread_id",
        help="启动时直接使用指定 thread_id。",
    )
    group.add_argument(
        "--fresh-thread",
        action="store_true",
        help="启动时自动创建一个新的 thread_id，避免复用旧世界线。",
    )
    parser.add_argument(
        "--fresh-thread-prefix",
        default="thread",
        help="配合 --fresh-thread 使用的 thread_id 前缀，默认 thread。",
    )
    return parser


def _worldline_runtime_dir(base_data_dir: Path, thread_id: str) -> Path:
    return Path(base_data_dir) / "worldlines" / _sanitize_thread_id_seed(thread_id, fallback="thread")


def _apply_worldline_runtime_paths(base_data_dir: Path, thread_id: str) -> Path:
    runtime_dir = _worldline_runtime_dir(base_data_dir, thread_id)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    os.environ["AMADEUS_DATA_DIR"] = str(runtime_dir)
    os.environ["AMADEUS_CHECKPOINT_DB"] = str(runtime_dir / "checkpoints.sqlite")
    os.environ["AMADEUS_MEMORY_DB"] = str(runtime_dir / "memories.sqlite")
    os.environ["AMADEUS_DIARY_PATH"] = str(runtime_dir / "diary.txt")
    return runtime_dir


def _has_explicit_runtime_path_overrides() -> bool:
    return any(
        str(os.getenv(name) or "").strip()
        for name in {
            "AMADEUS_DATA_DIR",
            "AMADEUS_CHECKPOINT_DB",
            "AMADEUS_MEMORY_DB",
            "AMADEUS_DIARY_PATH",
        }
    )


def _should_isolate_startup_runtime(
    *,
    startup_thread_id: str,
    fresh_thread: bool,
    explicit_runtime_paths: bool,
) -> bool:
    thread_id = str(startup_thread_id or "").strip()
    if fresh_thread:
        return True
    if explicit_runtime_paths:
        return False
    return bool(thread_id) and thread_id != "thread0"


def _repo_default_data_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "data"


def _shared_runtime_artifacts(base_data_dir: Path) -> list[str]:
    names = [
        "checkpoints.sqlite",
        "memories.sqlite",
        "decision_audit.jsonl",
        "mcp_audit.jsonl",
        "memory_store_audit.jsonl",
        "tool_audit.jsonl",
    ]
    found: list[str] = []
    root = Path(base_data_dir)
    for name in names:
        path = root / name
        try:
            if path.exists() and path.is_file() and path.stat().st_size > 0:
                found.append(name)
        except Exception:
            continue
    return found


def _should_warn_shared_default_runtime(
    *,
    base_data_dir: Path,
    runtime_data_dir: Path,
    startup_thread_id: str,
    startup_explicit: bool,
    shared_artifacts: list[str],
) -> bool:
    if startup_explicit:
        return False
    if str(startup_thread_id or "").strip() != "thread0":
        return False
    if not shared_artifacts:
        return False
    try:
        if Path(base_data_dir).resolve() != _repo_default_data_dir().resolve():
            return False
        if Path(runtime_data_dir).resolve() != Path(base_data_dir).resolve():
            return False
    except Exception:
        return False
    raw = str(os.getenv("AMADEUS_CLI_SUPPRESS_SHARED_RUNTIME_WARNING", "0") or "").strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return False
    return True

def _build_run_config(base_config: dict[str, object], pending_checkpoint_id: str | None) -> tuple[dict[str, object], str | None]:
    run_config: dict[str, object] = base_config
    pending_after = pending_checkpoint_id
    if pending_checkpoint_id:
        run_config = {
            "configurable": {
                "thread_id": base_config["configurable"]["thread_id"],
                "user_id": base_config["configurable"].get("user_id"),
                "checkpoint_id": pending_checkpoint_id,
            }
        }
        pending_after = None
    return run_config, pending_after


def _invoke_event_round(
    *,
    graph,
    run_config: dict[str, object],
    event_payload: dict[str, object],
    transient_label: str,
) -> tuple[dict[str, object], str]:
    before = graph.get_state({"configurable": {"thread_id": run_config["configurable"]["thread_id"]}})
    before_values = getattr(before, "values", {}) if before is not None else {}
    if not isinstance(before_values, dict):
        before_values = {}
    before_messages = before_values.get("messages") if isinstance(before_values.get("messages"), list) else []
    before_len = len(before_messages)

    try:
        out = graph.invoke(event_payload, config=run_config)
    except Exception as e:
        if _is_transient_runtime_error(e):
            print(f"\n[{transient_label}][warn] 本轮事件触发时网络连接中断。稍后再试就行。")
            return {}, ""
        raise

    while out.get("__interrupt__"):
        intr = out["__interrupt__"][0]
        payload = getattr(intr, "value", None)
        if payload is None and isinstance(intr, dict):
            payload = intr.get("value")
        payload = payload or {}
        tool_calls = payload.get("tool_calls") if isinstance(payload.get("tool_calls"), list) else []
        if isinstance(payload, dict) and _should_auto_resume_memory_approval(payload):
            decisions = [{"action": "approve"} for _ in tool_calls]
        else:
            decisions = [{"action": "reject", "reason": f"{transient_label}_no_manual_tooling"} for _ in tool_calls]
        out = graph.invoke(
            Command(resume={"decisions": decisions}),
            config={"configurable": {"thread_id": run_config["configurable"]["thread_id"]}},
        )

    after = graph.get_state({"configurable": {"thread_id": run_config["configurable"]["thread_id"]}})
    after_values = getattr(after, "values", {}) if after is not None else {}
    if not isinstance(after_values, dict):
        after_values = {}
    after_messages = after_values.get("messages") if isinstance(after_values.get("messages"), list) else []
    final_text = ""
    if len(after_messages) > before_len and after_messages:
        last = after_messages[-1]
        final_text = str(getattr(last, "content", "") or "").strip()
    return after_values, final_text


def _speak_text_realtime(
    *,
    text: str,
    emotion_label: str,
    enabled: bool,
    ref_audio: str,
) -> None:
    if not enabled:
        return
    final_text = str(text or "").strip()
    if not final_text:
        return

    backend = str(os.getenv("AMADEUS_TTS_BACKEND", "dashscope_realtime") or "dashscope_realtime").strip().strip('"').lower()
    if backend not in {"dashscope_realtime", "dashscope"}:
        print("\n[TTS][warn] TTS backend must be dashscope_realtime -> fallback=text-only")
        return
    if not ref_audio:
        print("\n[TTS][warn] AMADEUS_TTS_REF_AUDIO is required for dashscope enrollment -> fallback=text-only")
        return

    tts_out_dir = get_settings().data_dir / "tts_out"
    rt = None
    try:
        noise = io.StringIO()
        with redirect_stdout(noise), redirect_stderr(noise):
            rt = create_dashscope_realtime_session(
                ref_audio=ref_audio,
                out_dir=tts_out_dir,
                play_audio=True,
            )
        tts_plan = push_tts_segments(
            rt,
            text=final_text,
            emotion_label=str(emotion_label or "neutral").strip() or "neutral",
            sleep_fn=time.sleep,
        )
    except Exception as e:
        print("\n[TTS][warn] realtime init/push failed: " + str(e) + " -> fallback=text-only")
        return

    noise = io.StringIO()
    with redirect_stdout(noise), redirect_stderr(noise):
        rt.finish_and_wait()
    if rt.total_audio_bytes <= 0:
        print("[TTS-RT][warn] received 0 audio bytes (check API key/model/ws url & callback logs)")
    if isinstance(tts_plan, dict):
        profile = emotion_to_tts_profile(str(tts_plan.get("emotion_label") or emotion_label or "neutral"))
        print(
            "[TTS-RT] emotion="
            + str(tts_plan.get("emotion_label") or emotion_label or "neutral")
            + " | segments="
            + str(int(tts_plan.get("segment_count") or 0))
            + " | chars="
            + str(int(tts_plan.get("char_count") or 0))
            + " | interval="
            + str(profile.get("min_interval"))
        )
    if rt.first_audio_delay is not None:
        print(f"[TTS-RT] first_audio_delay={rt.first_audio_delay:.2f}s")
    print("[TTS-RT] saved: " + str(rt.out_path))


def _behavior_action_compact_line(action: dict[str, object] | None) -> str:
    if not isinstance(action, dict):
        return "-"
    mode = str(action.get("interaction_mode") or "").strip() or "-"
    target = str(action.get("action_target") or "").strip() or "-"
    channel = str(action.get("channel") or "").strip() or "-"
    style = str(action.get("approach_style") or "").strip() or "-"
    return f"mode={mode} | target={target} | channel={channel} | style={style}"


def _build_event_evolution_summary(
    memory_store: MemoryStore,
    after_values: dict[str, object] | None,
) -> dict[str, object]:
    vals = after_values if isinstance(after_values, dict) else {}
    return build_evolution_cli_summary(
        relationship=memory_store.get_relationship(),
        semantic_narrative_profile=vals.get("semantic_narrative_profile") if isinstance(vals.get("semantic_narrative_profile"), dict) else {},
        world_model_state=vals.get("world_model_state") if isinstance(vals.get("world_model_state"), dict) else {},
        emotion_state=vals.get("emotion_state") if isinstance(vals.get("emotion_state"), dict) else {},
        bond_state=vals.get("bond_state") if isinstance(vals.get("bond_state"), dict) else {},
        counterpart_assessment=vals.get("counterpart_assessment") if isinstance(vals.get("counterpart_assessment"), dict) else {},
        behavior_action=vals.get("behavior_action") if isinstance(vals.get("behavior_action"), dict) else {},
        behavior_plan=vals.get("behavior_plan") if isinstance(vals.get("behavior_plan"), dict) else {},
        behavior_queue=vals.get("behavior_queue") if isinstance(vals.get("behavior_queue"), list) else [],
        interaction_carryover=vals.get("interaction_carryover") if isinstance(vals.get("interaction_carryover"), dict) else {},
        current_event=vals.get("current_event") if isinstance(vals.get("current_event"), dict) else {},
        worldline_focus=vals.get("worldline_focus") if isinstance(vals.get("worldline_focus"), list) else [],
        reconsolidation_snapshot=vals.get("reconsolidation_snapshot") if isinstance(vals.get("reconsolidation_snapshot"), dict) else {},
    )


def _print_behavior_queue_summary(
    queue_vals: object,
    *,
    prefix: str = "",
) -> None:
    rendered = render_behavior_queue_cli_text(queue_vals, limit=3)
    if prefix:
        rendered = "\n".join(prefix + part if part else prefix for part in rendered.splitlines())
    print(f"\n{prefix}[BEHAVIOR_QUEUE_SUMMARY]\n" + rendered)


def _print_event_evolution_summary(
    summary: dict[str, object] | None,
    *,
    prefix: str = "",
    detailed: bool = False,
    label: str = "EVOLUTION",
) -> None:
    if not isinstance(summary, dict):
        return
    line = build_evolution_summary_line(summary)
    print(f"{prefix}[{label}] {line}")
    if not detailed:
        return
    dumped = json.dumps(summary, ensure_ascii=False, indent=2)
    if prefix:
        dumped = "\n".join(prefix + part if part else prefix for part in dumped.splitlines())
    print(f"\n{prefix}[{label}_SUMMARY]\n" + dumped)


def _print_turn_appraisal(values: dict[str, object] | None, *, prefix: str = "") -> None:
    vals = values if isinstance(values, dict) else {}
    appraisal = vals.get("turn_appraisal") if isinstance(vals.get("turn_appraisal"), dict) else {}
    dumped = json.dumps(appraisal, ensure_ascii=False, indent=2)
    if prefix:
        dumped = "\n".join(prefix + part if part else prefix for part in dumped.splitlines())
    print(f"\n{prefix}[TURN_APPRAISAL]\n" + dumped)


def _implicit_idle_trigger_minutes() -> int:
    raw = str(os.getenv("AMADEUS_IMPLICIT_IDLE_MINUTES", "") or "").strip()
    if not raw:
        return 12
    try:
        return max(0, min(24 * 60, int(raw)))
    except Exception:
        return 12


def _cli_show_turn_summary_enabled() -> bool:
    raw = str(os.getenv("AMADEUS_CLI_SHOW_TURN_SUMMARY", "0") or "").strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _apply_implicit_idle_maturation(
    *,
    graph,
    run_config: dict[str, object],
    last_conversation_touch_ts: int | None,
    now_ts: int | None = None,
) -> None:
    trigger_minutes = _implicit_idle_trigger_minutes()
    if trigger_minutes <= 0 or last_conversation_touch_ts is None:
        return
    clock_now = int(now_ts or time.time())
    elapsed_seconds = max(0, clock_now - int(last_conversation_touch_ts))
    elapsed_minutes = elapsed_seconds // 60
    if elapsed_minutes < trigger_minutes:
        return

    cfg = {"configurable": {"thread_id": run_config["configurable"]["thread_id"]}}
    current = graph.get_state(cfg)
    values = getattr(current, "values", {}) if current is not None else {}
    if not isinstance(values, dict):
        return

    prepared = build_implicit_idle_state_update(
        values,
        idle_minutes=int(elapsed_minutes),
        created_at=clock_now,
    )
    graph.update_state(cfg, prepared, as_node="prepare_turn")


def main():
    args = _build_startup_arg_parser().parse_args()

    # 优先从当前工作目录加载 .env（你用 `python -m amadeus_thread0.cli` 运行时最符合直觉）
    # 再回退到包根目录（避免以模块/安装形式运行时找不到配置）。
    dotenv_candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    ]
    loaded_path: Path | None = None
    for p in dotenv_candidates:
        if p.exists():
            # Keep shell-exported env vars higher priority than .env defaults.
            load_dotenv(dotenv_path=p, override=False)
            loaded_path = p
            break

    configure_runtime_environment()

    # 关闭 DashScope/websocket 的“正常断开(1000 Bye)”类提示，避免打断输入行。
    # （这些提示通常来自底层 websocket logger，而不是异常。）
    for name in ["websocket", "websockets", "dashscope"]:
        lg = logging.getLogger(name)
        lg.setLevel(logging.ERROR)
        lg.propagate = False

    print(
        "[env] cwd="
        + str(Path.cwd())
        + " | loaded="
        + (str(loaded_path) if loaded_path else "(none)")
    )
    print(
        "[env] AMADEUS_TTS_ENABLED="
        + str(os.getenv("AMADEUS_TTS_ENABLED"))
        + " | AMADEUS_TTS_BACKEND="
        + str(os.getenv("AMADEUS_TTS_BACKEND"))
        + " | AMADEUS_TTS_REF_AUDIO="
        + str(os.getenv("AMADEUS_TTS_REF_AUDIO"))
        + " | DASHSCOPE_API_KEY="
        + ("(set)" if str(os.getenv("DASHSCOPE_API_KEY") or "").strip() else "(empty)")
    )

    s = get_settings()
    base_data_dir = s.data_dir
    startup_explicit = bool(
        args.thread_id
        or args.fresh_thread
        or str(os.getenv("AMADEUS_THREAD_ID") or "").strip()
        or str(os.getenv("AMADEUS_DATA_DIR") or "").strip()
    )
    startup_thread_id = _resolve_startup_thread_id(
        default_thread_id=s.thread_id,
        cli_thread_id=args.thread_id,
        fresh_thread=bool(args.fresh_thread),
        fresh_thread_prefix=str(args.fresh_thread_prefix or "thread"),
    )
    isolated_worldline_dir: Path | None = None
    explicit_runtime_paths = _has_explicit_runtime_path_overrides()
    if _should_isolate_startup_runtime(
        startup_thread_id=startup_thread_id,
        fresh_thread=bool(args.fresh_thread),
        explicit_runtime_paths=explicit_runtime_paths,
    ):
        isolated_worldline_dir = _apply_worldline_runtime_paths(base_data_dir, startup_thread_id)
        s = get_settings()
    shared_runtime_artifacts = _shared_runtime_artifacts(base_data_dir)
    graph = build_graph()
    memory_store = MemoryStore(s.memory_db_path)

    config = {
        "configurable": {
            # LangGraph persistence 通过 thread_id 把 checkpoint 归到同一条“世界线”
            "thread_id": startup_thread_id,
            "user_id": s.user_id,
        }
    }

    # 用于 time travel：下一次对话从指定 checkpoint 分叉继续（用一次即清空）
    pending_checkpoint_id: str | None = None
    last_conversation_touch_ts: int | None = None

    # TTS（DashScope Realtime；从 env 读取）
    tts_cfg = get_tts_config()
    tts_enabled = bool(tts_cfg.enabled)
    tts_ref_audio = str(tts_cfg.ref_audio or "").strip()
    tts_ref_text = str(tts_cfg.ref_text or "").strip()

    print("Amadeus-K CLI 已启动。输入 /help 查看命令，/exit 退出。")
    if startup_thread_id != s.thread_id:
        print(
            "[runtime] startup_thread_override="
            + str(startup_thread_id)
            + " (default="
            + str(s.thread_id)
            + ")"
        )
    if isolated_worldline_dir is not None:
        print("[runtime] worldline_storage=" + str(isolated_worldline_dir))
    elif _should_warn_shared_default_runtime(
        base_data_dir=base_data_dir,
        runtime_data_dir=s.data_dir,
        startup_thread_id=startup_thread_id,
        startup_explicit=startup_explicit,
        shared_artifacts=shared_runtime_artifacts,
    ):
        print(
            "[runtime][warn] default thread0 is resuming shared runtime data in "
            + str(base_data_dir)
        )
        print(
            "[runtime][hint] clean demo: python -m amadeus_thread0.cli --fresh-thread"
        )
        print(
            "[runtime][hint] explicit resume: python -m amadeus_thread0.cli --thread-id thread0"
        )
        print(
            "[runtime][hint] shared artifacts="
            + ", ".join(shared_runtime_artifacts[:6])
        )
    print(
        "[runtime] model="
        + runtime_model_summary()
        + " | thread_id="
        + str(config["configurable"]["thread_id"])
        + " | data_dir="
        + str(s.data_dir)
    )
    print(
        "[TTS] "
        + ("on" if tts_enabled else "off")
        + " | backend=dashscope_realtime"
        + "\n      ref_audio="
        + (tts_ref_audio or "(empty)")
    )
    while True:
        user = _normalize_cli_text(input("\nYou> "))
        if not user:
            continue
        if user.lower() in {"/help", "/?"}:
            _print_help()
            continue
        if user.lower() in {"/exit", "exit", "quit"}:
            break
        if user.lower().startswith("/newthread"):
            new_id = _normalize_cli_text(user[len("/newthread") :].strip())
            if not new_id:
                entered = _normalize_cli_text(input("new thread_id (leave blank for auto)> "))
                new_id = entered or _generate_thread_id(prefix="thread")
            new_id = _sanitize_thread_id_seed(new_id, fallback=_generate_thread_id(prefix="thread"))
            worldline_dir = _apply_worldline_runtime_paths(base_data_dir, new_id)
            try:
                memory_store.close()
            except Exception:
                pass
            reset_tool_runtime_caches()
            reset_runtime_caches()
            s = get_settings()
            graph = build_graph()
            memory_store = MemoryStore(s.memory_db_path)
            config["configurable"]["thread_id"] = new_id
            # 切线程后清空 time travel 目标
            pending_checkpoint_id = None
            last_conversation_touch_ts = None
            print(f"已切换到 thread_id={new_id}")
            print("[runtime] worldline_storage=" + str(worldline_dir))
            continue
        if user.lower() == "/threads":
            # 从 checkpoints.sqlite 里尽量枚举 thread_id（不同版本表名可能不同，这里做容错）
            conn = sqlite3.connect(str(s.checkpoint_db_path), check_same_thread=False)
            try:
                tables = [
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                    ).fetchall()
                ]
                thread_ids: set[str] = set()
                for t in tables:
                    cols = [
                        c[1] for c in conn.execute(f"PRAGMA table_info({t})").fetchall()
                    ]
                    if "thread_id" not in cols:
                        continue
                    try:
                        rows = conn.execute(f"SELECT DISTINCT thread_id FROM {t}").fetchall()
                        for (tid,) in rows:
                            if tid:
                                thread_ids.add(str(tid))
                    except Exception:
                        continue
                if not thread_ids:
                    print("\n未在 checkpoint 数据库中找到 thread_id（可能还没有生成checkpoint）。")
                else:
                    print("\n[threads]")
                    for tid in sorted(thread_ids):
                        mark = "*" if tid == config["configurable"]["thread_id"] else " "
                        print(f"{mark} {tid}")
                worldline_root = Path(base_data_dir) / "worldlines"
                worldline_ids = sorted(
                    p.name for p in worldline_root.iterdir() if p.is_dir()
                ) if worldline_root.exists() else []
                if worldline_ids:
                    print("\n[worldline_dirs]")
                    for wid in worldline_ids:
                        mark = "*" if wid == config["configurable"]["thread_id"] else " "
                        print(f"{mark} {wid}")
            finally:
                conn.close()
            continue
        if user.lower().startswith("/history"):
            # /history 或 /history 10
            parts = user.split()
            limit = 10
            if len(parts) >= 2:
                try:
                    limit = int(parts[1])
                except Exception:
                    limit = 10
            hist = list(
                graph.get_state_history(
                    {"configurable": {"thread_id": config["configurable"]["thread_id"]}}
                )
            )
            print(
                f"\n[checkpoint history] (latest first, showing {min(limit, len(hist))}/{len(hist)})"
            )
            for sshot in hist[:limit]:
                cid = sshot.config.get("configurable", {}).get("checkpoint_id")
                nxt = sshot.next
                print(f"- checkpoint_id={cid} next={nxt}")
            continue
        if user.lower().startswith("/rewind "):
            # /rewind <checkpoint_id>
            cid = user[len("/rewind ") :].strip()
            if not cid:
                print("用法：/rewind <checkpoint_id>")
                continue
            pending_checkpoint_id = cid
            last_conversation_touch_ts = None
            print(f"已设置：下一次对话将从 checkpoint_id={cid} 分叉继续")
            continue
        if user.lower() == "/where":
            cur = graph.get_state(
                {"configurable": {"thread_id": config["configurable"]["thread_id"]}}
            )
            cid = cur.config.get("configurable", {}).get("checkpoint_id")
            print(
                f"\n[current] thread_id={config['configurable']['thread_id']} checkpoint_id={cid}"
            )
            continue
        if user.lower() == "/runtime":
            print("\n[repo-runtime]")
            print(render_runtime_audit_report(audit_runtime_layout(base_data_dir)))
            try:
                if Path(s.data_dir).resolve() != Path(base_data_dir).resolve():
                    print("\n[current-runtime]")
                    print(render_runtime_audit_report(audit_runtime_layout(s.data_dir)))
            except Exception:
                pass
            continue
        if user.lower() == "/env":
            print(
                "\n[env] cwd="
                + str(Path.cwd())
                + "\n  AMADEUS_MODEL_PROVIDER="
                + str(s.model_provider)
                + "\n  AMADEUS_MODEL_NAME="
                + str(s.model_name)
                + "\n  AMADEUS_MODEL_BASE_URL="
                + (str(s.model_base_url) if str(s.model_base_url).strip() else "(default)")
                + "\n  AMADEUS_RUNTIME_MODE="
                + str(s.runtime_mode)
                + "\n  AMADEUS_EVAL_MODE="
                + str(os.getenv("AMADEUS_EVAL_MODE", "0"))
                + "\n  AMADEUS_USER_FACING_MODE="
                + str(os.getenv("AMADEUS_USER_FACING_MODE", "1"))
                + "\n  AMADEUS_CLI_SHOW_TURN_SUMMARY="
                + str(os.getenv("AMADEUS_CLI_SHOW_TURN_SUMMARY", "0"))
                + "\n  AMADEUS_TTS_ENABLED="
                + str(os.getenv("AMADEUS_TTS_ENABLED"))
                + "\n  AMADEUS_TTS_BACKEND="
                + str(os.getenv("AMADEUS_TTS_BACKEND"))
                + "\n  AMADEUS_TTS_REF_AUDIO="
                + str(os.getenv("AMADEUS_TTS_REF_AUDIO"))
                + "\n  AMADEUS_TTS_DASHSCOPE_MODEL="
                + str(os.getenv("AMADEUS_TTS_DASHSCOPE_MODEL"))
                + "\n  DASHSCOPE_API_KEY="
                + ("(set)" if str(os.getenv("DASHSCOPE_API_KEY") or "").strip() else "(empty)")
            )
            continue
        if user.lower() == "/mem":
            snap = memory_store.snapshot()
            print("\n[PROFILE]\n" + json.dumps(snap["profile"], ensure_ascii=False, indent=2))
            print("\n[RELATIONSHIP]\n" + json.dumps(snap["relationship"], ensure_ascii=False, indent=2))
            print("\n[MOMENTS(latest)]\n" + json.dumps(snap["moments"], ensure_ascii=False, indent=2))
            continue
        if user.lower() == "/worldline":
            snap = memory_store.snapshot()
            cur = graph.get_state(
                {"configurable": {"thread_id": config["configurable"]["thread_id"]}}
            )
            vals = getattr(cur, "values", {}) if cur is not None else {}
            if not isinstance(vals, dict):
                vals = {}
            worldline_summary = build_evolution_cli_summary(
                relationship=snap.get("relationship") if isinstance(snap.get("relationship"), dict) else {},
                semantic_narrative_profile=vals.get("semantic_narrative_profile") if isinstance(vals.get("semantic_narrative_profile"), dict) else {},
                world_model_state=vals.get("world_model_state") if isinstance(vals.get("world_model_state"), dict) else {},
                emotion_state=vals.get("emotion_state") if isinstance(vals.get("emotion_state"), dict) else {},
                bond_state=vals.get("bond_state") if isinstance(vals.get("bond_state"), dict) else {},
                counterpart_assessment=vals.get("counterpart_assessment") if isinstance(vals.get("counterpart_assessment"), dict) else {},
                behavior_action=vals.get("behavior_action") if isinstance(vals.get("behavior_action"), dict) else {},
                behavior_plan=vals.get("behavior_plan") if isinstance(vals.get("behavior_plan"), dict) else {},
                behavior_queue=vals.get("behavior_queue") if isinstance(vals.get("behavior_queue"), list) else [],
                interaction_carryover=vals.get("interaction_carryover") if isinstance(vals.get("interaction_carryover"), dict) else {},
                current_event=vals.get("current_event") if isinstance(vals.get("current_event"), dict) else {},
                worldline_focus=vals.get("worldline_focus") if isinstance(vals.get("worldline_focus"), list) else [],
                reconsolidation_snapshot=vals.get("reconsolidation_snapshot") if isinstance(vals.get("reconsolidation_snapshot"), dict) else {},
            )
            print("\n[WORLDLINE_SUMMARY]\n" + json.dumps(worldline_summary, ensure_ascii=False, indent=2))
            print("\n[WORLDLINE_EVENTS]\n" + json.dumps(snap.get("worldline_events", []), ensure_ascii=False, indent=2))
            print("\n[COMMITMENTS]\n" + json.dumps(snap.get("commitments", []), ensure_ascii=False, indent=2))
            print("\n[CONFLICT_REPAIR]\n" + json.dumps(snap.get("conflict_repair", []), ensure_ascii=False, indent=2))
            print("\n[UNRESOLVED_TENSIONS]\n" + json.dumps(snap.get("unresolved_tensions", []), ensure_ascii=False, indent=2))
            print(
                "\n[SEMANTIC_SELF_NARRATIVES]\n"
                + json.dumps(snap.get("semantic_self_narratives", []), ensure_ascii=False, indent=2)
            )
            print("\n[REVISION_TRACES]\n" + json.dumps(snap.get("revision_traces", []), ensure_ascii=False, indent=2))
            continue
        if user.lower() == "/bond":
            rel = memory_store.get_relationship()
            rs = list(reversed(memory_store.list_relationship_timeline(limit=30)))
            repairs = list(reversed(memory_store.list_conflict_repairs(limit=30)))
            cur = graph.get_state(
                {"configurable": {"thread_id": config["configurable"]["thread_id"]}}
            )
            vals = getattr(cur, "values", {}) if cur is not None else {}
            if not isinstance(vals, dict):
                vals = {}
            current_rel = vals.get("relationship") if isinstance(vals.get("relationship"), dict) else None
            rel_out = current_rel if isinstance(current_rel, dict) and current_rel else rel
            print("\n[RELATIONSHIP_STATE]\n" + json.dumps(rel_out, ensure_ascii=False, indent=2))
            print("\n[BOND_STATE]\n" + json.dumps(vals.get("bond_state", {}), ensure_ascii=False, indent=2))
            print("\n[RELATIONSHIP_TIMELINE]")
            if not rs:
                print("- (empty)")
            for it in rs:
                print(
                    f"- #{it.get('id')} {it.get('summary')} "
                    f"(aff={it.get('affinity_delta')}, trust={it.get('trust_delta')})"
                )
            print("\n[CONFLICT_REPAIR]")
            if not repairs:
                print("- (empty)")
            for it in repairs:
                print(f"- #{it.get('id')} {it.get('summary')}")
            continue
        if user.lower() == "/sources":
            refs = list(reversed(memory_store.list_source_refs(limit=30)))
            cur = graph.get_state(
                {"configurable": {"thread_id": config["configurable"]["thread_id"]}}
            )
            vals = getattr(cur, "values", {}) if cur is not None else {}
            if not isinstance(vals, dict):
                vals = {}
            claim_links = vals.get("claim_links") if isinstance(vals.get("claim_links"), list) else []
            print("\n[SOURCES]")
            if not refs:
                print("- (empty)")
            for it in refs:
                print(
                    f"- #{it.get('id')} [{it.get('tool_name')}] {it.get('title') or '(no title)'}\n"
                    f"  url={it.get('url')} query={it.get('query')}"
                )
            print("\n[CLAIM->SOURCES]")
            if not claim_links:
                print("- (empty)")
            for row in claim_links:
                if not isinstance(row, dict):
                    continue
                print(
                    f"- claim={str(row.get('claim_excerpt') or '')[:120]}\n"
                    f"  source_ids={row.get('source_ids') or []}"
                )
            continue
        if user.lower() == "/persona":
            cur = graph.get_state(
                {"configurable": {"thread_id": config["configurable"]["thread_id"]}}
            )
            vals = getattr(cur, "values", {}) if cur is not None else {}
            if not isinstance(vals, dict):
                vals = {}
            evolution_summary = build_evolution_cli_summary(
                relationship=memory_store.get_relationship(),
                semantic_narrative_profile=vals.get("semantic_narrative_profile") if isinstance(vals.get("semantic_narrative_profile"), dict) else {},
                world_model_state=vals.get("world_model_state") if isinstance(vals.get("world_model_state"), dict) else {},
                emotion_state=vals.get("emotion_state") if isinstance(vals.get("emotion_state"), dict) else {},
                bond_state=vals.get("bond_state") if isinstance(vals.get("bond_state"), dict) else {},
                counterpart_assessment=vals.get("counterpart_assessment") if isinstance(vals.get("counterpart_assessment"), dict) else {},
                behavior_action=vals.get("behavior_action") if isinstance(vals.get("behavior_action"), dict) else {},
                behavior_plan=vals.get("behavior_plan") if isinstance(vals.get("behavior_plan"), dict) else {},
                behavior_queue=vals.get("behavior_queue") if isinstance(vals.get("behavior_queue"), list) else [],
                interaction_carryover=vals.get("interaction_carryover") if isinstance(vals.get("interaction_carryover"), dict) else {},
                current_event=vals.get("current_event") if isinstance(vals.get("current_event"), dict) else {},
                worldline_focus=vals.get("worldline_focus") if isinstance(vals.get("worldline_focus"), list) else [],
                reconsolidation_snapshot=vals.get("reconsolidation_snapshot") if isinstance(vals.get("reconsolidation_snapshot"), dict) else {},
            )
            print("\n[EVOLUTION_SUMMARY]\n" + json.dumps(evolution_summary, ensure_ascii=False, indent=2))
            print("\n[PERSONA_STATE]\n" + json.dumps(vals.get("persona_state", {}), ensure_ascii=False, indent=2))
            print("\n[EMOTION_STATE]\n" + json.dumps(vals.get("emotion_state", {}), ensure_ascii=False, indent=2))
            print("\n[BOND_STATE]\n" + json.dumps(vals.get("bond_state", {}), ensure_ascii=False, indent=2))
            print("\n[ALLOSTASIS_STATE]\n" + json.dumps(vals.get("allostasis_state", {}), ensure_ascii=False, indent=2))
            print("\n[COUNTERPART_ASSESSMENT]\n" + json.dumps(vals.get("counterpart_assessment", {}), ensure_ascii=False, indent=2))
            print("\n[SEMANTIC_NARRATIVE_PROFILE]\n" + json.dumps(vals.get("semantic_narrative_profile", {}), ensure_ascii=False, indent=2))
            print("\n[WORLD_MODEL_STATE]\n" + json.dumps(vals.get("world_model_state", {}), ensure_ascii=False, indent=2))
            print("\n[EVOLUTION_STATE]\n" + json.dumps(vals.get("evolution_state", {}), ensure_ascii=False, indent=2))
            print("\n[RECONSOLIDATION_SNAPSHOT]\n" + json.dumps(vals.get("reconsolidation_snapshot", {}), ensure_ascii=False, indent=2))
            print("\n[TURN_APPRAISAL]\n" + json.dumps(vals.get("turn_appraisal", {}), ensure_ascii=False, indent=2))
            print("\n[BEHAVIOR_POLICY]\n" + json.dumps(vals.get("behavior_policy", {}), ensure_ascii=False, indent=2))
            print("\n[BEHAVIOR_ACTION]\n" + json.dumps(vals.get("behavior_action", {}), ensure_ascii=False, indent=2))
            print("\n[INTERACTION_CARRYOVER]\n" + json.dumps(vals.get("interaction_carryover", {}), ensure_ascii=False, indent=2))
            print("\n[BEHAVIOR_PLAN]\n" + json.dumps(vals.get("behavior_plan", {}), ensure_ascii=False, indent=2))
            queue_vals = vals.get("behavior_queue", vals.get("behavior_agenda", []))
            _print_behavior_queue_summary(queue_vals)
            print("\n[BEHAVIOR_QUEUE]\n" + json.dumps(queue_vals, ensure_ascii=False, indent=2))
            print("\n[SCIENCE_MODE]\n" + json.dumps(vals.get("science_mode", False), ensure_ascii=False, indent=2))
            print("\n[TSUNDERE_INTENSITY]\n" + json.dumps(vals.get("tsundere_intensity", 0.5), ensure_ascii=False, indent=2))
            print("\n[OOC_DETECTOR]\n" + json.dumps(vals.get("ooc_detector", {}), ensure_ascii=False, indent=2))
            print("\n[CANON_GUARD]\n" + json.dumps(vals.get("canon_guard", {}), ensure_ascii=False, indent=2))
            continue

        if user.lower() == "/appraisal":
            cur = graph.get_state(
                {"configurable": {"thread_id": config["configurable"]["thread_id"]}}
            )
            vals = getattr(cur, "values", {}) if cur is not None else {}
            if not isinstance(vals, dict):
                vals = {}
            _print_turn_appraisal(vals)
            continue

        if user.lower() in {"/agenda", "/queue"}:
            cur = graph.get_state(
                {"configurable": {"thread_id": config["configurable"]["thread_id"]}}
            )
            vals = getattr(cur, "values", {}) if cur is not None else {}
            if not isinstance(vals, dict):
                vals = {}
            queue_vals = vals.get("behavior_queue", vals.get("behavior_agenda", []))
            _print_behavior_queue_summary(queue_vals)
            print("\n[BEHAVIOR_QUEUE]\n" + json.dumps(queue_vals, ensure_ascii=False, indent=2))
            continue

        if user.lower() in {"/events", "/event_list"}:
            rows = list_event_seed_rows()
            print("\n[EVENT_SEEDS]")
            if not rows:
                print("- (empty)")
            else:
                for row in rows:
                    print(row)
            sense_rows = list_sense_rows()
            print("\n[SENSE_SHORTCUTS]")
            if not sense_rows:
                print("- (empty)")
            else:
                for row in sense_rows:
                    print(row)
            continue

        if user.lower() in {"/senses", "/sense_list"}:
            rows = list_sense_rows()
            print("\n[SENSE_SHORTCUTS]")
            if not rows:
                print("- (empty)")
            else:
                for row in rows:
                    print(row)
            continue

        if user.lower().startswith("/event "):
            raw = user[len("/event ") :].strip()
            note_override = ""
            if "|" in raw:
                left, right = raw.split("|", 1)
                raw = left.strip()
                note_override = right.strip()
            seed_id = raw.strip()
            if not seed_id:
                print("用法：/event <seed_id> [| note]")
                continue

            built = build_seed_event(seed_id, note_override=note_override, now_ts=int(time.time()))
            if built is None:
                print(f"\n[event] 未找到事件种子：{seed_id}")
                continue
            resolved_seed_id, payload_event = built

            run_config, pending_checkpoint_id = _build_run_config(config, pending_checkpoint_id)
            after_values, final_text = _invoke_event_round(
                graph=graph,
                run_config=run_config,
                event_payload={"event_override": payload_event},
                transient_label="event",
            )
            if not after_values:
                continue

            behavior_action = after_values.get("behavior_action") if isinstance(after_values.get("behavior_action"), dict) else {}
            behavior_plan = after_values.get("behavior_plan") if isinstance(after_values.get("behavior_plan"), dict) else {}
            current_event = after_values.get("current_event") if isinstance(after_values.get("current_event"), dict) else {}
            evolution_summary = _build_event_evolution_summary(memory_store, after_values)

            print(
                "\n[event]"
                + f" seed={resolved_seed_id}"
                + "\n[BEHAVIOR_ACTION]\n"
                + json.dumps(behavior_action, ensure_ascii=False, indent=2)
            )
            _print_event_evolution_summary(evolution_summary, detailed=True)
            _print_turn_appraisal(after_values)
            if behavior_plan:
                print("\n[BEHAVIOR_PLAN]\n" + json.dumps(behavior_plan, ensure_ascii=False, indent=2))
            if current_event:
                print("\n[CURRENT_EVENT]\n" + json.dumps(current_event, ensure_ascii=False, indent=2))
            if final_text:
                print("\nAmadeus> " + final_text)
                emotion_label = str(
                    (
                        after_values.get("emotion_state")
                        if isinstance(after_values.get("emotion_state"), dict)
                        else {}
                    ).get("label")
                    or "neutral"
                )
                _speak_text_realtime(
                    text=final_text,
                    emotion_label=emotion_label,
                    enabled=tts_enabled,
                    ref_audio=tts_ref_audio,
                )
            else:
                print("\nAmadeus> （这轮她选择先不主动开口。）")
            last_conversation_touch_ts = int(time.time())
            continue

        if user.lower().startswith("/sense "):
            raw = user[len("/sense ") :].strip()
            note_override = ""
            if "|" in raw:
                left, right = raw.split("|", 1)
                raw = left.strip()
                note_override = right.strip()
            sense_ref = raw.strip()
            if not sense_ref:
                print("用法：/sense <ref> [| note]")
                continue

            try:
                resolved_ref, payload_event = build_sense_event(
                    sense_ref,
                    note_override=note_override,
                    now_ts=int(time.time()),
                )
            except ValueError as exc:
                print(f"\n[sense] {exc}")
                continue

            run_config, pending_checkpoint_id = _build_run_config(config, pending_checkpoint_id)
            after_values, final_text = _invoke_event_round(
                graph=graph,
                run_config=run_config,
                event_payload={"event_override": payload_event},
                transient_label="sense",
            )
            if not after_values:
                continue

            behavior_action = after_values.get("behavior_action") if isinstance(after_values.get("behavior_action"), dict) else {}
            behavior_plan = after_values.get("behavior_plan") if isinstance(after_values.get("behavior_plan"), dict) else {}
            current_event = after_values.get("current_event") if isinstance(after_values.get("current_event"), dict) else {}
            evolution_summary = _build_event_evolution_summary(memory_store, after_values)

            print(
                "\n[sense]"
                + f" ref={resolved_ref}"
                + "\n[BEHAVIOR_ACTION]\n"
                + json.dumps(behavior_action, ensure_ascii=False, indent=2)
            )
            _print_event_evolution_summary(evolution_summary, detailed=True)
            _print_turn_appraisal(after_values)
            if behavior_plan:
                print("\n[BEHAVIOR_PLAN]\n" + json.dumps(behavior_plan, ensure_ascii=False, indent=2))
            if current_event:
                print("\n[CURRENT_EVENT]\n" + json.dumps(current_event, ensure_ascii=False, indent=2))
            if final_text:
                print("\nAmadeus> " + final_text)
                emotion_label = str(
                    (
                        after_values.get("emotion_state")
                        if isinstance(after_values.get("emotion_state"), dict)
                        else {}
                    ).get("label")
                    or "neutral"
                )
                _speak_text_realtime(
                    text=final_text,
                    emotion_label=emotion_label,
                    enabled=tts_enabled,
                    ref_audio=tts_ref_audio,
                )
            else:
                print("\nAmadeus> （这轮她选择先不主动开口。）")
            last_conversation_touch_ts = int(time.time())
            continue

        if user.lower().startswith("/pulse"):
            raw = user[len("/pulse") :].strip()
            note_override = ""
            if "|" in raw:
                left, right = raw.split("|", 1)
                raw = left.strip()
                note_override = right.strip()

            total_minutes = 60
            step_minutes = 15
            if raw:
                parts = [part for part in raw.split() if part.strip()]
                if len(parts) >= 1:
                    try:
                        total_minutes = max(1, min(24 * 60, int(parts[0])))
                    except Exception:
                        print("用法：/pulse [total_minutes] [step_minutes] [| note]")
                        continue
                if len(parts) >= 2:
                    try:
                        step_minutes = max(1, min(total_minutes, int(parts[1])))
                    except Exception:
                        print("用法：/pulse [total_minutes] [step_minutes] [| note]")
                        continue
                elif total_minutes < step_minutes:
                    step_minutes = total_minutes

            rounds = max(1, int(math.ceil(total_minutes / float(max(1, step_minutes)))))
            print(
                "\n[pulse]"
                + f" total={total_minutes}min"
                + f" step={step_minutes}min"
                + f" rounds={rounds}"
            )

            run_config, pending_checkpoint_id = _build_run_config(config, pending_checkpoint_id)
            spoken_rounds = 0
            silence_rounds = 0
            elapsed_minutes = 0
            last_spoken_signature = ""
            last_evolution_summary: dict[str, object] | None = None

            for idx in range(rounds):
                remaining = max(0, total_minutes - elapsed_minutes)
                current_step = step_minutes if idx < rounds - 1 else max(1, remaining)
                elapsed_minutes += current_step
                event_text = note_override or f"已经安静地过去了 {elapsed_minutes} 分钟，没有新的用户消息。"
                idle_payload = {
                    "event_override": {
                        "kind": "time_idle",
                        "source": "time",
                        "text": event_text,
                        "effective_text": event_text,
                        "semantic_goal": "time passed without new user input",
                        "response_style_hint": "companion",
                        "event_frame": f"和对方之间安静地过去了 {elapsed_minutes} 分钟，现在轮到她决定是否主动开口。",
                        "tags": ["time_idle", "ambient", "behavior_layer", "pulse"],
                        "idle_minutes": elapsed_minutes,
                        "created_at": int(time.time()),
                    }
                }
                after_values, final_text = _invoke_event_round(
                    graph=graph,
                    run_config=run_config,
                    event_payload=idle_payload,
                    transient_label="pulse",
                )
                if not after_values:
                    break

                behavior_action = after_values.get("behavior_action") if isinstance(after_values.get("behavior_action"), dict) else {}
                behavior_plan = after_values.get("behavior_plan") if isinstance(after_values.get("behavior_plan"), dict) else {}
                evolution_summary = _build_event_evolution_summary(memory_store, after_values)
                last_evolution_summary = evolution_summary
                line = _behavior_action_compact_line(behavior_action)
                print(f"- round={idx + 1}/{rounds} elapsed={elapsed_minutes}min | {line}")
                _print_event_evolution_summary(evolution_summary, prefix="  ", detailed=False)
                _print_turn_appraisal(after_values, prefix="  ")
                if behavior_plan:
                    print("  plan=" + json.dumps(behavior_plan, ensure_ascii=False))

                if final_text:
                    normalized_text = re.sub(r"\s+", "", final_text).strip()
                    signature = normalized_text + "||" + json.dumps(
                        {
                            "interaction_mode": behavior_action.get("interaction_mode"),
                            "action_target": behavior_action.get("action_target"),
                            "channel": behavior_action.get("channel"),
                            "approach_style": behavior_action.get("approach_style"),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    if last_spoken_signature and signature == last_spoken_signature:
                        print("  [pulse] 检测到重复主动开口，提前停止连续推进。")
                        break
                    last_spoken_signature = signature
                    spoken_rounds += 1
                    print("  Amadeus> " + final_text)
                    emotion_label = str(
                        (
                            after_values.get("emotion_state")
                            if isinstance(after_values.get("emotion_state"), dict)
                            else {}
                        ).get("label")
                        or "neutral"
                    )
                    _speak_text_realtime(
                        text=final_text,
                        emotion_label=emotion_label,
                        enabled=tts_enabled,
                        ref_audio=tts_ref_audio,
                    )
                else:
                    silence_rounds += 1
                    print("  Amadeus> （这轮她选择先不主动开口。）")

            print(
                "[pulse][summary] spoken_rounds="
                + str(spoken_rounds)
                + " | silence_rounds="
                + str(silence_rounds)
                + " | total_elapsed="
                + str(elapsed_minutes)
                + "min"
            )
            if isinstance(last_evolution_summary, dict):
                _print_event_evolution_summary(last_evolution_summary, detailed=True, label="PULSE_FINAL_EVOLUTION")
            last_conversation_touch_ts = int(time.time())
            continue

        if user.lower().startswith("/idle"):
            raw = user[len("/idle") :].strip()
            idle_minutes = 30
            idle_note = ""
            if raw:
                if "|" in raw:
                    left, right = raw.split("|", 1)
                    raw = left.strip()
                    idle_note = right.strip()
                if raw:
                    try:
                        idle_minutes = max(1, min(24 * 60, int(raw)))
                    except Exception:
                        idle_note = (raw + (" | " + idle_note if idle_note else "")).strip()
                        idle_minutes = 30

            event_text = idle_note or f"已经安静地过去了 {idle_minutes} 分钟，没有新的用户消息。"
            idle_payload = {
                "event_override": {
                    "kind": "time_idle",
                    "source": "time",
                    "text": event_text,
                    "effective_text": event_text,
                    "semantic_goal": "time passed without new user input",
                    "response_style_hint": "companion",
                    "event_frame": f"和对方之间安静地过去了 {idle_minutes} 分钟，现在轮到她决定是否主动开口。",
                    "tags": ["time_idle", "ambient", "behavior_layer"],
                    "idle_minutes": idle_minutes,
                    "created_at": int(time.time()),
                }
            }

            run_config, pending_checkpoint_id = _build_run_config(config, pending_checkpoint_id)
            after_values, final_text = _invoke_event_round(
                graph=graph,
                run_config=run_config,
                event_payload=idle_payload,
                transient_label="idle",
            )
            if not after_values:
                continue

            behavior_action = after_values.get("behavior_action") if isinstance(after_values.get("behavior_action"), dict) else {}
            current_event = after_values.get("current_event") if isinstance(after_values.get("current_event"), dict) else {}
            evolution_summary = _build_event_evolution_summary(memory_store, after_values)

            print(
                "\n[idle]"
                + f" minutes={idle_minutes}"
                + "\n[BEHAVIOR_ACTION]\n"
                + json.dumps(behavior_action, ensure_ascii=False, indent=2)
            )
            _print_event_evolution_summary(evolution_summary, detailed=True)
            _print_turn_appraisal(after_values)
            if current_event:
                print("\n[CURRENT_EVENT]\n" + json.dumps(current_event, ensure_ascii=False, indent=2))
            if final_text:
                print("\nAmadeus> " + final_text)
                emotion_label = str(
                    (
                        after_values.get("emotion_state")
                        if isinstance(after_values.get("emotion_state"), dict)
                        else {}
                    ).get("label")
                    or "neutral"
                )
                _speak_text_realtime(
                    text=final_text,
                    emotion_label=emotion_label,
                    enabled=tts_enabled,
                    ref_audio=tts_ref_audio,
                )
            else:
                print("\nAmadeus> （这轮她选择先不主动开口。）")
            last_conversation_touch_ts = int(time.time())
            continue

        if user.lower().startswith("/tts"):
            # /tts on|off|status
            parts = user.split(maxsplit=1)
            arg = parts[1].strip().lower() if len(parts) >= 2 else "status"
            if arg in {"on", "1", "true"}:
                tts_enabled = True
                print("\n[TTS] 已开启")
            elif arg in {"off", "0", "false"}:
                tts_enabled = False
                print("\n[TTS] 已关闭")
            else:
                print(
                    "\n[TTS] status="
                    + ("on" if tts_enabled else "off")
                    + "\n  backend=dashscope_realtime"
                    + "\n  ref_audio="
                    + (tts_ref_audio or "(empty)")
                    + "\n  ref_text="
                    + ((tts_ref_text[:60] + "...") if len(tts_ref_text) > 60 else (tts_ref_text or "(empty)"))
                )
            continue

        if user.lower().startswith("/tts_ref "):
            # /tts_ref path.wav
            p = user[len("/tts_ref ") :].strip().strip('"')
            if not p:
                print("用法：/tts_ref <path.wav>")
                continue
            tts_ref_audio = p
            print("\n[TTS] ref_audio 已设置")
            continue

        if user.lower().startswith("/tts_ref_text "):
            # /tts_ref_text <日本語の文字起こし>
            t = user[len("/tts_ref_text ") :].strip()
            if not t:
                print("用法：/tts_ref_text <ref_text>")
                continue
            tts_ref_text = t
            print("\n[TTS] ref_text 已设置")
            continue

        if user.lower().startswith("/correct "):
            # /correct key=value [| reason]
            # 目的：提供一个“记忆纠错协议”入口；比 /forget + /set 更像“她记错了->你纠正->她改”。
            raw = user[len("/correct ") :].strip()
            if "|" in raw:
                kv, reason = raw.split("|", 1)
                reason = reason.strip()
            else:
                kv, reason = raw, ""
            if "=" not in kv:
                print("用法：/correct key=value [| reason]")
                continue
            k, v = kv.split("=", 1)
            k = k.strip()
            v = v.strip()
            if not k:
                print("用法：/correct key=value [| reason]")
                continue

            old = memory_store.get_profile().get(k)
            print("\n[memory correction]")
            print("- key=" + str(k))
            print("- old=" + json.dumps(old, ensure_ascii=False))
            print("- new=" + json.dumps(v, ensure_ascii=False))
            if reason:
                print("- reason=" + reason)

            ans = input("  确认覆盖并写入 meta? (y/N) > ").strip().lower()
            if ans != "y":
                print("已取消")
                continue

            try:
                memory_store.set_profile(k, v)
                memory_store.set_profile_meta(
                    k,
                    {
                        "source": "user_correction",
                        "old_value": old,
                        "new_value": v,
                        "reason": reason,
                        "corrected_at": int(time.time()),
                        "confirmed_by": "user",
                    },
                )
                print(f"已纠正 profile.{k}")
            except Exception as e:
                print("写入失败：" + str(e))
            continue

        if user.lower().startswith("/undo "):
            # /undo key [| reason]
            raw = user[len("/undo ") :].strip()
            if "|" in raw:
                k, reason = raw.split("|", 1)
                k = k.strip()
                reason = reason.strip()
            else:
                k, reason = raw.strip(), ""

            if not k:
                print("用法：/undo key [| reason]")
                continue
            if not reason:
                reason = "user requested undo"

            meta = (memory_store.get_profile_meta() or {}).get(k)
            if not isinstance(meta, dict):
                print("未找到该 key 的 meta，无法自动撤销。")
                continue
            if ("old_value" not in meta) or ("new_value" not in meta):
                print("meta 缺少 old_value/new_value，无法自动撤销。")
                continue

            cur = memory_store.get_profile().get(k)
            if cur != meta.get("new_value"):
                print("当前值与 meta.new_value 不一致，拒绝自动撤销（避免误操作）。")
                print("- current=" + json.dumps(cur, ensure_ascii=False))
                print("- meta.new_value=" + json.dumps(meta.get("new_value"), ensure_ascii=False))
                continue

            old_v = meta.get("old_value")
            print("\n[undo correction]")
            print("- key=" + str(k))
            print("- revert_to(old_value)=" + json.dumps(old_v, ensure_ascii=False))
            print("- reason=" + reason)
            ans = input("  确认撤销? (y/N) > ").strip().lower()
            if ans != "y":
                print("已取消")
                continue

            try:
                memory_store.set_profile(k, old_v)
                memory_store.set_profile_meta(
                    k,
                    {
                        "source": "undo_correction",
                        "undone_at": int(time.time()),
                        "reason": reason,
                        "reverted_from": meta.get("new_value"),
                        "reverted_to": old_v,
                        "prev_meta": meta,
                        "confirmed_by": "user",
                    },
                )
                print(f"已撤销 profile.{k} 的上一次纠错")
            except Exception as e:
                print("撤销失败：" + str(e))
            continue

        if user.lower().startswith("/set "):
            # /set key=value  （profile默认）
            kv = user[5:].strip()
            if "=" not in kv:
                print("用法：/set key=value")
                continue
            k, v = kv.split("=", 1)
            memory_store.set_profile(k.strip(), v.strip())
            print(f"已写入 profile.{k.strip()}")
            continue
        if user.lower().startswith("/forget "):
            # /forget key （profile默认）
            k = user[8:].strip()
            if not k:
                print("用法：/forget key")
                continue
            ok = memory_store.delete_profile(k)
            print("已删除" if ok else "未找到")
            continue
        if user.lower() == "/moments":
            ms = list(reversed(memory_store.list_moments(limit=20)))
            for m in ms:
                print(f"- #{m['id']} {m['summary']}")
            continue
        if user.lower().startswith("/forget_moment "):
            raw_id = user[len("/forget_moment "):].strip()
            try:
                mid = int(raw_id)
            except Exception:
                print("用法：/forget_moment <id>")
                continue
            ok = memory_store.delete_moment(mid)
            print("已删除" if ok else "未找到")
            continue
        if user.lower() == "/reflections":
            rs = list(reversed(memory_store.list_reflections(limit=20)))
            for r in rs:
                print(f"- @{r['id']}({r.get('importance')}) {r['text']}")
            continue
        if user.lower().startswith("/forget_reflection "):
            raw_id = user[len("/forget_reflection "):].strip()
            try:
                rid = int(raw_id)
            except Exception:
                print("用法：/forget_reflection <id>")
                continue
            ok = memory_store.delete_reflection(rid)
            print("已删除" if ok else "未找到")
            continue
        if user.lower().startswith("/reflect"):
            # /reflect 或 /reflect 20
            parts = user.split()
            n = 20
            if len(parts) >= 2:
                try:
                    n = int(parts[1])
                except Exception:
                    n = 20
            n = max(5, min(200, n))

            recent = list(reversed(memory_store.list_moments(limit=n)))
            if not recent:
                print("\n没有 moments，无法生成反思。")
                continue

            llm = build_chat_model(temperature=0.2)

            prompt = (
                "你是记忆反思器(reflection generator)。给定一组按时间排序的 moments，请总结出 1~6 条‘长期规律/稳定结论’。\n"
                "要求：\n"
                "- 反思应尽量稳定：偏好、禁忌、沟通方式、关系边界、长期目标等；不要总结一次性事件细节。\n"
                "- 每条反思尽量短（10~40字），可作为长期记忆注入。\n"
                "- 给出 derived_from：支撑该反思的 moment id 列表（1~10个）。\n"
                "- 给出 importance：0~1。越重要越高。\n"
                "- 只输出严格 JSON 数组，不要任何多余文字。\n"
                "输出格式：[{\"text\": str, \"derived_from\": [int,...], \"importance\": 0~1}, ...]\n"
                f"moments：{json.dumps([{ 'id': m['id'], 'summary': m['summary'] } for m in recent], ensure_ascii=False)}\n"
            )

            raw = llm.invoke([SystemMessage(content=prompt)])
            data = None
            for attempt in (1, 2):
                try:
                    data = json.loads(getattr(raw, "content", "") or "")
                    break
                except Exception:
                    if attempt == 1:
                        raw = llm.invoke(
                            [
                                SystemMessage(
                                    content=prompt
                                    + "\n【重试】只输出 JSON 数组，不得包含 Markdown 代码块/解释文字。"
                                )
                            ]
                        )
                        continue
                    data = None

            if not isinstance(data, list) or not data:
                print("\n反思生成失败（未得到合法 JSON 数组）。")
                continue

            print("\n[reflect proposals]")
            wrote = 0
            for it in data[:6]:
                if not isinstance(it, dict):
                    continue
                text = str(it.get("text") or "").strip()
                if not text:
                    continue
                derived_from = it.get("derived_from") or []
                importance = it.get("importance")
                print(
                    "- text="
                    + text
                    + "\n  derived_from="
                    + json.dumps(derived_from, ensure_ascii=False)
                    + " importance="
                    + str(importance)
                )
                ans = input("  写入这条 reflection? (y/N) > ").strip().lower()
                if ans != "y":
                    continue
                try:
                    rid = memory_store.add_reflection(text=text, derived_from=derived_from, importance=importance)
                    wrote += 1
                except Exception as e:
                    print("  写入失败：" + str(e))
                    continue

                # 可选：写回 profile.user_model_rules，形成 L3 -> L1 的闭环
                ans2 = input("  同时写入 profile.user_model_rules? (y/N) > ").strip().lower()
                if ans2 == "y":
                    try:
                        rule = {
                            "text": text,
                            "importance": importance,
                            "derived_from": derived_from,
                            "reflection_id": rid,
                            "created_at": int(time.time()),
                        }
                        old = memory_store.get_profile().get("user_model_rules")
                        merged = []
                        if isinstance(old, list):
                            merged = [*old]
                        merged.append(rule)
                        # 轻量去重：按 text 去重
                        seen = set()
                        uniq = []
                        for it2 in merged:
                            t2 = str((it2 or {}).get("text") if isinstance(it2, dict) else it2).strip()
                            if not t2 or t2 in seen:
                                continue
                            seen.add(t2)
                            uniq.append(it2)
                        memory_store.set_profile("user_model_rules", uniq[:50])
                        memory_store.set_profile_meta(
                            "user_model_rules",
                            {
                                "source": "reflect_batch",
                                "last_confirmed_at": int(time.time()),
                                "note": "derived from reflections",
                            },
                        )
                    except Exception as e:
                        print("  写回 profile 失败：" + str(e))

            print(f"\n已写入 {wrote} 条 reflections。")
            continue

        run_config = config
        if pending_checkpoint_id:
            run_config = {
                "configurable": {
                    "thread_id": config["configurable"]["thread_id"],
                    "user_id": config["configurable"].get("user_id"),
                    "checkpoint_id": pending_checkpoint_id,
                }
            }
            # 只对下一次生效，避免一直从同一个checkpoint反复分叉
            pending_checkpoint_id = None

        def _invoke_stream(payload, cfg, on_text=None):
            """基于 LangGraph streaming 的最小流式输出：只流式打印 call_model 节点产出的 AIMessageChunk。

            同时提供 on_text 回调：每个 token chunk 到来时回调，便于做“边生成边TTS”。
            """
            last_values = None
            buf = ""
            for mode, chunk in graph.stream(payload, config=cfg, stream_mode=["messages", "values"]):
                if mode == "values":
                    last_values = chunk
                    continue
                if mode != "messages":
                    continue

                msg, meta = chunk
                if (meta or {}).get("langgraph_node") != "call_model":
                    continue

                # 只打印 token chunk，避免最终完整消息重复输出
                if not type(msg).__name__.endswith("Chunk"):
                    continue
                text = getattr(msg, "content", "") or ""
                if not text:
                    continue

                buf += text
                if callable(on_text):
                    try:
                        on_text(text)
                    except Exception:
                        pass

            # Console output is rendered from the final message only.
            # This avoids showing draft + rewritten text mixed together.
            return last_values or {}, False, buf

        # 按官方示例：使用 DashScope Realtime，把文本 append_text 给服务端，服务端流式返回 audio.delta。
        tts_out_dir = (get_settings().data_dir / "tts_out")
        backend = str(os.getenv("AMADEUS_TTS_BACKEND", "dashscope_realtime") or "dashscope_realtime").strip().strip('"').lower()

        rt = None
        emotion_label = "neutral"
        try:
            cur = graph.get_state(
                {"configurable": {"thread_id": run_config["configurable"]["thread_id"]}}
            )
            vals = getattr(cur, "values", {}) if cur is not None else {}
            if isinstance(vals, dict) and isinstance(vals.get("emotion_state"), dict):
                emotion_label = str((vals.get("emotion_state") or {}).get("label") or "neutral")
        except Exception:
            emotion_label = "neutral"
        tts_profile = emotion_to_tts_profile(emotion_label)

        tts_round_enabled = bool(tts_enabled)
        if tts_round_enabled:
            tts_warn = ""
            if backend not in {"dashscope_realtime", "dashscope"}:
                tts_warn = "TTS backend must be dashscope_realtime"
            elif not tts_ref_audio:
                tts_warn = "AMADEUS_TTS_REF_AUDIO is required for dashscope enrollment"
            else:
                try:
                    # 关闭底层 SDK/websocket 在 stdout/stderr 的噪音输出（例如 1000 Bye），避免打断 CLI 输入行。
                    _noise = io.StringIO()
                    with redirect_stdout(_noise), redirect_stderr(_noise):
                        rt = create_dashscope_realtime_session(
                            ref_audio=tts_ref_audio,
                            out_dir=tts_out_dir,
                            play_audio=True,
                        )
                except Exception as e:
                    tts_warn = f"realtime init failed: {e}"
                    rt = None
            if tts_warn:
                print("\n[TTS][warn] " + tts_warn + " -> fallback=text-only")

        # 官方示例在 append_text 之间会 sleep 一小段时间；
        # 这里如果按 token 粒度“毫秒级狂发”，容易导致服务端来不及产出音频或连接不稳定。
        try:
            if pending_checkpoint_id is None:
                _apply_implicit_idle_maturation(
                    graph=graph,
                    run_config=run_config,
                    last_conversation_touch_ts=last_conversation_touch_ts,
                )
            out, streamed, streamed_text = _invoke_stream(
                {"messages": [{"role": "user", "content": user}]},
                cfg=run_config,
                on_text=None,
            )
        except Exception as e:
            if _is_transient_runtime_error(e):
                print("\n[network][warn] 远端模型连接中断，本轮未完成。请直接重试刚才那条输入。")
                continue
            raise

        # 工具调用 HITL：一个回合里可能出现多次 interrupt（例如：先审批记忆写入，再审批对话工具）
        while out.get("__interrupt__"):
            intr = out["__interrupt__"][0]
            payload = getattr(intr, "value", None)
            if payload is None and isinstance(intr, dict):
                payload = intr.get("value")
            payload = payload or {}
            if payload.get("kind") != "tool_approval":
                break

            tool_calls = payload.get("tool_calls", [])
            payload_source = str(payload.get("source") or "").strip().lower()
            if isinstance(payload, dict) and _should_auto_resume_memory_approval(payload):
                decisions = [{"action": "approve"} for _ in tool_calls] if isinstance(tool_calls, list) else []
                out, streamed, streamed_text = _invoke_stream(
                    Command(resume={"decisions": decisions}),
                    cfg={"configurable": {"thread_id": run_config["configurable"]["thread_id"]}},
                    on_text=None,
                )
                continue
            show_approval_logs = not (bool(HIDE_TOOL_APPROVAL_LOGS) and payload_source == "memory")
            # 防线：避免一次 interrupt 里出现过多调用导致刷屏/误批。
            max_calls = int(TOOL_CALLS_MAX)
            if max_calls <= 0:
                max_calls = 12
            if isinstance(tool_calls, list) and len(tool_calls) > max_calls:
                if show_approval_logs:
                    print(f"\n[warn] tool_calls too many ({len(tool_calls)}), only showing first {max_calls}")
                tool_calls = tool_calls[:max_calls]
            decisions = []
            if show_approval_logs:
                print("\n[需要审批的工具调用]")

            risky_profile_keys = {
                "nickname",
                "timezone",
                "likes",
                "dislikes",
                "persona_rules",
                "user_model_rules",
            }

            for tc in tool_calls:
                name = str(tc.get("name") or "")
                args = tc.get("args") or {}

                # 更可读的审批信息：把证据链(meta)单独打印出来
                if show_approval_logs:
                    print("- tool=" + str(name))
                if name == "request_toolset_upgrade" and isinstance(args, dict):
                    try:
                        req_tools = args.get("requested_tools")
                        rsn = args.get("reason")
                        if isinstance(req_tools, list):
                            if show_approval_logs:
                                print("  requested_tools=" + json.dumps(req_tools, ensure_ascii=False))
                        if isinstance(rsn, str) and rsn.strip():
                            if show_approval_logs:
                                print("  reason=" + rsn.strip())
                        if show_approval_logs:
                            print(
                                "  note=approve 将临时解锁上述工具，预计有效期约 "
                                + str(int(TOOLSET_UPGRADE_TTL_S))
                                + "s"
                            )
                    except Exception:
                        pass
                try:
                    if isinstance(args, dict) and isinstance(args.get("meta"), dict):
                        meta = args.get("meta") or {}
                        meta_preview = {
                            "source_text": meta.get("source_text"),
                            "confidence": meta.get("confidence"),
                            "extracted_at": meta.get("extracted_at"),
                            "confirmed_by": meta.get("confirmed_by"),
                        }
                        # 避免 meta 过长刷屏
                        if isinstance(meta_preview.get("source_text"), str) and len(meta_preview["source_text"]) > 200:
                            meta_preview["source_text"] = meta_preview["source_text"][:200] + "..."
                        if show_approval_logs:
                            print("  meta=" + json.dumps(meta_preview, ensure_ascii=False))
                except Exception:
                    pass
                if show_approval_logs:
                    print("  args=" + json.dumps(args, ensure_ascii=False))

                action = input("  选择 a=approve / e=edit / r=reject > ").strip().lower() or "r"

                # 记忆写入二次确认：
                # - 仅针对 memory 提案（source=memory）
                # - set_profile：高风险字段 or overwrite 才二次确认
                # - correct_profile：纠错/覆盖写本身就高风险，默认一律二次确认
                need_second_confirm = False
                try:
                    if payload_source == "memory" and name in {"set_profile", "correct_profile", "undo_profile_correction"} and isinstance(args, dict):
                        k = str(args.get("key") or "").strip()
                        if name in {"correct_profile", "undo_profile_correction"}:
                            need_second_confirm = True
                        else:
                            mode = str(args.get("mode") or "merge").strip().lower()
                            if (k in risky_profile_keys) or (mode == "overwrite"):
                                need_second_confirm = True
                except Exception:
                    need_second_confirm = False

                if action == "a":
                    if need_second_confirm:
                        ans2 = input("  二次确认：输入 y 才会写入长期记忆 > ").strip().lower()
                        if ans2 != "y":
                            decisions.append({"action": "reject", "reason": "second confirm failed"})
                            continue
                    decisions.append({"action": "approve"})
                elif action == "e":
                    raw = input("  输入新的 args(JSON) > ").strip()
                    try:
                        new_args = json.loads(raw)
                    except Exception:
                        print("  JSON 解析失败，按 reject 处理")
                        decisions.append({"action": "reject", "reason": "bad json"})
                        continue
                    # edit 也可能涉及高风险覆盖，仍要求二次确认（以 new_args 为准）
                    try:
                        if payload_source == "memory" and name in {"set_profile", "correct_profile", "undo_profile_correction"} and isinstance(new_args, dict):
                            k = str(new_args.get("key") or "").strip()
                            need_second = False
                            if name in {"correct_profile", "undo_profile_correction"}:
                                need_second = True
                            else:
                                mode = str(new_args.get("mode") or "merge").strip().lower()
                                if (k in risky_profile_keys) or (mode == "overwrite"):
                                    need_second = True
                            if need_second:
                                ans2 = input("  二次确认(edit)：输入 y 才会写入长期记忆 > ").strip().lower()
                                if ans2 != "y":
                                    decisions.append({"action": "reject", "reason": "second confirm failed"})
                                    continue
                    except Exception:
                        pass
                    decisions.append({"action": "edit", "args": new_args})
                else:
                    reason = input("  reject 原因(可空) > ").strip() or "rejected"
                    decisions.append({"action": "reject", "reason": reason})

            out, streamed, streamed_text = _invoke_stream(
                Command(resume={"decisions": decisions}),
                cfg={"configurable": {"thread_id": run_config["configurable"]["thread_id"]}},
                on_text=None,
            )

        # out["messages"] 是完整消息列表，最后一条是刚生成的 AIMessage/ToolMessage
        final_text = ""
        try:
            msgs = out.get("messages") if isinstance(out, dict) else None
            if isinstance(msgs, list) and msgs:
                last_msg = msgs[-1]
                final_text = str(getattr(last_msg, "content", "") or "")
        except Exception:
            final_text = ""

        if (not final_text.strip()) and streamed:
            final_text = (streamed_text or "").strip()

        if not streamed:
            print(f"\nAmadeus> {final_text}")
        if _cli_show_turn_summary_enabled() and isinstance(out, dict):
            turn_summary = _build_event_evolution_summary(memory_store, out)
            _print_event_evolution_summary(turn_summary, detailed=False, label="TURN_EVOLUTION")

        # TTS 收尾：必须等“工具审批/执行结束后的最终回复”出来再 finish，否则有工具调用时会没声音。
        if tts_enabled and rt is not None:
            tts_plan = None
            tts_push_error = None
            try:
                if final_text.strip():
                    tts_plan = push_tts_segments(
                        rt,
                        text=final_text.strip(),
                        emotion_label=emotion_label,
                        sleep_fn=time.sleep,
                    )
            except Exception as e:
                tts_push_error = e

            _noise = io.StringIO()
            with redirect_stdout(_noise), redirect_stderr(_noise):
                rt.finish_and_wait()
            if rt.total_audio_bytes <= 0:
                print("[TTS-RT][warn] received 0 audio bytes (check API key/model/ws url & callback logs)")
            if tts_push_error is not None:
                print("[TTS-RT][warn] append failed: " + str(tts_push_error))
            if isinstance(tts_plan, dict):
                print(
                    "[TTS-RT] emotion="
                    + str(tts_plan.get("emotion_label") or emotion_label)
                    + " | segments="
                    + str(int(tts_plan.get("segment_count") or 0))
                    + " | chars="
                    + str(int(tts_plan.get("char_count") or 0))
                    + " | interval="
                    + str(tts_profile.get("min_interval"))
                )
            if rt.first_audio_delay is not None:
                print(f"\n[TTS-RT] first_audio_delay={rt.first_audio_delay:.2f}s")
            print("[TTS-RT] saved: " + str(rt.out_path))

        # 旧的“整段回复后再 TTS”路径已被“流式异步 TTS”替代（更低首包出声 + 更连贯）。
        # 回退：设 AMADEUS_TTS_STREAM=0。

        # 记忆写入已统一通过工具调用 + interrupt 审批执行，这里不再在 CLI 直接写库。
        last_conversation_touch_ts = int(time.time())


if __name__ == "__main__":
    main()
