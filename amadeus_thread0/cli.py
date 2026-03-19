from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
import warnings
from contextlib import redirect_stderr, redirect_stdout
from functools import partial
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
from .config import (
    AUTO_APPROVE_MEMORY_WRITES,
    HIDE_TOOL_APPROVAL_LOGS,
    TOOL_CALLS_MAX,
    TOOLSET_UPGRADE_TTL_S,
    USER_FACING_MODE,
)
from .utils.cli_views import build_evolution_summary_line, render_behavior_queue_cli_text
from .runtime.memory_admin import MemoryAdminError
from .runtime.modeling import runtime_model_summary
from .runtime.runtime_bundle import RuntimeBundle
from .runtime.thread_runtime import (
    apply_worldline_runtime_paths as _apply_worldline_runtime_paths,
    has_explicit_runtime_path_overrides as _has_explicit_runtime_path_overrides,
    resolve_startup_thread_id as _resolve_startup_thread_id,
    shared_runtime_artifacts as _shared_runtime_artifacts,
    should_isolate_startup_runtime as _should_isolate_startup_runtime,
    should_warn_shared_default_runtime as _should_warn_shared_default_runtime,
)
from .runtime.tool_approval import (
    auto_approve_decisions,
    needs_second_confirmation,
    should_auto_resume_memory_approval,
    summarize_tool_approval_request,
)
from .utils.perception_events import (
    build_seed_event,
    build_sense_event,
    list_event_seed_rows,
    list_sense_rows,
)
from .utils.runtime_audit import render_runtime_audit_report
from .runtime.session_orchestrator import emotion_to_tts_profile, push_tts_segments
from .runtime.settings import configure_runtime_environment, get_settings
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


_AUTO_RESUME_MEMORY_APPROVAL = partial(
    should_auto_resume_memory_approval,
    user_facing_mode=bool(USER_FACING_MODE),
    auto_approve_memory_writes=bool(AUTO_APPROVE_MEMORY_WRITES),
)


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
    motive = str(action.get("primary_motive") or "").strip() or "-"
    channel = str(action.get("channel") or "").strip() or "-"
    style = str(action.get("approach_style") or "").strip() or "-"
    return f"mode={mode} | target={target} | motive={motive} | channel={channel} | style={style}"

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


def _print_event_round_payload(
    *,
    header_label: str,
    header_value: str,
    payload: dict[str, object] | None,
    tts_enabled: bool,
    tts_ref_audio: str,
) -> None:
    data = payload if isinstance(payload, dict) else {}
    behavior_action = data.get("behavior_action") if isinstance(data.get("behavior_action"), dict) else {}
    behavior_plan = data.get("behavior_plan") if isinstance(data.get("behavior_plan"), dict) else {}
    current_event = data.get("current_event") if isinstance(data.get("current_event"), dict) else {}
    turn_summary = data.get("turn_summary") if isinstance(data.get("turn_summary"), dict) else {}
    turn_appraisal = data.get("turn_appraisal") if isinstance(data.get("turn_appraisal"), dict) else {}
    final_text = str(data.get("final_text") or "").strip()
    emotion_label = str(data.get("emotion_label") or "neutral").strip() or "neutral"

    print(
        f"\n[{header_label}]"
        + f" {header_value}"
        + "\n[BEHAVIOR_ACTION]\n"
        + json.dumps(behavior_action, ensure_ascii=False, indent=2)
    )
    _print_event_evolution_summary(turn_summary, detailed=True)
    _print_turn_appraisal({"turn_appraisal": turn_appraisal})
    if behavior_plan:
        print("\n[BEHAVIOR_PLAN]\n" + json.dumps(behavior_plan, ensure_ascii=False, indent=2))
    if current_event:
        print("\n[CURRENT_EVENT]\n" + json.dumps(current_event, ensure_ascii=False, indent=2))
    if final_text:
        print("\nAmadeus> " + final_text)
        _speak_text_realtime(
            text=final_text,
            emotion_label=emotion_label,
            enabled=tts_enabled,
            ref_audio=tts_ref_audio,
        )
    else:
        print("\nAmadeus> （这轮她选择先不主动开口。）")


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
    runtime_bundle = RuntimeBundle.create(thread_id=startup_thread_id, settings=s)
    memory_admin = runtime_bundle.memory_admin
    backend_session = runtime_bundle.backend_session
    backend_api = runtime_bundle.backend_api(base_data_dir=base_data_dir, cwd=Path.cwd())
    config = runtime_bundle.config()

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
                new_id = entered
            switch_plan = runtime_bundle.switch_thread(
                base_data_dir=base_data_dir,
                requested_thread_id=new_id,
                fallback_prefix="thread",
            )
            s = runtime_bundle.settings
            memory_admin = runtime_bundle.memory_admin
            backend_session = runtime_bundle.backend_session
            backend_api = runtime_bundle.backend_api(base_data_dir=base_data_dir, cwd=Path.cwd())
            config = runtime_bundle.config()
            # 切线程后清空 time travel 目标
            pending_checkpoint_id = None
            last_conversation_touch_ts = None
            print(f"已切换到 thread_id={switch_plan.thread_id}")
            print("[runtime] worldline_storage=" + str(switch_plan.runtime_dir))
            continue
        if user.lower() == "/threads":
            inventory = backend_api.thread_inventory().payload
            checkpoint_thread_ids = inventory.get("checkpoint_thread_ids", [])
            worldline_dir_ids = inventory.get("worldline_dir_ids", [])
            current_thread_id = inventory.get("current_thread_id")
            if not checkpoint_thread_ids:
                print("\n未在 checkpoint 数据库中找到 thread_id（可能还没有生成checkpoint）。")
            else:
                print("\n[threads]")
                for tid in checkpoint_thread_ids:
                    mark = "*" if tid == current_thread_id else " "
                    print(f"{mark} {tid}")
            if worldline_dir_ids:
                print("\n[worldline_dirs]")
                for wid in worldline_dir_ids:
                    mark = "*" if wid == current_thread_id else " "
                    print(f"{mark} {wid}")
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
            history_view = backend_api.checkpoint_history(limit=limit, config=config).payload
            rows = history_view.get("rows", [])
            total = int(history_view.get("total", 0) or 0)
            print(
                f"\n[checkpoint history] (latest first, showing {len(rows)}/{total})"
            )
            for row in rows:
                print(f"- checkpoint_id={row.get('checkpoint_id')} next={row.get('next')}")
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
            current_view = backend_api.current_checkpoint(config=config).payload
            print(
                f"\n[current] thread_id={current_view.get('thread_id')} checkpoint_id={current_view.get('checkpoint_id')}"
            )
            continue
        if user.lower() == "/runtime":
            runtime_view = backend_api.runtime_layout().payload
            print("\n[repo-runtime]")
            print(render_runtime_audit_report(runtime_view.get("repo_runtime")))
            current_runtime = runtime_view.get("current_runtime")
            if isinstance(current_runtime, dict):
                print("\n[current-runtime]")
                print(render_runtime_audit_report(current_runtime))
            continue
        if user.lower() == "/env":
            env_view = backend_api.environment_summary(cwd=Path.cwd()).payload
            print(
                "\n[env] cwd="
                + str(env_view.get("cwd"))
                + "\n  AMADEUS_MODEL_PROVIDER="
                + str(env_view.get("model_provider"))
                + "\n  AMADEUS_MODEL_NAME="
                + str(env_view.get("model_name"))
                + "\n  AMADEUS_MODEL_BASE_URL="
                + str(env_view.get("model_base_url"))
                + "\n  AMADEUS_RUNTIME_MODE="
                + str(env_view.get("runtime_mode"))
                + "\n  AMADEUS_EVAL_MODE="
                + str(env_view.get("eval_mode"))
                + "\n  AMADEUS_USER_FACING_MODE="
                + str(env_view.get("user_facing_mode"))
                + "\n  AMADEUS_CLI_SHOW_TURN_SUMMARY="
                + str(env_view.get("cli_show_turn_summary"))
                + "\n  AMADEUS_TTS_ENABLED="
                + str(env_view.get("tts_enabled"))
                + "\n  AMADEUS_TTS_BACKEND="
                + str(env_view.get("tts_backend"))
                + "\n  AMADEUS_TTS_REF_AUDIO="
                + str(env_view.get("tts_ref_audio"))
                + "\n  AMADEUS_TTS_DASHSCOPE_MODEL="
                + str(env_view.get("tts_model"))
                + "\n  DASHSCOPE_API_KEY="
                + ("(set)" if bool(env_view.get("dashscope_api_key_set")) else "(empty)")
            )
            continue
        if user.lower() == "/mem":
            snap = backend_api.memory_snapshot().payload
            print("\n[PROFILE]\n" + json.dumps(snap["profile"], ensure_ascii=False, indent=2))
            print("\n[RELATIONSHIP]\n" + json.dumps(snap["relationship"], ensure_ascii=False, indent=2))
            print("\n[MOMENTS(latest)]\n" + json.dumps(snap["moments"], ensure_ascii=False, indent=2))
            continue
        if user.lower() == "/worldline":
            worldline_view = backend_api.worldline().payload
            print("\n[WORLDLINE_SUMMARY]\n" + json.dumps(worldline_view.get("worldline_summary", {}), ensure_ascii=False, indent=2))
            print("\n[WORLDLINE_EVENTS]\n" + json.dumps(worldline_view.get("worldline_events", []), ensure_ascii=False, indent=2))
            print("\n[COMMITMENTS]\n" + json.dumps(worldline_view.get("commitments", []), ensure_ascii=False, indent=2))
            print("\n[CONFLICT_REPAIR]\n" + json.dumps(worldline_view.get("conflict_repair", []), ensure_ascii=False, indent=2))
            print("\n[UNRESOLVED_TENSIONS]\n" + json.dumps(worldline_view.get("unresolved_tensions", []), ensure_ascii=False, indent=2))
            print(
                "\n[SEMANTIC_SELF_NARRATIVES]\n"
                + json.dumps(worldline_view.get("semantic_self_narratives", []), ensure_ascii=False, indent=2)
            )
            print("\n[REVISION_TRACES]\n" + json.dumps(worldline_view.get("revision_traces", []), ensure_ascii=False, indent=2))
            continue
        if user.lower() == "/bond":
            bond_view = backend_api.bond().payload
            print("\n[RELATIONSHIP_STATE]\n" + json.dumps(bond_view.get("relationship_state", {}), ensure_ascii=False, indent=2))
            print("\n[BOND_STATE]\n" + json.dumps(bond_view.get("bond_state", {}), ensure_ascii=False, indent=2))
            print("\n[RELATIONSHIP_TIMELINE]")
            relationship_timeline = bond_view.get("relationship_timeline", [])
            if not relationship_timeline:
                print("- (empty)")
            for it in relationship_timeline:
                print(
                    f"- #{it.get('id')} {it.get('summary')} "
                    f"(aff={it.get('affinity_delta')}, trust={it.get('trust_delta')})"
                )
            print("\n[CONFLICT_REPAIR]")
            repairs = bond_view.get("conflict_repair", [])
            if not repairs:
                print("- (empty)")
            for it in repairs:
                print(f"- #{it.get('id')} {it.get('summary')}")
            continue
        if user.lower() == "/sources":
            sources_view = backend_api.sources().payload
            print("\n[SOURCES]")
            refs = sources_view.get("sources", [])
            if not refs:
                print("- (empty)")
            for it in refs:
                print(
                    f"- #{it.get('id')} [{it.get('tool_name')}] {it.get('title') or '(no title)'}\n"
                    f"  url={it.get('url')} query={it.get('query')}"
                )
            print("\n[CLAIM->SOURCES]")
            claim_links = sources_view.get("claim_links", [])
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
            persona_view = backend_api.persona().payload
            print("\n[EVOLUTION_SUMMARY]\n" + json.dumps(persona_view.get("evolution_summary", {}), ensure_ascii=False, indent=2))
            print("\n[PERSONA_STATE]\n" + json.dumps(persona_view.get("persona_state", {}), ensure_ascii=False, indent=2))
            print("\n[EMOTION_STATE]\n" + json.dumps(persona_view.get("emotion_state", {}), ensure_ascii=False, indent=2))
            print("\n[BOND_STATE]\n" + json.dumps(persona_view.get("bond_state", {}), ensure_ascii=False, indent=2))
            print("\n[ALLOSTASIS_STATE]\n" + json.dumps(persona_view.get("allostasis_state", {}), ensure_ascii=False, indent=2))
            print("\n[COUNTERPART_ASSESSMENT]\n" + json.dumps(persona_view.get("counterpart_assessment", {}), ensure_ascii=False, indent=2))
            print("\n[SEMANTIC_NARRATIVE_PROFILE]\n" + json.dumps(persona_view.get("semantic_narrative_profile", {}), ensure_ascii=False, indent=2))
            print("\n[WORLD_MODEL_STATE]\n" + json.dumps(persona_view.get("world_model_state", {}), ensure_ascii=False, indent=2))
            print("\n[EVOLUTION_STATE]\n" + json.dumps(persona_view.get("evolution_state", {}), ensure_ascii=False, indent=2))
            print("\n[RECONSOLIDATION_SNAPSHOT]\n" + json.dumps(persona_view.get("reconsolidation_snapshot", {}), ensure_ascii=False, indent=2))
            print("\n[TURN_APPRAISAL]\n" + json.dumps(persona_view.get("turn_appraisal", {}), ensure_ascii=False, indent=2))
            print("\n[BEHAVIOR_POLICY]\n" + json.dumps(persona_view.get("behavior_policy", {}), ensure_ascii=False, indent=2))
            print("\n[BEHAVIOR_ACTION]\n" + json.dumps(persona_view.get("behavior_action", {}), ensure_ascii=False, indent=2))
            print("\n[INTERACTION_CARRYOVER]\n" + json.dumps(persona_view.get("interaction_carryover", {}), ensure_ascii=False, indent=2))
            print("\n[AGENDA_LIFECYCLE_RESIDUE]\n" + json.dumps(persona_view.get("agenda_lifecycle_residue", {}), ensure_ascii=False, indent=2))
            print("\n[BEHAVIOR_PLAN]\n" + json.dumps(persona_view.get("behavior_plan", {}), ensure_ascii=False, indent=2))
            queue_vals = persona_view.get("behavior_queue", [])
            _print_behavior_queue_summary(queue_vals)
            print("\n[BEHAVIOR_QUEUE]\n" + json.dumps(queue_vals, ensure_ascii=False, indent=2))
            print("\n[SCIENCE_MODE]\n" + json.dumps(persona_view.get("science_mode", False), ensure_ascii=False, indent=2))
            print("\n[TSUNDERE_INTENSITY]\n" + json.dumps(persona_view.get("tsundere_intensity", 0.5), ensure_ascii=False, indent=2))
            print("\n[OOC_DETECTOR]\n" + json.dumps(persona_view.get("ooc_detector", {}), ensure_ascii=False, indent=2))
            print("\n[CANON_GUARD]\n" + json.dumps(persona_view.get("canon_guard", {}), ensure_ascii=False, indent=2))
            continue

        if user.lower() == "/appraisal":
            _print_turn_appraisal(backend_api.appraisal().payload)
            continue

        if user.lower() in {"/agenda", "/queue"}:
            queue_view = backend_api.behavior_queue(config=config).payload
            queue_vals = queue_view.get("behavior_queue", [])
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

            run_config, pending_checkpoint_id = backend_session.build_run_config(pending_checkpoint_id)
            try:
                event_result = backend_session.invoke_event_round(
                    run_config=run_config,
                    event_payload={"event_override": payload_event},
                    auto_resume_memory_approval=_AUTO_RESUME_MEMORY_APPROVAL,
                    reject_reason="event_no_manual_tooling",
                )
            except Exception as e:
                if _is_transient_runtime_error(e):
                    print("\n[event][warn] 本轮事件触发时网络连接中断。稍后再试就行。")
                    continue
                raise
            event_payload = backend_api.build_event_round_response(
                state_values=event_result.values,
                final_text=event_result.final_text,
                meta={"event_kind": "seed", "seed_id": resolved_seed_id},
            ).payload
            _print_event_round_payload(
                header_label="event",
                header_value=f"seed={resolved_seed_id}",
                payload=event_payload,
                tts_enabled=tts_enabled,
                tts_ref_audio=tts_ref_audio,
            )
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

            run_config, pending_checkpoint_id = backend_session.build_run_config(pending_checkpoint_id)
            try:
                event_result = backend_session.invoke_event_round(
                    run_config=run_config,
                    event_payload={"event_override": payload_event},
                    auto_resume_memory_approval=_AUTO_RESUME_MEMORY_APPROVAL,
                    reject_reason="sense_no_manual_tooling",
                )
            except Exception as e:
                if _is_transient_runtime_error(e):
                    print("\n[sense][warn] 本轮感知事件触发时网络连接中断。稍后再试就行。")
                    continue
                raise
            sense_payload = backend_api.build_event_round_response(
                state_values=event_result.values,
                final_text=event_result.final_text,
                meta={"event_kind": "sense", "sense_ref": resolved_ref},
            ).payload
            _print_event_round_payload(
                header_label="sense",
                header_value=f"ref={resolved_ref}",
                payload=sense_payload,
                tts_enabled=tts_enabled,
                tts_ref_audio=tts_ref_audio,
            )
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

            run_config, pending_checkpoint_id = backend_session.build_run_config(pending_checkpoint_id)
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
                idle_payload = backend_session.build_idle_event_payload(
                    run_config=run_config,
                    idle_minutes=elapsed_minutes,
                    note=event_text,
                    created_at=int(time.time()),
                    extra_tags=["pulse"],
                )
                try:
                    event_result = backend_session.invoke_event_round(
                        run_config=run_config,
                        event_payload=idle_payload,
                        auto_resume_memory_approval=_AUTO_RESUME_MEMORY_APPROVAL,
                        reject_reason="pulse_no_manual_tooling",
                    )
                except Exception as e:
                    if _is_transient_runtime_error(e):
                        print("  [pulse][warn] 这轮 idle 事件触发时网络连接中断，结束连续推进。")
                        break
                    raise
                event_payload = backend_api.build_event_round_response(
                    state_values=event_result.values,
                    final_text=event_result.final_text,
                    meta={"event_kind": "pulse", "elapsed_minutes": elapsed_minutes},
                ).payload
                behavior_action = event_payload.get("behavior_action", {}) if isinstance(event_payload.get("behavior_action"), dict) else {}
                behavior_plan = event_payload.get("behavior_plan", {}) if isinstance(event_payload.get("behavior_plan"), dict) else {}
                evolution_summary = event_payload.get("turn_summary", {}) if isinstance(event_payload.get("turn_summary"), dict) else {}
                last_evolution_summary = evolution_summary
                line = _behavior_action_compact_line(behavior_action)
                print(f"- round={idx + 1}/{rounds} elapsed={elapsed_minutes}min | {line}")
                _print_event_evolution_summary(evolution_summary, prefix="  ", detailed=False)
                _print_turn_appraisal({"turn_appraisal": event_payload.get("turn_appraisal", {})}, prefix="  ")
                if behavior_plan:
                    print("  plan=" + json.dumps(behavior_plan, ensure_ascii=False))

                final_text = str(event_payload.get("final_text") or "").strip()
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
                    _speak_text_realtime(
                        text=final_text,
                        emotion_label=str(event_payload.get("emotion_label") or "neutral"),
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

            run_config, pending_checkpoint_id = backend_session.build_run_config(pending_checkpoint_id)
            event_text = idle_note or f"已经安静地过去了 {idle_minutes} 分钟，没有新的用户消息。"
            idle_payload = backend_session.build_idle_event_payload(
                run_config=run_config,
                idle_minutes=idle_minutes,
                note=event_text,
                created_at=int(time.time()),
            )
            try:
                event_result = backend_session.invoke_event_round(
                    run_config=run_config,
                    event_payload=idle_payload,
                    auto_resume_memory_approval=_AUTO_RESUME_MEMORY_APPROVAL,
                    reject_reason="idle_no_manual_tooling",
                )
            except Exception as e:
                if _is_transient_runtime_error(e):
                    print("\n[idle][warn] 本轮 idle 事件触发时网络连接中断。稍后再试就行。")
                    continue
                raise
            idle_response = backend_api.build_event_round_response(
                state_values=event_result.values,
                final_text=event_result.final_text,
                meta={"event_kind": "idle", "idle_minutes": idle_minutes},
            ).payload
            _print_event_round_payload(
                header_label="idle",
                header_value=f"minutes={idle_minutes}",
                payload=idle_response,
                tts_enabled=tts_enabled,
                tts_ref_audio=tts_ref_audio,
            )
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

            preview = memory_admin.prepare_profile_correction(k, v, reason=reason)
            print("\n[memory correction]")
            print("- key=" + str(preview.key))
            print("- old=" + json.dumps(preview.old_value, ensure_ascii=False))
            print("- new=" + json.dumps(preview.new_value, ensure_ascii=False))
            if preview.reason:
                print("- reason=" + preview.reason)

            ans = input("  确认覆盖并写入 meta? (y/N) > ").strip().lower()
            if ans != "y":
                print("已取消")
                continue

            try:
                memory_admin.apply_profile_correction(preview, confirmed_by="user")
                print(f"已纠正 profile.{preview.key}")
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
            try:
                preview = memory_admin.prepare_undo_profile_correction(k, reason=reason)
            except MemoryAdminError as exc:
                print(str(exc))
                if exc.details:
                    if "current" in exc.details:
                        print("- current=" + json.dumps(exc.details.get("current"), ensure_ascii=False))
                    if "meta_new_value" in exc.details:
                        print("- meta.new_value=" + json.dumps(exc.details.get("meta_new_value"), ensure_ascii=False))
                continue

            print("\n[undo correction]")
            print("- key=" + str(preview.key))
            print("- revert_to(old_value)=" + json.dumps(preview.revert_to, ensure_ascii=False))
            print("- reason=" + preview.reason)
            ans = input("  确认撤销? (y/N) > ").strip().lower()
            if ans != "y":
                print("已取消")
                continue

            try:
                memory_admin.apply_undo_profile_correction(preview, confirmed_by="user")
                print(f"已撤销 profile.{preview.key} 的上一次纠错")
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
            try:
                normalized_key = memory_admin.set_profile_value(k.strip(), v.strip())
            except MemoryAdminError as exc:
                print(str(exc))
                continue
            print(f"已写入 profile.{normalized_key}")
            continue
        if user.lower().startswith("/forget "):
            # /forget key （profile默认）
            k = user[8:].strip()
            if not k:
                print("用法：/forget key")
                continue
            try:
                ok = memory_admin.delete_profile_key(k)
            except MemoryAdminError as exc:
                print(str(exc))
                continue
            print("已删除" if ok else "未找到")
            continue
        if user.lower() == "/moments":
            ms = memory_admin.list_moments(limit=20)
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
            ok = memory_admin.delete_moment(mid)
            print("已删除" if ok else "未找到")
            continue
        if user.lower() == "/reflections":
            rs = memory_admin.list_reflections(limit=20)
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
            ok = memory_admin.delete_reflection(rid)
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
            try:
                proposals = memory_admin.generate_reflection_proposals(moment_limit=n)
            except MemoryAdminError as exc:
                print("\n" + str(exc))
                continue

            print("\n[reflect proposals]")
            wrote = 0
            for proposal in proposals:
                print(
                    "- text="
                    + proposal.text
                    + "\n  derived_from="
                    + json.dumps(proposal.derived_from, ensure_ascii=False)
                    + " importance="
                    + str(proposal.importance)
                )
                ans = input("  写入这条 reflection? (y/N) > ").strip().lower()
                if ans != "y":
                    continue
                write_rule = input("  同时写入 profile.user_model_rules? (y/N) > ").strip().lower() == "y"
                try:
                    memory_admin.write_reflection(proposal, write_user_model_rule=write_rule)
                    wrote += 1
                except Exception as e:
                    print("  写入失败：" + str(e))
                    continue

            print(f"\n已写入 {wrote} 条 reflections。")
            continue

        run_config, pending_checkpoint_id = backend_session.build_run_config(pending_checkpoint_id)

        # 按官方示例：使用 DashScope Realtime，把文本 append_text 给服务端，服务端流式返回 audio.delta。
        tts_out_dir = (get_settings().data_dir / "tts_out")
        backend = str(os.getenv("AMADEUS_TTS_BACKEND", "dashscope_realtime") or "dashscope_realtime").strip().strip('"').lower()

        rt = None
        emotion_label = "neutral"
        try:
            emotion_label = backend_session.emotion_label(config=run_config, default="neutral")
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
                backend_session.apply_implicit_idle_maturation(
                    run_config=run_config,
                    last_conversation_touch_ts=last_conversation_touch_ts,
                    trigger_minutes=_implicit_idle_trigger_minutes(),
                )
            stream_result = backend_session.invoke_stream(
                {"messages": [{"role": "user", "content": user}]},
                config=run_config,
                on_text=None,
            )
            out = stream_result.values
            streamed_text = stream_result.streamed_text
        except Exception as e:
            if _is_transient_runtime_error(e):
                print("\n[network][warn] 远端模型连接中断，本轮未完成。请直接重试刚才那条输入。")
                continue
            raise

        # 工具调用 HITL：一个回合里可能出现多次 interrupt（例如：先审批记忆写入，再审批对话工具）
        approval_request = stream_result.approval_request
        while approval_request is not None:
            tool_calls = approval_request.tool_calls
            payload = approval_request.payload
            payload_source = approval_request.source
            if _AUTO_RESUME_MEMORY_APPROVAL(payload):
                decisions = auto_approve_decisions(tool_calls)
                stream_result = backend_session.resume_stream(
                    decisions,
                    config={"configurable": {"thread_id": run_config["configurable"]["thread_id"]}},
                    on_text=None,
                )
                out = stream_result.values
                streamed_text = stream_result.streamed_text
                approval_request = stream_result.approval_request
                continue
            approval_batch = summarize_tool_approval_request(
                source=payload_source,
                tool_calls=tool_calls,
                hide_memory_logs=bool(HIDE_TOOL_APPROVAL_LOGS),
                max_calls=TOOL_CALLS_MAX,
                toolset_upgrade_ttl_s=TOOLSET_UPGRADE_TTL_S,
            )
            decisions = []
            if approval_batch.show_logs:
                if approval_batch.hidden_tool_call_count > 0:
                    print(
                        f"\n[warn] tool_calls too many ({approval_batch.total_tool_call_count}), "
                        f"only showing first {len(approval_batch.visible_tool_calls)}"
                    )
                print("\n[需要审批的工具调用]")

            for preview in approval_batch.visible_tool_calls:
                if approval_batch.show_logs:
                    print("- tool=" + preview.name)
                    if preview.requested_tools:
                        print("  requested_tools=" + json.dumps(preview.requested_tools, ensure_ascii=False))
                    if preview.reason:
                        print("  reason=" + preview.reason)
                    if preview.note:
                        print("  note=" + preview.note)
                    if preview.meta_preview:
                        print("  meta=" + json.dumps(preview.meta_preview, ensure_ascii=False))
                    print("  args=" + json.dumps(preview.args, ensure_ascii=False))

                action = input("  选择 a=approve / e=edit / r=reject > ").strip().lower() or "r"

                if action == "a":
                    if preview.needs_second_confirmation:
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
                    if needs_second_confirmation(payload_source, preview.name, new_args):
                        ans2 = input("  二次确认(edit)：输入 y 才会写入长期记忆 > ").strip().lower()
                        if ans2 != "y":
                            decisions.append({"action": "reject", "reason": "second confirm failed"})
                            continue
                    decisions.append({"action": "edit", "args": new_args})
                else:
                    reason = input("  reject 原因(可空) > ").strip() or "rejected"
                    decisions.append({"action": "reject", "reason": reason})

            if approval_batch.hidden_tool_call_count > 0:
                decisions.extend(
                    {"action": "reject", "reason": "tool_calls_clipped"}
                    for _ in range(approval_batch.hidden_tool_call_count)
                )

            stream_result = backend_session.resume_stream(
                decisions,
                config={"configurable": {"thread_id": run_config["configurable"]["thread_id"]}},
                on_text=None,
            )
            out = stream_result.values
            streamed_text = stream_result.streamed_text
            approval_request = stream_result.approval_request

        turn_response = backend_api.build_turn_response(
            state_values=out,
            streamed_text=streamed_text,
        ).payload
        final_text = str(turn_response.get("final_text") or "").strip()
        emotion_label = str(turn_response.get("emotion_label") or emotion_label or "neutral").strip() or "neutral"

        print(f"\nAmadeus> {final_text}")
        if _cli_show_turn_summary_enabled():
            turn_summary = turn_response.get("turn_summary", {})
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

    runtime_bundle.close()


if __name__ == "__main__":
    main()
