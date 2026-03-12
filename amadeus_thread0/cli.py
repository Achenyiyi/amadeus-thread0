from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import io

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
from .graph import build_graph
from .memory_store import MemoryStore
from .modeling import build_chat_model, runtime_model_summary
from .session_orchestrator import emotion_to_tts_profile, push_tts_segments
from .settings import get_settings
from .tts_io import create_dashscope_realtime_session, get_tts_config


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


def _print_help() -> None:
    print(
        "\n[commands]\n"
        "/help                     查看命令总览\n"
        "/exit                     退出 CLI\n"
        "/newthread                切换到新世界线\n"
        "/threads                  列出已有 thread_id\n"
        "/history [n]              查看 checkpoint 历史\n"
        "/rewind <checkpoint_id>   从 checkpoint 分叉继续\n"
        "/where                    查看当前 thread / checkpoint\n"
        "/env                      查看运行环境摘要\n"
        "/mem                      查看 profile / relationship / moments 快照\n"
        "/worldline                查看世界线事件 / 承诺 / 冲突修复\n"
        "/bond                     查看关系状态与关系时间线\n"
        "/sources                  查看来源与 claim->source 映射\n"
        "/persona                  查看角色状态快照\n"
        "/agenda                   查看待成熟行为议程\n"
        "/queue                    查看待成熟行为队列（/agenda 别名）\n"
        "/idle [minutes] [| note]  模拟一段安静时间经过，让她决定是否主动开口\n"
        "/events                   列出可注入的感知/生活事件种子\n"
        "/event <seed_id> [| note] 触发一个事件种子，让她按事件而非用户发言做行为选择\n"
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


_EVENT_SEED_BANK_CACHE: dict[str, dict[str, object]] | None = None


def _event_seed_bank_path() -> Path:
    return Path(__file__).resolve().parents[1] / "evals" / "perception_event_seed_bank.json"


def _load_event_seed_bank() -> dict[str, dict[str, object]]:
    global _EVENT_SEED_BANK_CACHE
    if _EVENT_SEED_BANK_CACHE is not None:
        return _EVENT_SEED_BANK_CACHE
    path = _event_seed_bank_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _EVENT_SEED_BANK_CACHE = {}
        return _EVENT_SEED_BANK_CACHE
    seeds = raw.get("seeds") if isinstance(raw, dict) else []
    bank: dict[str, dict[str, object]] = {}
    if isinstance(seeds, list):
        for item in seeds:
            if not isinstance(item, dict):
                continue
            seed_id = str(item.get("id") or "").strip()
            if seed_id:
                bank[seed_id] = item
    _EVENT_SEED_BANK_CACHE = bank
    return bank


def _list_event_seed_rows() -> list[str]:
    bank = _load_event_seed_bank()
    rows: list[str] = []
    for seed_id in sorted(bank):
        item = bank[seed_id]
        kind = str(item.get("kind") or "").strip() or "unknown"
        source = str(item.get("source") or "").strip() or "unknown"
        status = str(item.get("status") or "").strip() or "unknown"
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        rows.append(
            f"- {seed_id} [{kind}/{source}/{status}]"
            + (f" tags={tags[:4]}" if tags else "")
        )
    return rows


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


def main():
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
    graph = build_graph()
    memory_store = MemoryStore(s.memory_db_path)

    config = {
        "configurable": {
            # LangGraph persistence 通过 thread_id 把 checkpoint 归到同一条“世界线”
            "thread_id": s.thread_id,
            "user_id": s.user_id,
        }
    }

    # 用于 time travel：下一次对话从指定 checkpoint 分叉继续（用一次即清空）
    pending_checkpoint_id: str | None = None

    # TTS（DashScope Realtime；从 env 读取）
    tts_cfg = get_tts_config()
    tts_enabled = bool(tts_cfg.enabled)
    tts_ref_audio = str(tts_cfg.ref_audio or "").strip()
    tts_ref_text = str(tts_cfg.ref_text or "").strip()

    print("Amadeus-K CLI 已启动。输入 /help 查看命令，/exit 退出。")
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
        user = input("\nYou> ").strip()
        if not user:
            continue
        if user.lower() in {"/help", "/?"}:
            _print_help()
            continue
        if user.lower() in {"/exit", "exit", "quit"}:
            break
        if user.lower() == "/newthread":
            # 简单起见：让你手动输入新 thread_id（后续我可以做自动命名/列出历史线程）
            new_id = input("new thread_id> ").strip()
            if new_id:
                config["configurable"]["thread_id"] = new_id
                # 切线程后清空 time travel 目标
                pending_checkpoint_id = None
                print(f"已切换到 thread_id={new_id}")
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
            print("\n[RELATIONSHIP_STATE]\n" + json.dumps(rel, ensure_ascii=False, indent=2))
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
            print("\n[PERSONA_STATE]\n" + json.dumps(vals.get("persona_state", {}), ensure_ascii=False, indent=2))
            print("\n[EMOTION_STATE]\n" + json.dumps(vals.get("emotion_state", {}), ensure_ascii=False, indent=2))
            print("\n[BOND_STATE]\n" + json.dumps(vals.get("bond_state", {}), ensure_ascii=False, indent=2))
            print("\n[ALLOSTASIS_STATE]\n" + json.dumps(vals.get("allostasis_state", {}), ensure_ascii=False, indent=2))
            print("\n[COUNTERPART_ASSESSMENT]\n" + json.dumps(vals.get("counterpart_assessment", {}), ensure_ascii=False, indent=2))
            print("\n[SEMANTIC_NARRATIVE_PROFILE]\n" + json.dumps(vals.get("semantic_narrative_profile", {}), ensure_ascii=False, indent=2))
            print("\n[BEHAVIOR_POLICY]\n" + json.dumps(vals.get("behavior_policy", {}), ensure_ascii=False, indent=2))
            print("\n[BEHAVIOR_ACTION]\n" + json.dumps(vals.get("behavior_action", {}), ensure_ascii=False, indent=2))
            print("\n[BEHAVIOR_PLAN]\n" + json.dumps(vals.get("behavior_plan", {}), ensure_ascii=False, indent=2))
            queue_vals = vals.get("behavior_queue", vals.get("behavior_agenda", []))
            print("\n[BEHAVIOR_QUEUE]\n" + json.dumps(queue_vals, ensure_ascii=False, indent=2))
            print("\n[SCIENCE_MODE]\n" + json.dumps(vals.get("science_mode", False), ensure_ascii=False, indent=2))
            print("\n[TSUNDERE_INTENSITY]\n" + json.dumps(vals.get("tsundere_intensity", 0.5), ensure_ascii=False, indent=2))
            print("\n[CANON_GUARD]\n" + json.dumps(vals.get("canon_guard", {}), ensure_ascii=False, indent=2))
            continue

        if user.lower() in {"/agenda", "/queue"}:
            cur = graph.get_state(
                {"configurable": {"thread_id": config["configurable"]["thread_id"]}}
            )
            vals = getattr(cur, "values", {}) if cur is not None else {}
            if not isinstance(vals, dict):
                vals = {}
            queue_vals = vals.get("behavior_queue", vals.get("behavior_agenda", []))
            print("\n[BEHAVIOR_QUEUE]\n" + json.dumps(queue_vals, ensure_ascii=False, indent=2))
            continue

        if user.lower() in {"/events", "/event_list"}:
            rows = _list_event_seed_rows()
            print("\n[EVENT_SEEDS]")
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

            bank = _load_event_seed_bank()
            seed = bank.get(seed_id)
            if not isinstance(seed, dict):
                print(f"\n[event] 未找到事件种子：{seed_id}")
                continue
            event = seed.get("event") if isinstance(seed.get("event"), dict) else {}
            if not event:
                print(f"\n[event] 事件种子缺少 event 载荷：{seed_id}")
                continue

            payload_event = dict(event)
            if note_override:
                payload_event["text"] = note_override
                payload_event["effective_text"] = note_override
            payload_event.setdefault("created_at", int(time.time()))

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

            print(
                "\n[event]"
                + f" seed={seed_id}"
                + "\n[BEHAVIOR_ACTION]\n"
                + json.dumps(behavior_action, ensure_ascii=False, indent=2)
            )
            if behavior_plan:
                print("\n[BEHAVIOR_PLAN]\n" + json.dumps(behavior_plan, ensure_ascii=False, indent=2))
            if current_event:
                print("\n[CURRENT_EVENT]\n" + json.dumps(current_event, ensure_ascii=False, indent=2))
            if final_text:
                print("\nAmadeus> " + final_text)
            else:
                print("\nAmadeus> （这轮她选择先不主动开口。）")
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

            print(
                "\n[idle]"
                + f" minutes={idle_minutes}"
                + "\n[BEHAVIOR_ACTION]\n"
                + json.dumps(behavior_action, ensure_ascii=False, indent=2)
            )
            if current_event:
                print("\n[CURRENT_EVENT]\n" + json.dumps(current_event, ensure_ascii=False, indent=2))
            if final_text:
                print("\nAmadeus> " + final_text)
            else:
                print("\nAmadeus> （这轮她选择先不主动开口。）")
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


if __name__ == "__main__":
    main()
