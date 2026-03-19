from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from amadeus_thread0.runtime.backend_api import BackendAPI, BackendApiEnvelope


class FakeBackendSession:
    def __init__(self):
        self.behavior_queue_config = None
        self.checkpoint_history_args = None
        self.current_checkpoint_config = None
        self.last_summary_state = None
        self.last_extract_args = None

    def worldline_view(self):
        return {
            "worldline_events": [{"summary": "一起熬夜。"}],
            "semantic_self_narratives": [
                {
                    "id": 12,
                    "text": "她会把最终行为沉淀回长期自我叙事，而不是继续展示检索阶段的旧副本。",
                    "category": "agency_style",
                }
            ],
        }

    def bond_view(self):
        return {"relationship_state": {"stage": "warming"}}

    def sources_view(self):
        return {"sources": [{"id": 9, "title": "paper"}], "claim_links": [{"source_ids": [9]}]}

    def persona_view(self):
        return {"persona_state": {"role": "kurisu_amadeus"}}

    def appraisal_view(self):
        return {"scene": "daily_care"}

    def behavior_queue_view(self, *, config=None):
        self.behavior_queue_config = config
        return {"behavior_queue": [{"agenda_id": "q1"}]}

    def checkpoint_history_view(self, *, limit=10, config=None):
        self.checkpoint_history_args = (limit, config)
        return {"total": 1, "rows": [{"checkpoint_id": "cp-1"}]}

    def current_checkpoint_view(self, *, config=None):
        self.current_checkpoint_config = config
        return {"thread_id": "thread-a", "checkpoint_id": "cp-9"}

    def build_evolution_summary(self, *, state_values=None):
        self.last_summary_state = state_values
        values = state_values if isinstance(state_values, dict) else {}
        recon = values.get("reconsolidation_snapshot") if isinstance(values.get("reconsolidation_snapshot"), dict) else {}
        consequence = recon.get("behavior_consequence") if isinstance(recon.get("behavior_consequence"), dict) else {}
        return {
            "relationship": {"stage": "warming"},
            "current_turn": {
                "recon_event_kind": str(recon.get("event_kind") or "").strip(),
                "recon_interaction_frame": str(recon.get("interaction_frame") or "").strip(),
                "behavior_consequence_kind": str(consequence.get("kind") or "").strip(),
            },
        }

    def extract_final_text(self, values, *, streamed_text=""):
        self.last_extract_args = (values, streamed_text)
        return "final from session"


class FakeMemoryAdmin:
    def snapshot_view(self):
        return {
            "profile": {"name": "okabe"},
            "relationship": {"stage": "warming"},
            "moments": [{"id": 1, "summary": "一起熬夜。"}],
        }


class BackendApiTests(unittest.TestCase):
    def _build_api(
        self,
        *,
        base_data_dir: Path,
        checkpoint_db_path: Path,
        current_data_dir: Path | None = None,
        model_base_url: str = "",
    ) -> tuple[BackendAPI, FakeBackendSession]:
        session = FakeBackendSession()
        settings = SimpleNamespace(
            checkpoint_db_path=checkpoint_db_path,
            data_dir=current_data_dir or base_data_dir,
            model_provider="dashscope",
            model_name="qwen3.5-plus",
            model_base_url=model_base_url,
            runtime_mode="cli",
        )
        runtime_bundle = SimpleNamespace(
            thread_id="thread-a",
            backend_session=session,
            memory_admin=FakeMemoryAdmin(),
            settings=settings,
        )
        return BackendAPI(runtime_bundle=runtime_bundle, base_data_dir=base_data_dir, cwd=base_data_dir), session

    def test_envelope_to_dict_preserves_schema_fields(self):
        envelope = BackendApiEnvelope(
            kind="persona_view",
            thread_id="thread-a",
            payload={"persona_state": {"role": "kurisu_amadeus"}},
            generated_at=123,
            meta={"source": "cli"},
        )
        self.assertEqual(
            envelope.to_dict(),
            {
                "schema_version": "backend.v1",
                "generated_at": 123,
                "kind": "persona_view",
                "thread_id": "thread-a",
                "payload": {"persona_state": {"role": "kurisu_amadeus"}},
                "meta": {"source": "cli"},
            },
        )

    def test_view_methods_wrap_backend_session_surfaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, session = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            config = {"configurable": {"thread_id": "thread-a"}}

            self.assertEqual(api.memory_snapshot().payload["profile"]["name"], "okabe")
            self.assertEqual(api.worldline().payload["worldline_events"][0]["summary"], "一起熬夜。")
            self.assertIn("最终行为沉淀", api.worldline().payload["semantic_self_narratives"][0]["text"])
            self.assertEqual(api.bond().payload["relationship_state"]["stage"], "warming")
            self.assertEqual(api.sources().payload["claim_links"][0]["source_ids"], [9])
            self.assertEqual(api.persona().payload["persona_state"]["role"], "kurisu_amadeus")
            self.assertEqual(api.appraisal().payload["turn_appraisal"]["scene"], "daily_care")

            queue = api.behavior_queue(config=config).payload
            history = api.checkpoint_history(limit=5, config=config).payload
            current = api.current_checkpoint(config=config).payload

            self.assertEqual(queue["behavior_queue"][0]["agenda_id"], "q1")
            self.assertEqual(history["rows"][0]["checkpoint_id"], "cp-1")
            self.assertEqual(current["checkpoint_id"], "cp-9")
            self.assertEqual(session.behavior_queue_config, config)
            self.assertEqual(session.checkpoint_history_args, (5, config))
            self.assertEqual(session.current_checkpoint_config, config)

    def test_thread_inventory_and_runtime_layout_are_frontend_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            conn = sqlite3.connect(str(checkpoint_db))
            try:
                conn.execute("CREATE TABLE checkpoints (id INTEGER PRIMARY KEY, thread_id TEXT)")
                conn.execute("INSERT INTO checkpoints(thread_id) VALUES (?)", ("thread-b",))
                conn.execute("INSERT INTO checkpoints(thread_id) VALUES (?)", ("thread-a",))
                conn.commit()
            finally:
                conn.close()

            (root / "worldlines" / "thread-a").mkdir(parents=True, exist_ok=True)
            (root / "worldlines" / "thread-c").mkdir(parents=True, exist_ok=True)
            (root / "decision_audit.jsonl").write_text("{}\n", encoding="utf-8")

            current_runtime = root / "worldlines" / "thread-a"
            (current_runtime / "memories.sqlite").write_bytes(b"x")

            api, _ = self._build_api(
                base_data_dir=root,
                checkpoint_db_path=checkpoint_db,
                current_data_dir=current_runtime,
            )

            inventory = api.thread_inventory().payload
            runtime_layout = api.runtime_layout().payload

            self.assertEqual(inventory["checkpoint_thread_ids"], ["thread-a", "thread-b"])
            self.assertEqual(inventory["worldline_dir_ids"], ["thread-a", "thread-c"])
            self.assertEqual(inventory["current_thread_id"], "thread-a")
            self.assertEqual(runtime_layout["repo_runtime"]["stats"]["shared_artifact_count"], 2)
            self.assertIsNotNone(runtime_layout["current_runtime"])
            assert runtime_layout["current_runtime"] is not None
            self.assertEqual(runtime_layout["current_runtime"]["shared_runtime"]["artifact_count"], 1)

    def test_environment_summary_includes_runtime_model_and_tts_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(
                base_data_dir=root,
                checkpoint_db_path=checkpoint_db,
                model_base_url="",
            )

            payload = api.environment_summary(
                cwd=root / "workspace",
                env={
                    "AMADEUS_EVAL_MODE": "1",
                    "AMADEUS_USER_FACING_MODE": "0",
                    "AMADEUS_CLI_SHOW_TURN_SUMMARY": "1",
                    "AMADEUS_TTS_ENABLED": "1",
                    "AMADEUS_TTS_BACKEND": "dashscope_realtime",
                    "AMADEUS_TTS_REF_AUDIO": "data/copy_wav/sora.wav",
                    "AMADEUS_TTS_DASHSCOPE_MODEL": "cosyvoice-v2",
                    "DASHSCOPE_API_KEY": "sk-test",
                },
            ).payload

            self.assertEqual(payload["cwd"], str(root / "workspace"))
            self.assertEqual(payload["model_provider"], "dashscope")
            self.assertEqual(payload["model_name"], "qwen3.5-plus")
            self.assertEqual(payload["model_base_url"], "(default)")
            self.assertEqual(payload["runtime_mode"], "cli")
            self.assertEqual(payload["eval_mode"], "1")
            self.assertEqual(payload["user_facing_mode"], "0")
            self.assertEqual(payload["cli_show_turn_summary"], "1")
            self.assertEqual(payload["tts_enabled"], "1")
            self.assertEqual(payload["tts_backend"], "dashscope_realtime")
            self.assertTrue(payload["dashscope_api_key_set"])

    def test_turn_and_event_responses_share_final_state_payload_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, session = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "emotion_state": {"label": "care"},
                "behavior_action": {"interaction_mode": "checkin"},
                "behavior_plan": {"kind": "small_opening"},
                "reconsolidation_snapshot": {
                    "event_kind": "user_utterance",
                    "interaction_frame": "relationship",
                    "behavior_consequence": {"kind": "leave_small_opening"},
                },
                "current_event": {"kind": "idle"},
                "turn_appraisal": {"scene": "daily_care"},
                "claim_links": [{"source_ids": [9]}],
                "evidence_pack": [{"id": 9, "title": "paper"}],
                "pending_utterance_fragment": "unfinished thought",
            }

            event_response = api.build_event_round_response(
                state_values=state_values,
                final_text="我在。",
                meta={"event_kind": "idle"},
            )
            turn_response = api.build_turn_response(
                state_values=state_values,
                streamed_text="ignored",
                meta={"source": "cli"},
            )

            self.assertEqual(event_response.kind, "event_round")
            self.assertEqual(event_response.meta["event_kind"], "idle")
            self.assertEqual(event_response.payload["final_text"], "我在。")
            self.assertEqual(event_response.payload["emotion_label"], "care")
            self.assertEqual(event_response.payload["behavior_action"]["interaction_mode"], "checkin")
            self.assertEqual(event_response.payload["turn_summary"]["relationship"]["stage"], "warming")
            self.assertEqual(event_response.payload["reconsolidation_snapshot"]["interaction_frame"], "relationship")
            self.assertEqual(
                event_response.payload["turn_summary"]["current_turn"]["behavior_consequence_kind"],
                "leave_small_opening",
            )

            self.assertEqual(turn_response.kind, "assistant_turn")
            self.assertEqual(turn_response.meta["source"], "cli")
            self.assertEqual(turn_response.payload["final_text"], "final from session")
            self.assertEqual(turn_response.payload["claim_links"][0]["source_ids"], [9])
            self.assertEqual(turn_response.payload["sources"][0]["id"], 9)
            self.assertEqual(turn_response.payload["reconsolidation_snapshot"]["event_kind"], "user_utterance")
            self.assertEqual(turn_response.payload["turn_summary"]["current_turn"]["recon_event_kind"], "user_utterance")
            self.assertEqual(turn_response.payload["pending_utterance_fragment"], "unfinished thought")
            self.assertEqual(session.last_extract_args, (state_values, "ignored"))
            self.assertIs(session.last_summary_state, state_values)

    def test_turn_and_event_responses_prefer_final_persisted_behavior_plan_over_derived_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "behavior_action": {
                    "action_target": "offer_small_opening",
                    "interaction_mode": "self_activity_reopen",
                    "primary_motive": "gentle_recontact",
                    "motive_tension": "self_rhythm_vs_contact",
                    "goal_frame": "这次顺着余温轻轻回头。",
                    "deferred_action_family": "small_opening",
                    "timing_window_min": 0,
                    "relationship_weather": "warm_residue",
                    "attention_target": "counterpart_state",
                    "nonverbal_signal": "glance_back",
                    "channel": "speech",
                },
                "behavior_plan": {
                    "kind": "deferred_checkin",
                    "target": "counterpart",
                    "trigger_family": "observe",
                    "scheduled_after_min": 45,
                    "legacy_hint": "keep-me",
                },
                "current_event": {"kind": "self_activity_state", "event_frame": "idle continuation", "tags": []},
                "world_model_state": {"presence_residue": 0.42},
            }

            with patch(
                "amadeus_thread0.runtime.final_state._behavior_plan_from_action",
                return_value={
                    "kind": "small_opening",
                    "target": "counterpart",
                    "scheduled_after_min": 0,
                    "trigger_family": "small_opening",
                    "primary_motive": "gentle_recontact",
                },
            ) as mock_derive:
                event_response = api.build_event_round_response(
                    state_values=state_values,
                    final_text="我在。",
                )
                turn_response = api.build_turn_response(
                    state_values=state_values,
                    streamed_text="ignored",
                )

            self.assertEqual(event_response.payload["behavior_plan"]["kind"], "deferred_checkin")
            self.assertEqual(turn_response.payload["behavior_plan"]["kind"], "deferred_checkin")
            self.assertEqual(event_response.payload["behavior_plan"]["trigger_family"], "observe")
            self.assertEqual(turn_response.payload["behavior_plan"]["scheduled_after_min"], 45)
            self.assertEqual(event_response.payload["behavior_plan"]["legacy_hint"], "keep-me")
            self.assertEqual(turn_response.payload["behavior_plan"]["legacy_hint"], "keep-me")
            mock_derive.assert_not_called()


if __name__ == "__main__":
    unittest.main()
