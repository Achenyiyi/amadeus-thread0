from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..utils.runtime_audit import audit_runtime_layout
from .thread_runtime import list_threads


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _emotion_label_from_state(values: dict[str, Any] | None, *, default: str = "neutral") -> str:
    data = values if isinstance(values, dict) else {}
    emotion_state = data.get("emotion_state") if isinstance(data.get("emotion_state"), dict) else {}
    label = str((emotion_state or {}).get("label") or "").strip()
    return label or str(default or "neutral")


@dataclass(frozen=True)
class BackendApiEnvelope:
    kind: str
    thread_id: str
    payload: dict[str, Any]
    generated_at: int = field(default_factory=lambda: int(time.time()))
    schema_version: str = "backend.v1"
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": int(self.generated_at),
            "kind": self.kind,
            "thread_id": self.thread_id,
            "payload": dict(self.payload),
            "meta": dict(self.meta),
        }


@dataclass
class BackendAPI:
    runtime_bundle: Any
    base_data_dir: Path
    cwd: Path | None = None

    @property
    def thread_id(self) -> str:
        return str(getattr(self.runtime_bundle, "thread_id", "") or "")

    @property
    def backend_session(self) -> Any:
        return getattr(self.runtime_bundle, "backend_session")

    @property
    def memory_admin(self) -> Any:
        return getattr(self.runtime_bundle, "memory_admin")

    @property
    def settings(self) -> Any:
        return getattr(self.runtime_bundle, "settings")

    def _envelope(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        meta: dict[str, Any] | None = None,
    ) -> BackendApiEnvelope:
        return BackendApiEnvelope(
            kind=kind,
            thread_id=self.thread_id,
            payload=dict(payload),
            meta=dict(meta or {}),
        )

    def memory_snapshot(self) -> BackendApiEnvelope:
        return self._envelope("memory_snapshot", self.memory_admin.snapshot_view())

    def worldline(self) -> BackendApiEnvelope:
        return self._envelope("worldline_view", self.backend_session.worldline_view())

    def bond(self) -> BackendApiEnvelope:
        return self._envelope("bond_view", self.backend_session.bond_view())

    def sources(self) -> BackendApiEnvelope:
        return self._envelope("sources_view", self.backend_session.sources_view())

    def persona(self) -> BackendApiEnvelope:
        return self._envelope("persona_view", self.backend_session.persona_view())

    def appraisal(self) -> BackendApiEnvelope:
        return self._envelope("appraisal_view", {"turn_appraisal": self.backend_session.appraisal_view()})

    def behavior_queue(self, *, config: dict[str, Any] | None = None) -> BackendApiEnvelope:
        return self._envelope("behavior_queue_view", self.backend_session.behavior_queue_view(config=config))

    def checkpoint_history(
        self,
        *,
        limit: int = 10,
        config: dict[str, Any] | None = None,
    ) -> BackendApiEnvelope:
        return self._envelope(
            "checkpoint_history",
            self.backend_session.checkpoint_history_view(limit=limit, config=config),
        )

    def current_checkpoint(self, *, config: dict[str, Any] | None = None) -> BackendApiEnvelope:
        return self._envelope("current_checkpoint", self.backend_session.current_checkpoint_view(config=config))

    def thread_inventory(self) -> BackendApiEnvelope:
        inventory = list_threads(
            base_data_dir=self.base_data_dir,
            checkpoint_db_path=self.settings.checkpoint_db_path,
        )
        return self._envelope(
            "thread_inventory",
            {
                "checkpoint_thread_ids": inventory.checkpoint_thread_ids,
                "worldline_dir_ids": inventory.worldline_dir_ids,
                "current_thread_id": self.thread_id,
            },
        )

    def runtime_layout(self) -> BackendApiEnvelope:
        repo_runtime = audit_runtime_layout(self.base_data_dir)
        current_runtime = None
        try:
            if Path(self.settings.data_dir).resolve() != Path(self.base_data_dir).resolve():
                current_runtime = audit_runtime_layout(self.settings.data_dir)
        except Exception:
            current_runtime = None
        return self._envelope(
            "runtime_layout",
            {
                "repo_runtime": repo_runtime,
                "current_runtime": current_runtime,
            },
        )

    def environment_summary(
        self,
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> BackendApiEnvelope:
        current_env = dict(env or os.environ)
        current_cwd = Path(cwd or self.cwd or Path.cwd())
        base_url = str(self.settings.model_base_url) if str(self.settings.model_base_url).strip() else "(default)"
        payload = {
            "cwd": str(current_cwd),
            "model_provider": str(self.settings.model_provider),
            "model_name": str(self.settings.model_name),
            "model_base_url": base_url,
            "runtime_mode": str(self.settings.runtime_mode),
            "eval_mode": str(current_env.get("AMADEUS_EVAL_MODE", "0")),
            "user_facing_mode": str(current_env.get("AMADEUS_USER_FACING_MODE", "1")),
            "cli_show_turn_summary": str(current_env.get("AMADEUS_CLI_SHOW_TURN_SUMMARY", "0")),
            "tts_enabled": str(current_env.get("AMADEUS_TTS_ENABLED")),
            "tts_backend": str(current_env.get("AMADEUS_TTS_BACKEND")),
            "tts_ref_audio": str(current_env.get("AMADEUS_TTS_REF_AUDIO")),
            "tts_model": str(current_env.get("AMADEUS_TTS_DASHSCOPE_MODEL")),
            "dashscope_api_key_set": bool(str(current_env.get("DASHSCOPE_API_KEY") or "").strip()),
        }
        return self._envelope("environment_summary", payload)

    def build_event_round_response(
        self,
        *,
        state_values: dict[str, Any] | None,
        final_text: str,
        meta: dict[str, Any] | None = None,
    ) -> BackendApiEnvelope:
        values = state_values if isinstance(state_values, dict) else {}
        payload = {
            "final_text": str(final_text or "").strip(),
            "emotion_label": _emotion_label_from_state(values),
            "behavior_action": _dict_or_empty(values.get("behavior_action")),
            "behavior_plan": _dict_or_empty(values.get("behavior_plan")),
            "current_event": _dict_or_empty(values.get("current_event")),
            "turn_appraisal": _dict_or_empty(values.get("turn_appraisal")),
            "turn_summary": self.backend_session.build_evolution_summary(state_values=values),
        }
        return self._envelope("event_round", payload, meta=meta)

    def build_turn_response(
        self,
        *,
        state_values: dict[str, Any] | None,
        streamed_text: str = "",
        meta: dict[str, Any] | None = None,
    ) -> BackendApiEnvelope:
        values = state_values if isinstance(state_values, dict) else {}
        final_text = self.backend_session.extract_final_text(values, streamed_text=streamed_text)
        payload = {
            "final_text": final_text,
            "emotion_label": _emotion_label_from_state(values),
            "turn_summary": self.backend_session.build_evolution_summary(state_values=values),
            "behavior_action": _dict_or_empty(values.get("behavior_action")),
            "behavior_plan": _dict_or_empty(values.get("behavior_plan")),
            "turn_appraisal": _dict_or_empty(values.get("turn_appraisal")),
            "claim_links": _list_or_empty(values.get("claim_links")),
            "sources": _list_or_empty(values.get("evidence_pack")),
            "pending_utterance_fragment": str(values.get("pending_utterance_fragment") or "").strip(),
        }
        return self._envelope("assistant_turn", payload, meta=meta)


__all__ = ["BackendAPI", "BackendApiEnvelope"]
