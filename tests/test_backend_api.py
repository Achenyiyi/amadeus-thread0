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
        self.memory_store = None

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
        behavior_action = (
            dict(recon.get("behavior_action") or {})
            if isinstance(recon.get("behavior_action"), dict) and recon.get("behavior_action")
            else values.get("behavior_action")
            if isinstance(values.get("behavior_action"), dict)
            else {}
        )
        counterpart = recon.get("counterpart") if isinstance(recon.get("counterpart"), dict) else {}
        digital_body = values.get("digital_body_state") if isinstance(values.get("digital_body_state"), dict) else {}
        access_state = digital_body.get("access_state") if isinstance(digital_body.get("access_state"), dict) else {}
        resource_state = digital_body.get("resource_state") if isinstance(digital_body.get("resource_state"), dict) else {}
        digital_body_consequence = (
            values.get("digital_body_consequence")
            if isinstance(values.get("digital_body_consequence"), dict)
            else {}
        )
        if not digital_body_consequence and isinstance(recon.get("digital_body_consequence"), dict):
            digital_body_consequence = dict(recon.get("digital_body_consequence") or {})
        current_event = values.get("current_event") if isinstance(values.get("current_event"), dict) else {}
        interaction_carryover = (
            dict(recon.get("interaction_carryover") or {})
            if isinstance(recon.get("interaction_carryover"), dict) and recon.get("interaction_carryover")
            else values.get("interaction_carryover")
            if isinstance(values.get("interaction_carryover"), dict)
            else {}
        )
        return {
            "relationship": {"stage": "warming"},
            "current_turn": {
                "recon_event_kind": str(recon.get("event_kind") or "").strip(),
                "recon_interaction_frame": str(recon.get("interaction_frame") or "").strip(),
                "counterpart_stance": str(counterpart.get("stance") or "").strip(),
                "counterpart_scene": str(counterpart.get("scene") or "").strip(),
                "behavior_consequence_kind": str(consequence.get("kind") or "").strip(),
                "behavior_action_embodied_context": (
                    dict(behavior_action.get("embodied_context") or {})
                    if isinstance(behavior_action.get("embodied_context"), dict)
                    else {}
                ),
                "digital_body_surface": str(digital_body.get("active_surface") or "").strip(),
                "digital_body_access_mode": str(access_state.get("mode") or "").strip(),
                "digital_body_pending_approval_count": int(access_state.get("pending_approval_count") or 0),
                "digital_body_retry_after_s": int(access_state.get("retry_after_s") or 0),
                "digital_body_cooldown_scope": str(access_state.get("cooldown_scope") or "").strip(),
                "digital_body_session_continuity": str(access_state.get("session_continuity") or "").strip(),
                "digital_body_session_expires_in_s": int(access_state.get("session_expires_in_s") or 0),
                "digital_body_session_recovery_mode": str(access_state.get("session_recovery_mode") or "").strip(),
                "digital_body_artifact_continuity": str(resource_state.get("artifact_continuity") or "").strip(),
                "digital_body_active_artifact_kind": str(resource_state.get("active_artifact_kind") or "").strip(),
                "digital_body_active_artifact_label": str(
                    resource_state.get("active_artifact_label") or resource_state.get("active_artifact_ref") or ""
                ).strip(),
                "digital_body_artifact_reacquisition_mode": str(resource_state.get("artifact_reacquisition_mode") or "").strip(),
                "digital_body_consequence_kind": str(digital_body_consequence.get("kind") or "").strip(),
                "digital_body_consequence_summary": str(digital_body_consequence.get("summary") or "").strip(),
            },
            "event_residue": {
                "event_kind": str(current_event.get("kind") or "").strip(),
                "digital_body_consequence": dict(digital_body_consequence),
            },
            "interaction_carryover": dict(interaction_carryover),
            "digital_body": dict(digital_body),
            "digital_body_consequence": dict(digital_body_consequence),
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
                "bond_state": {"trust": 0.7, "closeness": 0.68, "hurt": 0.02},
                "allostasis_state": {"safety_need": 0.18, "autonomy_need": 0.28},
                "semantic_narrative_profile": {"history_weight": 0.54, "presence_carry": 0.5},
                "world_model_state": {"presence_residue": 0.4, "ambient_resonance": 0.2, "self_activity_momentum": 0.3},
                "evolution_state": {"self_coherence": 0.76, "agency_pressure": 0.42},
                "behavior_action": {"interaction_mode": "checkin"},
                "behavior_plan": {"kind": "small_opening"},
                "autonomy_intent": {
                    "mode": "queue_followthrough",
                    "origin": "counterpart_request",
                    "reason": "先回应这次靠近，再把后续的小窗口留着。",
                    "confidence": 0.67,
                    "continuity_weight": 0.58,
                },
                "digital_body_state": {
                    "active_surface": "tooling",
                    "perception_channels": ["chat", "text"],
                    "action_channels": ["language", "tooling", "structured_action"],
                    "available_toolsets": ["search_web"],
                    "active_tools": ["search_web"],
                    "access_state": {
                        "mode": "tool_enabled",
                        "granted_toolsets": ["search_web"],
                        "api_key_state": "present",
                        "quota_state": "low",
                    },
                    "resource_state": {"action_packet_count": 1},
                },
                "action_packets": [
                    {
                        "proposal_id": "ap-turn-1",
                        "origin": "counterpart_request",
                        "intent": "small_opening",
                        "status": "queued",
                        "risk": "read",
                        "requires_approval": False,
                        "capability_steps": [],
                        "expected_effect": "先回应，再留一个小窗口。",
                        "writeback_ready": False,
                    }
                ],
                "action_trace": [{"proposal_id": "ap-turn-1", "status": "queued", "event": "derived_from_behavior"}],
                "reconsolidation_snapshot": {
                    "event_kind": "user_utterance",
                    "interaction_frame": "relationship",
                    "counterpart": {
                        "summary": "她会先把这次靠近当成一次仍带着谨慎感的修复尝试。",
                        "stance": "watchful",
                        "scene": "repair_attempt",
                        "respect_level": 0.58,
                        "reciprocity": 0.54,
                        "boundary_pressure": 0.31,
                        "reliability_read": 0.57,
                    },
                    "behavior_consequence": {"kind": "leave_small_opening"},
                    "agenda_lifecycle_consequence": {
                        "kind": "released_to_self_activity",
                        "carryover_mode": "own_rhythm",
                    },
                    "digital_body_consequence": {
                        "kind": "embodied_growth",
                        "summary": "这轮她把新的环境路径真正摸顺了。",
                        "procedural_growth": True,
                        "granted_toolsets": ["search_web"],
                    },
                },
                "current_event": {"kind": "idle"},
                "counterpart_assessment": {"stance": "open", "scene": "care_bid"},
                "agenda_lifecycle_residue": {"kind": "held", "carryover_mode": "small_opening"},
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
            self.assertEqual(event_response.payload["session_context"]["thread_id"], "thread-a")
            self.assertEqual(event_response.payload["turn_summary"]["relationship"]["stage"], "warming")
            self.assertEqual(event_response.payload["reconsolidation_snapshot"]["interaction_frame"], "relationship")
            self.assertEqual(event_response.payload["emotion_state"]["label"], "care")
            self.assertEqual(event_response.payload["bond_state"]["trust"], 0.7)
            self.assertEqual(event_response.payload["allostasis_state"]["autonomy_need"], 0.28)
            self.assertEqual(event_response.payload["semantic_narrative_profile"]["history_weight"], 0.54)
            self.assertEqual(event_response.payload["world_model_state"]["presence_residue"], 0.4)
            self.assertEqual(event_response.payload["evolution_state"]["self_coherence"], 0.76)
            self.assertEqual(event_response.payload["counterpart_assessment"]["scene"], "repair_attempt")
            self.assertIn("修复尝试", event_response.payload["counterpart_assessment"]["summary"])
            self.assertEqual(event_response.payload["autonomy"]["intent"]["mode"], "queue_followthrough")
            self.assertEqual(event_response.payload["autonomy"]["action_packets"][0]["proposal_id"], "ap-turn-1")
            self.assertEqual(event_response.payload["digital_body"]["access_state"]["mode"], "tool_enabled")
            self.assertEqual(event_response.payload["digital_body"]["access_state"]["api_key_state"], "present")
            self.assertEqual(event_response.payload["digital_body"]["access_state"]["quota_state"], "low")
            self.assertIn("tooling", event_response.payload["digital_body"]["action_channels"])
            self.assertEqual(event_response.payload["digital_body_consequence"]["kind"], "embodied_growth")
            self.assertTrue(bool(event_response.payload["digital_body_consequence"]["procedural_growth"]))
            self.assertEqual(
                event_response.payload["turn_summary"]["digital_body_consequence"]["kind"],
                "embodied_growth",
            )
            self.assertEqual(
                (
                    (event_response.payload["turn_summary"].get("event_residue") or {}).get("digital_body_consequence")
                    or {}
                ).get("kind"),
                "embodied_growth",
            )
            event_profile = (
                event_response.payload["counterpart_assessment"].get("assessment_profile")
                if isinstance(event_response.payload["counterpart_assessment"].get("assessment_profile"), dict)
                else {}
            )
            self.assertEqual(event_profile.get("dominant_scene_signal"), "repair")
            self.assertIn("safety_read", event_profile)
            self.assertIn("repairability", event_profile)
            self.assertIn("predictability", event_profile)
            self.assertIn("dependency_risk", event_profile)
            self.assertIn("closeness_read", event_profile)
            self.assertEqual(event_response.payload["agenda_lifecycle_residue"]["kind"], "released_to_self_activity")
            self.assertEqual(
                event_response.payload["turn_summary"]["current_turn"]["behavior_consequence_kind"],
                "leave_small_opening",
            )

            self.assertEqual(turn_response.kind, "assistant_turn")
            self.assertEqual(turn_response.meta["source"], "cli")
            self.assertEqual(turn_response.payload["final_text"], "final from session")
            self.assertEqual(turn_response.payload["session_context"]["thread_id"], "thread-a")
            self.assertEqual(turn_response.payload["claim_links"][0]["source_ids"], [9])
            self.assertEqual(turn_response.payload["sources"][0]["id"], 9)
            self.assertEqual(turn_response.payload["reconsolidation_snapshot"]["event_kind"], "user_utterance")
            self.assertEqual(turn_response.payload["emotion_state"]["label"], "care")
            self.assertEqual(turn_response.payload["bond_state"]["closeness"], 0.68)
            self.assertEqual(turn_response.payload["allostasis_state"]["safety_need"], 0.18)
            self.assertEqual(turn_response.payload["semantic_narrative_profile"]["presence_carry"], 0.5)
            self.assertEqual(turn_response.payload["world_model_state"]["ambient_resonance"], 0.2)
            self.assertEqual(turn_response.payload["evolution_state"]["agency_pressure"], 0.42)
            self.assertEqual(turn_response.payload["turn_summary"]["current_turn"]["recon_event_kind"], "user_utterance")
            self.assertEqual(turn_response.payload["turn_summary"]["current_turn"]["counterpart_stance"], "watchful")
            self.assertEqual(turn_response.payload["turn_summary"]["current_turn"]["counterpart_scene"], "repair_attempt")
            self.assertEqual(turn_response.payload["counterpart_assessment"]["scene"], "repair_attempt")
            turn_profile = (
                turn_response.payload["counterpart_assessment"].get("assessment_profile")
                if isinstance(turn_response.payload["counterpart_assessment"].get("assessment_profile"), dict)
                else {}
            )
            self.assertEqual(turn_profile.get("dominant_scene_signal"), "repair")
            self.assertIn("safety_read", turn_profile)
            self.assertIn("repairability", turn_profile)
            self.assertEqual(turn_response.payload["agenda_lifecycle_residue"]["carryover_mode"], "own_rhythm")
            self.assertEqual(turn_response.payload["pending_utterance_fragment"], "unfinished thought")
            self.assertEqual(turn_response.payload["current_event"]["kind"], "idle")
            self.assertEqual(turn_response.payload["autonomy"]["execution_trace"][0]["event"], "derived_from_behavior")
            self.assertEqual(turn_response.payload["digital_body"]["active_surface"], "tooling")
            self.assertEqual(turn_response.payload["digital_body"]["available_toolsets"], ["search_web"])
            self.assertEqual(turn_response.payload["digital_body"]["access_state"]["api_key_state"], "present")
            self.assertEqual(turn_response.payload["digital_body"]["access_state"]["quota_state"], "low")
            self.assertEqual(turn_response.payload["digital_body_consequence"]["kind"], "embodied_growth")
            self.assertEqual(
                turn_response.payload["turn_summary"]["current_turn"]["digital_body_consequence_kind"],
                "embodied_growth",
            )
            self.assertEqual(
                (
                    (turn_response.payload["turn_summary"].get("event_residue") or {}).get("digital_body_consequence")
                    or {}
                ).get("kind"),
                "embodied_growth",
            )
            self.assertEqual(session.last_extract_args, (state_values, "ignored"))
            self.assertIs(session.last_summary_state, state_values)

    def test_turn_and_event_responses_preserve_digital_body_cooldown_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "digital_body_state": {
                    "active_surface": "cooldown_gate",
                    "perception_channels": ["chat", "text"],
                    "action_channels": ["language", "cooldown_gate"],
                    "world_surfaces": ["network"],
                    "access_state": {
                        "mode": "cooldown",
                        "quota_state": "exhausted",
                        "retry_after_s": 300,
                        "cooldown_scope": "provider",
                        "requestable_access": ["api_quota"],
                        "missing_access": ["api_quota"],
                    },
                    "resource_state": {},
                },
                "reconsolidation_snapshot": {
                    "digital_body_consequence": {
                        "kind": "environmental_friction",
                        "summary": "这轮留下的是上游服务的临时冷却。",
                        "environmental_friction": True,
                        "retry_after_s": 300,
                        "cooldown_scope": "provider",
                    }
                },
            }

            event_response = api.build_event_round_response(state_values=state_values, final_text="稍后再试。")
            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")

            for payload in (event_response.payload, turn_response.payload):
                self.assertEqual(payload["digital_body"]["access_state"]["mode"], "cooldown")
                self.assertEqual(payload["digital_body"]["access_state"]["retry_after_s"], 300)
                self.assertEqual(payload["digital_body"]["access_state"]["cooldown_scope"], "provider")
                self.assertEqual(payload["turn_summary"]["current_turn"]["digital_body_retry_after_s"], 300)
                self.assertEqual(payload["turn_summary"]["current_turn"]["digital_body_cooldown_scope"], "provider")
                self.assertEqual(payload["digital_body_consequence"]["retry_after_s"], 300)
                self.assertEqual(payload["digital_body_consequence"]["cooldown_scope"], "provider")

    def test_turn_and_event_responses_preserve_digital_body_session_lifecycle_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "digital_body_state": {
                    "active_surface": "dialogue",
                    "perception_channels": ["chat", "text"],
                    "action_channels": ["language"],
                    "world_surfaces": ["browser"],
                    "access_state": {
                        "mode": "native_only",
                        "browser_session": "present",
                        "account_state": "logged_in",
                        "cookie_state": "present",
                        "session_continuity": "expiring",
                        "session_expires_in_s": 600,
                        "session_recovery_mode": "refresh_session",
                    },
                    "resource_state": {},
                },
                "reconsolidation_snapshot": {
                    "digital_body_consequence": {
                        "kind": "environmental_friction",
                        "summary": "这轮留下的是会话连续性中断，需要刷新会话。",
                        "environmental_friction": True,
                        "session_continuity": "expired",
                        "session_recovery_mode": "refresh_session",
                    }
                },
            }

            event_response = api.build_event_round_response(state_values=state_values, final_text="先刷新一下会话。")
            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")

            for payload in (event_response.payload, turn_response.payload):
                self.assertEqual(payload["digital_body"]["access_state"]["session_continuity"], "expiring")
                self.assertEqual(payload["digital_body"]["access_state"]["session_expires_in_s"], 600)
                self.assertEqual(payload["digital_body"]["access_state"]["session_recovery_mode"], "refresh_session")
                self.assertEqual(payload["turn_summary"]["current_turn"]["digital_body_session_continuity"], "expiring")
                self.assertEqual(payload["turn_summary"]["current_turn"]["digital_body_session_expires_in_s"], 600)
                self.assertEqual(payload["turn_summary"]["current_turn"]["digital_body_session_recovery_mode"], "refresh_session")
                self.assertEqual(payload["digital_body_consequence"]["session_continuity"], "expired")
                self.assertEqual(payload["digital_body_consequence"]["session_recovery_mode"], "refresh_session")

    def test_turn_and_event_responses_preserve_access_acquire_proposals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "final_text": "我先把需要的入口路径列出来。",
                "current_event": {"kind": "user_utterance"},
                "digital_body_state": {
                    "active_surface": "approval_gate",
                    "access_state": {
                        "mode": "approval_pending",
                        "conditions": ["human_approval_required", "access_acquire_planned"],
                        "pending_approval_count": 1,
                        "missing_access": ["api_key"],
                        "requestable_access": ["api_key", "human_approval"],
                        "access_acquire_proposals": [
                            {
                                "target": "api_key",
                                "mode": "operator_provide_api_key",
                                "summary": "先补一个可用 API key。",
                                "operator_action": "填入一个可用 key。",
                                "grants": ["api_key"],
                                "requires_operator": True,
                            }
                        ],
                        "selected_access_proposal": {
                            "target": "api_key",
                            "mode": "operator_provide_api_key",
                            "summary": "先补一个可用 API key。",
                            "operator_action": "填入一个可用 key。",
                            "grants": ["api_key"],
                            "requires_operator": True,
                        },
                    },
                    "resource_state": {},
                },
            }

            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")
            event_response = api.build_event_round_response(state_values=state_values, final_text="ignored")
            for payload in (turn_response.payload, event_response.payload):
                access_state = payload["digital_body"]["access_state"]
                self.assertEqual(access_state["access_acquire_proposals"][0]["target"], "api_key")
                self.assertEqual(access_state["selected_access_proposal"]["mode"], "operator_provide_api_key")
                summary_body = payload["turn_summary"]["digital_body"]
                summary_access = (
                    summary_body["access"]
                    if isinstance(summary_body, dict) and isinstance(summary_body.get("access"), dict)
                    else summary_body["access_state"]
                )
                self.assertEqual(summary_access["access_acquire_proposals"][0]["grants"], ["api_key"])
                self.assertTrue(summary_access["selected_access_proposal"]["requires_operator"])
                consequence = payload["digital_body_consequence"]
                self.assertEqual(consequence["access_acquire_proposals"][0]["target"], "api_key")
                self.assertEqual(consequence["selected_access_proposal"]["mode"], "operator_provide_api_key")

    def test_turn_and_event_responses_preserve_digital_body_artifact_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "digital_body_state": {
                    "active_surface": "dialogue",
                    "perception_channels": ["chat", "text"],
                    "action_channels": ["language"],
                    "world_surfaces": ["filesystem"],
                    "access_state": {
                        "mode": "native_only",
                    },
                    "resource_state": {
                        "artifact_continuity": "detached",
                        "active_artifact_kind": "file",
                        "active_artifact_ref": "notes/plan.md",
                        "active_artifact_label": "plan.md",
                        "artifact_age_s": 7200,
                        "artifact_reacquisition_mode": "reopen_file",
                        "artifact_carrier": "source_ref",
                        "artifact_source_ref_ids": [17],
                        "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "artifact_source_query": "langgraph persistence checkpointer thread",
                        "artifact_source_title": "Persistence",
                        "artifact_source_tool_name": "search_web",
                    },
                },
                "reconsolidation_snapshot": {
                    "digital_body_consequence": {
                        "kind": "environmental_friction",
                        "summary": "这轮留下的是前面文件工作面的断开，需要重新打开文件。",
                        "environmental_friction": True,
                        "artifact_continuity": "detached",
                        "active_artifact_kind": "file",
                        "active_artifact_label": "plan.md",
                        "artifact_reacquisition_mode": "reopen_file",
                        "artifact_carrier": "source_ref",
                        "artifact_source_ref_ids": [17],
                        "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "artifact_source_query": "langgraph persistence checkpointer thread",
                        "artifact_source_title": "Persistence",
                        "artifact_source_tool_name": "search_web",
                    }
                },
            }

            event_response = api.build_event_round_response(state_values=state_values, final_text="先把文件重新打开。")
            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")

            for payload in (event_response.payload, turn_response.payload):
                self.assertEqual(payload["digital_body"]["resource_state"]["artifact_continuity"], "detached")
                self.assertEqual(payload["digital_body"]["resource_state"]["active_artifact_kind"], "file")
                self.assertEqual(payload["digital_body"]["resource_state"]["active_artifact_label"], "plan.md")
                self.assertEqual(payload["digital_body"]["resource_state"]["artifact_reacquisition_mode"], "reopen_file")
                self.assertEqual(payload["digital_body"]["resource_state"]["artifact_carrier"], "source_ref")
                self.assertEqual(payload["digital_body"]["resource_state"]["artifact_source_ref_ids"], [17])
                self.assertEqual(payload["digital_body"]["resource_state"]["artifact_source_title"], "Persistence")
                self.assertEqual(payload["digital_body"]["resource_state"]["artifact_source_tool_name"], "search_web")
                self.assertEqual(payload["turn_summary"]["current_turn"]["digital_body_artifact_continuity"], "detached")
                self.assertEqual(payload["turn_summary"]["current_turn"]["digital_body_active_artifact_kind"], "file")
                self.assertEqual(payload["turn_summary"]["current_turn"]["digital_body_active_artifact_label"], "plan.md")
                self.assertEqual(payload["turn_summary"]["current_turn"]["digital_body_artifact_reacquisition_mode"], "reopen_file")
                self.assertEqual(payload["digital_body_consequence"]["artifact_continuity"], "detached")
                self.assertEqual(payload["digital_body_consequence"]["active_artifact_kind"], "file")
                self.assertEqual(payload["digital_body_consequence"]["active_artifact_label"], "plan.md")
                self.assertEqual(payload["digital_body_consequence"]["artifact_reacquisition_mode"], "reopen_file")
                self.assertEqual(payload["digital_body_consequence"]["artifact_carrier"], "source_ref")
                self.assertEqual(payload["digital_body_consequence"]["artifact_source_ref_ids"], [17])
                self.assertEqual(payload["digital_body_consequence"]["artifact_source_title"], "Persistence")
                self.assertEqual(payload["digital_body_consequence"]["artifact_source_tool_name"], "search_web")

    def test_turn_and_event_responses_surface_workspace_access_resolved_consequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "digital_body_state": {
                    "active_surface": "tooling",
                    "perception_channels": ["dialogue", "filesystem"],
                    "action_channels": ["language", "structured_action", "tooling"],
                    "world_surfaces": ["filesystem"],
                    "access_state": {
                        "mode": "tool_enabled",
                        "filesystem_state": "writable",
                    },
                    "resource_state": {
                        "artifact_continuity": "attached",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": "E:/runtime/workspaces/lab-notes",
                        "active_artifact_label": "lab-notes",
                    },
                },
                "reconsolidation_snapshot": {
                    "digital_body_consequence": {
                        "kind": "workspace_access_resolved",
                        "summary": "可写工作区 lab-notes 已经真的创建好并接入当前上下文，后面的落盘动作现在可以继续。",
                        "active_surface": "tooling",
                        "access_mode": "tool_enabled",
                        "world_surfaces": ["filesystem"],
                        "artifact_continuity": "attached",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": "E:/runtime/workspaces/lab-notes",
                        "active_artifact_label": "lab-notes",
                        "primary_status": "completed",
                        "primary_intent": "access:request_help",
                        "primary_tool_name": "create_workspace_access",
                    }
                },
            }

            event_response = api.build_event_round_response(state_values=state_values, final_text="那就在这个工作区里继续。")
            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")

            for payload in (event_response.payload, turn_response.payload):
                self.assertEqual(payload["digital_body"]["resource_state"]["active_artifact_kind"], "workspace")
                self.assertEqual(payload["digital_body"]["resource_state"]["active_artifact_label"], "lab-notes")
                self.assertEqual(payload["digital_body_consequence"]["kind"], "workspace_access_resolved")
                self.assertEqual(payload["digital_body_consequence"]["primary_tool_name"], "create_workspace_access")
                self.assertEqual(payload["digital_body_consequence"]["active_artifact_kind"], "workspace")
                self.assertEqual(payload["digital_body_consequence"]["active_artifact_label"], "lab-notes")
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_consequence_kind"],
                    "workspace_access_resolved",
                )
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_consequence_summary"],
                    payload["digital_body_consequence"]["summary"],
                )

    def test_turn_response_prefers_graph_session_context_for_turn_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "session_context": {
                    "thread_id": "thread-a",
                    "turn_id": "thread-a:555",
                    "turn_started_at": 555,
                    "user_id": "okabe",
                    "checkpoint_id": "cp-2",
                },
                "current_event": {
                    "kind": "idle",
                    "created_at": 555,
                    "perception": {},
                },
            }

            response = api.build_turn_response(state_values=state_values, streamed_text="")

            self.assertEqual(response.payload["session_context"]["thread_id"], "thread-a")
            self.assertEqual(response.payload["session_context"]["turn_id"], "thread-a:555")
            self.assertEqual(response.payload["session_context"]["turn_started_at"], 555)
            self.assertEqual(response.payload["session_context"]["user_id"], "okabe")
            self.assertEqual(response.payload["session_context"]["checkpoint_id"], "cp-2")
            self.assertEqual(response.payload["current_event"]["perception"]["thread_id"], "thread-a")
            self.assertEqual(response.payload["current_event"]["perception"]["turn_id"], "thread-a:555")

    def test_turn_response_backfills_sparse_event_perception_from_session_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "session_context": {
                    "thread_id": "thread-a",
                    "turn_id": "thread-a:555",
                    "channel": "system",
                    "modality": "system",
                    "source_role": "system",
                    "trust_tier": "high",
                    "salience": 0.58,
                    "interruptibility": "soft",
                    "delivery_mode": "scheduled",
                    "is_proactive": False,
                },
                "current_event": {
                    "kind": "idle",
                    "source": "scheduler",
                    "created_at": 555,
                    "perception": {},
                },
            }

            response = api.build_turn_response(state_values=state_values, streamed_text="")
            perception = response.payload["current_event"]["perception"]

            self.assertEqual(perception["thread_id"], "thread-a")
            self.assertEqual(perception["turn_id"], "thread-a:555")
            self.assertEqual(perception["event_id"], "thread-a:555:idle:scheduler")
            self.assertEqual(perception["channel"], "system")
            self.assertEqual(perception["modality"], "system")
            self.assertEqual(perception["source_role"], "system")
            self.assertEqual(perception["trust_tier"], "high")
            self.assertEqual(perception["salience"], 0.58)
            self.assertEqual(perception["interruptibility"], "soft")
            self.assertEqual(perception["delivery_mode"], "scheduled")
            self.assertFalse(perception["is_proactive"])

    def test_turn_response_prefers_live_pending_approval_intent_over_stale_recon_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "autonomy_intent": {
                    "mode": "queue_followthrough",
                    "origin": "counterpart_request",
                    "reason": "先守住边界和自我位置，再决定要不要继续靠近。",
                    "primary_proposal_id": "ap-old",
                },
                "action_packets": [
                    {
                        "proposal_id": "ap-pending-1",
                        "origin": "motive_goal",
                        "intent": "tool:write_diary",
                        "status": "awaiting_approval",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "capability_steps": [
                            {
                                "kind": "tool_call",
                                "name": "write_diary",
                                "target": "",
                                "status": "awaiting_approval",
                                "requires_approval": True,
                                "note": "",
                            }
                        ],
                        "expected_effect": "",
                        "result_summary": "",
                        "writeback_ready": False,
                        "tool_name": "write_diary",
                    }
                ],
                "pending_action_proposal": {
                    "proposal_id": "ap-pending-1",
                    "origin": "motive_goal",
                    "intent": "tool:write_diary",
                    "status": "awaiting_approval",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "capability_steps": [],
                    "expected_effect": "",
                    "result_summary": "",
                    "writeback_ready": False,
                },
                "current_event": {"kind": "user_utterance"},
                "reconsolidation_snapshot": {
                    "autonomy_intent": {
                        "mode": "queue_followthrough",
                        "origin": "counterpart_request",
                        "reason": "先守住边界和自我位置，再决定要不要继续靠近。",
                        "primary_proposal_id": "ap-old",
                    }
                },
            }

            response = api.build_turn_response(state_values=state_values, streamed_text="")

            self.assertEqual(response.payload["autonomy"]["intent"]["mode"], "approval_pending")
            self.assertEqual(response.payload["autonomy"]["intent"]["primary_proposal_id"], "ap-pending-1")
            self.assertEqual(response.payload["autonomy"]["pending_approval"]["proposal_id"], "ap-pending-1")

    def test_turn_and_event_responses_include_current_turn_writeback_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, session = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            session.memory_store = SimpleNamespace(
                list_revision_traces=lambda limit=60: [
                    {
                        "namespace": "semantic_self_evidence",
                        "target_id": "agency_style",
                        "after_summary": "她不会永远围着对方转。",
                        "source": "auto:passive_evolution_final",
                        "behavior_consequence": {
                            "embodied_context": {
                                "kind": "access_request_pending",
                                "summary": "这个改动还卡在审批口。",
                                "requested_access": ["workspace_write"],
                                "artifact_carrier": "source_ref",
                                "artifact_source_ref_ids": [17],
                                "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                                "artifact_source_query": "langgraph persistence checkpointer thread",
                                "artifact_source_title": "Persistence",
                                "artifact_source_tool_name": "search_web",
                                "requested_help": True,
                                "primary_status": "awaiting_approval",
                            }
                        },
                        "created_at": 531,
                    },
                    {
                        "namespace": "semantic_self_narratives",
                        "target_id": "12",
                        "after_summary": "她有自己的节奏和靠近方式。",
                        "reason": "semantic_reconsolidation",
                        "source": "auto:passive_evolution_final",
                        "interaction_carryover": {
                            "embodied_context": {
                                "kind": "environmental_friction",
                                "summary": "浏览器环境还没准备好。",
                                "missing_access": ["browser_session"],
                                "artifact_carrier": "source_ref",
                                "artifact_source_ref_ids": [17],
                                "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                                "artifact_source_query": "langgraph persistence checkpointer thread",
                                "artifact_source_title": "Persistence",
                                "artifact_source_tool_name": "search_web",
                                "environmental_friction": True,
                            }
                        },
                        "updated_at": 532,
                    },
                    {
                        "namespace": "semantic_self_evidence",
                        "target_id": "presence_style",
                        "after_summary": "旧的非本轮痕迹不该混进来。",
                        "source": "auto:passive_evolution_final",
                        "updated_at": 400,
                    },
                    {
                        "namespace": "semantic_self_evidence",
                        "target_id": "presence_style",
                        "after_summary": "非 final source 不该进入 finished-turn trace。",
                        "source": "auto:passive_evolution",
                        "updated_at": 540,
                    },
                ],
                list_semantic_self_narratives=lambda limit=20: [
                    {
                        "id": 12,
                        "category": "agency_style",
                        "text": "她有自己的节奏和靠近方式。",
                        "updated_at": 532,
                    },
                    {
                        "id": 15,
                        "category": "presence_style",
                        "text": "这条太早，不该被当成本轮写回。",
                        "updated_at": 400,
                    },
                ],
                list_counterpart_assessment_history=lambda limit=12: [
                    {
                        "summary": "她重新判断这次靠近是认真修复，不是敷衍找补。",
                        "stance": "repair_open",
                        "scene": "repair",
                        "created_at": 534,
                    },
                    {
                        "summary": "这条太早，不该被混入本轮写回。",
                        "stance": "guarded",
                        "scene": "friction",
                        "created_at": 401,
                    },
                ],
                list_proactive_continuity_history=lambda limit=12: [
                    {
                        "summary": "她把这轮余温收进后续小幅回头的连续性里。",
                        "kind": "promoted",
                        "trace_family": "continuity_recontact",
                        "created_at": 535,
                    },
                    {
                        "summary": "旧的 own-rhythm 记录不该混进本轮预览。",
                        "kind": "held",
                        "trace_family": "own_rhythm",
                        "created_at": 402,
                    },
                ],
            )
            state_values = {
                "session_context": {
                    "thread_id": "thread-a",
                    "turn_id": "thread-a:530",
                    "turn_started_at": 530,
                },
                "current_event": {
                    "kind": "user_utterance",
                    "created_at": 530,
                    "perception": {},
                },
            }

            event_response = api.build_event_round_response(
                state_values=state_values,
                final_text="我在。",
            )
            turn_response = api.build_turn_response(
                state_values=state_values,
                streamed_text="ignored",
            )

            for payload in (event_response.payload, turn_response.payload):
                writeback = payload["writeback_trace"]
                self.assertEqual(writeback["turn_started_at"], 530)
                self.assertEqual(len(writeback["revision_traces"]), 2)
                self.assertTrue(all(item["source"] == "auto:passive_evolution_final" for item in writeback["revision_traces"]))
                self.assertEqual(writeback["revision_traces"][0]["embodied_context"]["kind"], "access_request_pending")
                self.assertEqual(writeback["revision_traces"][0]["embodied_context"]["requested_access"], ["workspace_write"])
                self.assertEqual(writeback["revision_traces"][0]["embodied_context"]["artifact_carrier"], "source_ref")
                self.assertEqual(writeback["revision_traces"][0]["embodied_context"]["artifact_source_ref_ids"], [17])
                self.assertEqual(writeback["revision_traces"][0]["embodied_context"]["artifact_source_title"], "Persistence")
                self.assertEqual(writeback["revision_traces"][0]["embodied_context"]["artifact_source_tool_name"], "search_web")
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["kind"], "environmental_friction")
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["missing_access"], ["browser_session"])
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["artifact_carrier"], "source_ref")
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["artifact_source_ref_ids"], [17])
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["artifact_source_title"], "Persistence")
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["artifact_source_tool_name"], "search_web")
                self.assertEqual([item["category"] for item in writeback["semantic_self_narratives"]], ["agency_style"])
                self.assertEqual(writeback["semantic_self_narratives"][0]["text"], "她有自己的节奏和靠近方式。")
                self.assertEqual(
                    [item["summary"] for item in writeback["counterpart_assessment_history"]],
                    ["她重新判断这次靠近是认真修复，不是敷衍找补。"],
                )
                self.assertEqual(
                    [item["summary"] for item in writeback["proactive_continuity_history"]],
                    ["她把这轮余温收进后续小幅回头的连续性里。"],
                )

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

    def test_turn_and_event_responses_prefer_frozen_reconsolidation_behavior_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "behavior_action": {
                    "action_target": "hold_own_rhythm",
                    "interaction_mode": "self_activity_hold",
                    "primary_motive": "preserve_self_rhythm",
                    "motive_tension": "self_rhythm_vs_contact",
                    "goal_frame": "stale live action should not win",
                    "initiative_shape": "pause",
                    "initiative_level": 0.22,
                    "disclosure_posture": "tight",
                    "window_profile": {
                        "profile_type": "self_opening",
                        "decision": "hold_own_rhythm",
                        "readiness": 0.22,
                        "required_readiness": 0.49,
                        "reopen_ready": False,
                    },
                },
                "behavior_plan": {
                    "kind": "self_activity_continue",
                    "target": "self",
                    "trigger_family": "self_activity",
                },
                "interaction_carryover": {
                    "source": "live",
                    "strength": 0.14,
                    "carryover_mode": "fading_residue",
                    "relationship_weather": "thin_residue",
                },
                "reconsolidation_snapshot": {
                    "behavior_action": {
                        "action_target": "wait_and_recheck",
                        "interaction_mode": "deferred_watch",
                        "primary_motive": "honor_continuity",
                        "motive_tension": "contact_without_pressure",
                        "goal_frame": "顺着前面的惦记等更自然的时候再接回来。",
                        "deferred_action_family": "life_window",
                        "timing_window_min": 30,
                        "engagement_level": 0.61,
                        "initiative_level": 0.47,
                        "task_focus": "relationship",
                        "affect_surface": "gentle",
                        "silence_ok": True,
                        "proactive_checkin_readiness": 0.39,
                        "initiative_shape": "micro_opening",
                        "disclosure_posture": "measured",
                        "note": "顺着余温看一眼，但不立刻把距离拉近。",
                        "relationship_weather": "warm_residue",
                        "embodied_context": {
                            "kind": "access_request_pending",
                            "summary": "她把动作推进到了审批门口。",
                            "requested_access": ["workspace_write"],
                            "requested_help": True,
                            "primary_status": "awaiting_approval",
                        },
                        "window_profile": {
                            "profile_type": "self_opening",
                            "event_kind": "self_activity_state",
                            "family": "self_activity",
                            "trigger_family": "life_window",
                            "stance": "watchful",
                            "scene": "repair_attempt",
                            "decision": "wait_and_recheck",
                            "readiness": 0.41,
                            "required_readiness": 0.57,
                            "reopen_ready": False,
                            "recheck_min": 18,
                            "continuity_bonus": 0.14,
                            "carryover_mode": "own_rhythm",
                            "carryover_strength": 0.46,
                            "presence_residue": 0.33,
                            "ambient_resonance": 0.22,
                            "self_activity_momentum": 0.58,
                            "recontact_echo": 0.29,
                            "own_rhythm_load": 0.63,
                        },
                    },
                    "behavior_plan": {
                        "kind": "deferred_checkin",
                        "target": "counterpart",
                        "trigger_family": "observe",
                        "scheduled_after_min": 30,
                    },
                    "interaction_carryover": {
                        "source": "reconsolidation",
                        "strength": 0.53,
                        "carryover_mode": "own_rhythm",
                        "relationship_weather": "warm_residue",
                        "note": "final carryover should win",
                        "embodied_context": {
                            "kind": "access_request_pending",
                            "summary": "她把动作推进到了审批门口。",
                            "requested_access": ["workspace_write"],
                            "requested_help": True,
                            "primary_status": "awaiting_approval",
                        },
                    },
                },
                "current_event": {"kind": "self_activity_state", "event_frame": "idle continuation", "tags": []},
                "world_model_state": {"presence_residue": 0.42},
            }

            event_response = api.build_event_round_response(
                state_values=state_values,
                final_text="我在。",
            )
            turn_response = api.build_turn_response(
                state_values=state_values,
                streamed_text="ignored",
            )

            self.assertEqual(event_response.payload["behavior_action"]["action_target"], "wait_and_recheck")
            self.assertEqual(turn_response.payload["behavior_action"]["interaction_mode"], "deferred_watch")
            self.assertEqual(event_response.payload["behavior_action"]["timing_window_min"], 30)
            self.assertEqual(event_response.payload["behavior_action"]["initiative_shape"], "micro_opening")
            self.assertEqual(event_response.payload["behavior_action"]["initiative_level"], 0.47)
            self.assertEqual(turn_response.payload["behavior_action"]["engagement_level"], 0.61)
            self.assertEqual(turn_response.payload["behavior_action"]["disclosure_posture"], "measured")
            self.assertEqual(turn_response.payload["behavior_action"]["task_focus"], "relationship")
            self.assertTrue(turn_response.payload["behavior_action"]["silence_ok"])
            self.assertEqual(turn_response.payload["behavior_action"]["note"], "顺着余温看一眼，但不立刻把距离拉近。")
            self.assertEqual(event_response.payload["behavior_action"]["window_profile"]["decision"], "wait_and_recheck")
            self.assertEqual(turn_response.payload["behavior_action"]["window_profile"]["profile_type"], "self_opening")
            self.assertEqual(turn_response.payload["behavior_action"]["window_profile"]["recheck_min"], 18)
            self.assertEqual(turn_response.payload["behavior_plan"]["kind"], "deferred_checkin")
            self.assertEqual(event_response.payload["interaction_carryover"]["source"], "reconsolidation")
            self.assertEqual(turn_response.payload["interaction_carryover"]["carryover_mode"], "own_rhythm")
            self.assertEqual(turn_response.payload["interaction_carryover"]["strength"], 0.53)
            self.assertEqual(
                (turn_response.payload["interaction_carryover"].get("embodied_context") or {}).get("kind"),
                "access_request_pending",
            )
            self.assertEqual(
                (
                    (turn_response.payload["turn_summary"].get("interaction_carryover") or {}).get("embodied_context")
                    or {}
                ).get("kind"),
                "access_request_pending",
            )
            self.assertEqual(
                (
                    turn_response.payload["turn_summary"]
                    .get("current_turn", {})
                    .get("behavior_action_embodied_context", {})
                    .get("kind")
                ),
                "access_request_pending",
            )

    def test_turn_and_event_responses_prefer_frozen_behavior_plan_with_context_only_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "behavior_plan": {
                    "kind": "deferred_checkin",
                    "target": "counterpart",
                    "trigger_family": "observe",
                    "scheduled_after_min": 45,
                },
                "reconsolidation_snapshot": {
                    "behavior_plan": {
                        "note": "final frozen context should win",
                        "attention_target": "counterpart_state",
                        "nonverbal_signal": "quiet_glance",
                        "carryover_strength": 0.46,
                        "presence_residue": 0.33,
                        "ambient_resonance": 0.22,
                        "self_activity_momentum": 0.58,
                        "allow_interrupt": False,
                    }
                },
            }

            event_response = api.build_event_round_response(
                state_values=state_values,
                final_text="我在。",
            )
            turn_response = api.build_turn_response(
                state_values=state_values,
                streamed_text="ignored",
            )

            self.assertEqual(event_response.payload["behavior_plan"]["note"], "final frozen context should win")
            self.assertEqual(event_response.payload["behavior_plan"]["attention_target"], "counterpart_state")
            self.assertEqual(event_response.payload["behavior_plan"]["nonverbal_signal"], "quiet_glance")
            self.assertEqual(event_response.payload["behavior_plan"]["presence_residue"], 0.33)
            self.assertEqual(turn_response.payload["behavior_plan"]["ambient_resonance"], 0.22)
            self.assertEqual(turn_response.payload["behavior_plan"]["self_activity_momentum"], 0.58)
            self.assertEqual(turn_response.payload["behavior_plan"]["carryover_strength"], 0.46)
            self.assertFalse(turn_response.payload["behavior_plan"]["allow_interrupt"])
            self.assertNotIn("kind", event_response.payload["behavior_plan"])

    def test_turn_and_event_responses_preserve_embodied_only_behavior_payload_signals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "reconsolidation_snapshot": {
                    "behavior_action": {
                        "embodied_context": {
                            "kind": "access_request_pending",
                            "summary": "这一步还在等审批。",
                            "requested_access": ["workspace_write"],
                            "requested_help": True,
                            "primary_status": "awaiting_approval",
                        }
                    },
                    "behavior_plan": {
                        "embodied_context": {
                            "kind": "environmental_friction",
                            "summary": "浏览器会话还没准备好。",
                            "missing_access": ["browser_session"],
                            "environmental_friction": True,
                        }
                    },
                }
            }

            event_response = api.build_event_round_response(
                state_values=state_values,
                final_text="我在。",
            )
            turn_response = api.build_turn_response(
                state_values=state_values,
                streamed_text="ignored",
            )

            for payload in (event_response.payload, turn_response.payload):
                action_embodied = (
                    payload["behavior_action"].get("embodied_context")
                    if isinstance(payload.get("behavior_action"), dict)
                    and isinstance(payload["behavior_action"].get("embodied_context"), dict)
                    else {}
                )
                plan_embodied = (
                    payload["behavior_plan"].get("embodied_context")
                    if isinstance(payload.get("behavior_plan"), dict)
                    and isinstance(payload["behavior_plan"].get("embodied_context"), dict)
                    else {}
                )
                self.assertEqual(action_embodied.get("kind"), "access_request_pending")
                self.assertEqual(action_embodied.get("requested_access"), ["workspace_write"])
                self.assertEqual(plan_embodied.get("kind"), "environmental_friction")
                self.assertEqual(plan_embodied.get("missing_access"), ["browser_session"])

    def test_turn_and_event_responses_derive_plan_from_frozen_action_before_live_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "behavior_action": {
                    "action_target": "hold_own_rhythm",
                    "interaction_mode": "self_activity_hold",
                    "primary_motive": "preserve_self_rhythm",
                    "goal_frame": "stale live action should not win",
                },
                "behavior_plan": {
                    "kind": "self_activity_continue",
                    "target": "self",
                    "trigger_family": "self_activity",
                    "scheduled_after_min": 45,
                    "legacy_hint": "stale-live-plan",
                },
                "reconsolidation_snapshot": {
                    "behavior_action": {
                        "action_target": "wait_and_recheck",
                        "interaction_mode": "deferred_watch",
                        "primary_motive": "honor_continuity",
                        "motive_tension": "contact_without_pressure",
                        "goal_frame": "顺着前面的惦记等更自然的时候再接回来。",
                        "deferred_action_family": "life_window",
                        "timing_window_min": 30,
                        "relationship_weather": "warm_residue",
                    }
                },
                "current_event": {"kind": "self_activity_state"},
                "world_model_state": {"presence_residue": 0.42},
            }

            with patch(
                "amadeus_thread0.runtime.final_state._behavior_plan_from_action",
                return_value={
                    "kind": "deferred_checkin",
                    "target": "counterpart",
                    "trigger_family": "life_window",
                    "scheduled_after_min": 30,
                    "primary_motive": "honor_continuity",
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

            self.assertEqual(event_response.payload["behavior_action"]["action_target"], "wait_and_recheck")
            self.assertEqual(turn_response.payload["behavior_action"]["interaction_mode"], "deferred_watch")
            self.assertEqual(event_response.payload["behavior_plan"]["kind"], "deferred_checkin")
            self.assertEqual(turn_response.payload["behavior_plan"]["trigger_family"], "life_window")
            self.assertEqual(turn_response.payload["behavior_plan"]["scheduled_after_min"], 30)
            self.assertNotIn("legacy_hint", event_response.payload["behavior_plan"])
            self.assertNotIn("legacy_hint", turn_response.payload["behavior_plan"])
            self.assertEqual(mock_derive.call_count, 2)

    def test_turn_and_event_responses_reuse_carried_embodied_context_for_digital_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "current_event": {
                    "kind": "user_utterance",
                    "perception": {"channel": "chat", "modality": "text"},
                },
                "interaction_carryover": {
                    "source": "reconsolidation",
                    "carryover_mode": "own_rhythm",
                    "strength": 0.53,
                    "embodied_context": {
                        "kind": "access_request_pending",
                        "summary": "她把动作推进到了审批门口。",
                        "requested_access": ["workspace_write"],
                        "missing_access": ["workspace_write"],
                        "requested_help": True,
                        "primary_status": "awaiting_approval",
                    },
                },
            }

            event_response = api.build_event_round_response(
                state_values=state_values,
                final_text="我在。",
            )
            turn_response = api.build_turn_response(
                state_values=state_values,
                streamed_text="ignored",
            )

            for payload in (event_response.payload, turn_response.payload):
                self.assertEqual(payload["digital_body"]["active_surface"], "approval_gate")
                self.assertEqual(payload["digital_body"]["access_state"]["mode"], "approval_pending")
                self.assertIn("workspace_write", payload["digital_body"]["access_state"]["missing_access"])
                self.assertIn("human_approval", payload["digital_body"]["access_state"]["requestable_access"])


if __name__ == "__main__":
    unittest.main()
