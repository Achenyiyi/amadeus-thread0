from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from amadeus_thread0.runtime.backend_api import BackendAPI, BackendApiEnvelope
from amadeus_thread0.runtime.memory_admin import MemoryAdminService


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
        action_trace = values.get("action_trace") if isinstance(values.get("action_trace"), list) else []
        procedural_planning = (
            values.get("procedural_planning")
            if isinstance(values.get("procedural_planning"), dict)
            else {}
        )
        if not procedural_planning:
            for item in action_trace:
                if isinstance(item, dict) and isinstance(item.get("procedural_planning"), dict):
                    procedural_planning = dict(item.get("procedural_planning") or {})
                    break
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
                "digital_body_workspace_root": str(resource_state.get("workspace_root") or "").strip(),
                "digital_body_artifact_reacquisition_mode": str(resource_state.get("artifact_reacquisition_mode") or "").strip(),
                "digital_body_preferred_source_ref_id": int(resource_state.get("preferred_source_ref_id") or 0),
                "digital_body_preferred_anchor_reason": str(resource_state.get("preferred_anchor_reason") or "").strip(),
                "digital_body_consequence_kind": str(digital_body_consequence.get("kind") or "").strip(),
                "digital_body_consequence_summary": str(digital_body_consequence.get("summary") or "").strip(),
                "digital_body_consequence_preferred_source_ref_id": int(
                    digital_body_consequence.get("preferred_source_ref_id") or 0
                ),
                "digital_body_consequence_preferred_anchor_reason": str(
                    digital_body_consequence.get("preferred_anchor_reason") or ""
                ).strip(),
                "procedural_planning": dict(procedural_planning),
            },
            "autonomy": {
                "procedural_planning": dict(procedural_planning),
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
        data = values if isinstance(values, dict) else {}
        return str(data.get("final_text") or "final from session")


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

    def test_runtime_productization_envelope_reports_operator_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)

            payload = api.runtime_productization().payload

            self.assertEqual(payload["schema"], "operator_readback.v2")
            self.assertEqual(payload["readiness_status"], "runtime_productization_phase2_ready")
            self.assertEqual(payload["console_summary"]["mode"], "readback_only")
            self.assertFalse(payload["authority_boundary"]["persona_core_mutation_allowed"])
            self.assertEqual(payload["inputs"]["post_baseline"]["readiness_status"], "post_baseline_closure_ready")
            self.assertEqual(payload["inputs"]["post_unlock_roadmap"]["readiness_status"], "post_unlock_roadmap_ready")

    def test_turn_and_event_responses_attach_operator_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "autonomy_intent": {"mode": "assist", "origin": "motive_goal"},
                "action_packets": [
                    {
                        "proposal_id": "ap-runtime-productization",
                        "intent": "sandbox:execute_workspace_command",
                        "status": "completed",
                        "risk": "external_mutation",
                        "requires_approval": True,
                    }
                ],
                "digital_body_consequence": {"kind": "sandbox_execution_completed"},
            }

            turn_payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload
            event_payload = api.build_event_round_response(
                state_values=state_values,
                final_text="done",
            ).payload

            self.assertEqual(turn_payload["operator_readback"]["schema"], "operator_readback.v2")
            self.assertEqual(turn_payload["operator_readback"]["readiness_status"], "runtime_productization_phase2_ready")
            self.assertEqual(
                turn_payload["operator_readback"]["operator_snapshot"]["digital_body_consequence_kind"],
                "sandbox_execution_completed",
            )
            self.assertEqual(event_payload["operator_readback"]["readiness_status"], "runtime_productization_phase2_ready")

    def test_turn_and_event_responses_attach_living_loop_realism_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            final_text = "嗯。我听见了。边界还在，但这次我会先把话放轻一点。"
            state_values = {
                "final_text": final_text,
                "current_event": {
                    "kind": "user_utterance",
                    "text": "之前那件事我一直记着，我们能慢慢聊吗？",
                    "tags": ["repair", "relationship"],
                    "created_at": 1_777_777_001,
                },
                "session_context": {"thread_id": "thread-a", "turn_started_at": 1_777_777_001},
                "turn_appraisal": {
                    "scene": "repair_attempt",
                    "interaction_frame": "relationship",
                    "signals": {"repair": True, "care": True},
                },
                "emotion_state": {"label": "hurt", "valence": -0.08, "arousal": 0.22},
                "bond_state": {"trust": 0.60, "closeness": 0.58, "hurt": 0.14, "repair_confidence": 0.66},
                "allostasis_state": {"autonomy_need": 0.38, "safety_need": 0.42, "cognitive_budget": 0.70},
                "counterpart_assessment": {
                    "stance": "watchful",
                    "scene": "repair_attempt",
                    "boundary_pressure": 0.18,
                    "reliability_read": 0.62,
                },
                "semantic_narrative_profile": {
                    "repair_residue": 0.76,
                    "continuity_depth": 0.68,
                    "commitment_carry": 0.62,
                    "continuity_axes": [{"category": "repair_style", "score": 0.74}],
                },
                "behavior_action": {
                    "interaction_mode": "low_pressure_support",
                    "action_target": "low_pressure_hold",
                    "primary_motive": "support_without_pressure",
                    "motive_tension": "boundary_vs_closeness",
                    "goal_frame": "先低负担接住，不接管对方节奏。",
                },
                "behavior_plan": {
                    "kind": "low_pressure_support",
                    "interaction_mode": "low_pressure_support",
                    "primary_motive": "support_without_pressure",
                    "goal_frame": "先低负担接住，不接管对方节奏。",
                },
                "digital_body_consequence": {"kind": "relationship_repair_acknowledged"},
                "reconsolidation_snapshot": {
                    "behavior_action": {"primary_motive": "support_without_pressure"},
                    "behavior_plan": {"kind": "low_pressure_support", "primary_motive": "support_without_pressure"},
                    "digital_body_consequence": {"kind": "relationship_repair_acknowledged"},
                    "final_text": final_text,
                },
                "writeback_trace": {
                    "revision_traces": [{"namespace": "semantic_self_evidence", "target_id": "repair_style"}],
                    "counterpart_assessment_history": [{"stance": "watchful", "scene": "repair_attempt"}],
                },
            }

            turn_payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload
            event_payload = api.build_event_round_response(
                state_values=state_values,
                final_text=final_text,
            ).payload

            for payload in (turn_payload, event_payload):
                readback = payload["living_loop_realism"]
                self.assertEqual(readback["schema"], "living_loop_realism.backend_payload.v1")
                self.assertEqual(readback["readiness_status"], "living_loop_runtime_realism_phase2_ready")
                self.assertEqual(readback["backend_payload"]["status"], "ready")
                self.assertEqual(readback["causality"]["status"], "ready")

    def test_memory_snapshot_normalizes_revision_trace_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            session = FakeBackendSession()
            raw_snapshot = {
                "profile": {"name": "okabe"},
                "source_refs": [
                    {
                        "content": {
                            "source_id": "17",
                            "title": " Persistence ",
                            "tool_name": " search_web ",
                            "embodied_context": {
                                "kind": "source_material_compared",
                                "artifact_source_ref_ids": ["17", "9"],
                                "preferred_source_ref_id": "17",
                                "preferred_anchor_reason": " currently_active ",
                                "artifact_source_title": "Persistence",
                                "artifact_source_tool_name": "search_web",
                            },
                        }
                    }
                ],
                "revision_traces": [
                    {
                        "namespace": "semantic_self_narratives",
                        "target_id": "14",
                        "content": {
                            "summary": " 刚刚刷新过一次入口状态 ",
                            "embodied_context": {
                                "kind": "access_state_refreshed",
                                "api_key_state": " present ",
                                "quota_state": " healthy ",
                                "filesystem_state": " writable ",
                                "network_access": " enabled ",
                                "session_continuity": " stable ",
                            },
                        },
                        "interaction_carryover": {
                            "embodied_context": {
                                "kind": "access_state_refreshed",
                                "api_key_state": "present",
                                "quota_state": "healthy",
                                "filesystem_state": "writable",
                                "network_access": "enabled",
                                "session_continuity": "stable",
                            }
                        },
                    }
                ],
            }
            memory_admin = MemoryAdminService(
                memory_store=SimpleNamespace(snapshot=lambda: raw_snapshot),
                llm_factory=lambda **_: None,
            )
            settings = SimpleNamespace(
                checkpoint_db_path=checkpoint_db,
                data_dir=root,
                model_provider="dashscope",
                model_name="qwen3.5-plus",
                model_base_url="",
                runtime_mode="cli",
            )
            runtime_bundle = SimpleNamespace(
                thread_id="thread-a",
                backend_session=session,
                memory_admin=memory_admin,
                settings=settings,
            )
            api = BackendAPI(runtime_bundle=runtime_bundle, base_data_dir=root, cwd=root)

            payload = api.memory_snapshot().payload

            self.assertEqual(payload["revision_traces"][0]["embodied_context"]["kind"], "access_state_refreshed")
            self.assertEqual(payload["revision_traces"][0]["embodied_context"]["api_key_state"], "present")
            self.assertEqual(payload["revision_traces"][0]["embodied_context"]["quota_state"], "healthy")
            self.assertEqual(payload["revision_traces"][0]["embodied_context"]["session_continuity"], "stable")
            self.assertEqual(payload["revision_traces"][0]["content"]["summary"], "刚刚刷新过一次入口状态")
            self.assertEqual(payload["revision_traces"][0]["content"]["embodied_context"]["api_key_state"], "present")
            self.assertEqual(payload["revision_traces"][0]["content"]["embodied_context"]["quota_state"], "healthy")
            self.assertEqual(payload["revision_traces"][0]["content"]["embodied_context"]["session_continuity"], "stable")
            self.assertEqual(
                payload["revision_traces"][0]["interaction_carryover"]["embodied_context"]["api_key_state"],
                "present",
            )
            self.assertEqual(
                payload["revision_traces"][0]["interaction_carryover"]["embodied_context"]["session_continuity"],
                "stable",
            )
            self.assertIn("bodyfx=access_state_refreshed", payload["revision_traces"][0].get("preview_line") or "")
            self.assertEqual(payload["source_refs"][0]["id"], 17)
            self.assertEqual(payload["source_refs"][0]["source_id"], 17)
            self.assertEqual(payload["source_refs"][0]["title"], "Persistence")
            self.assertEqual(payload["source_refs"][0]["tool_name"], "search_web")
            self.assertEqual(payload["source_refs"][0]["embodied_context"]["preferred_source_ref_id"], 17)
            self.assertEqual(payload["source_refs"][0]["embodied_context"]["artifact_source_ref_ids"], [17, 9])
            self.assertEqual(payload["source_refs"][0]["embodied_context"]["preferred_anchor_reason"], "currently_active")
            self.assertEqual(payload["source_refs"][0]["content"]["title"], "Persistence")
            self.assertEqual(payload["source_refs"][0]["content"]["tool_name"], "search_web")
            self.assertEqual(payload["source_refs"][0]["content"]["embodied_context"]["preferred_source_ref_id"], 17)
            self.assertEqual(payload["source_refs"][0]["content"]["embodied_context"]["artifact_source_ref_ids"], [17, 9])
            self.assertEqual(
                payload["source_refs"][0]["content"]["embodied_context"]["preferred_anchor_reason"],
                "currently_active",
            )
            self.assertIn("bodyfx=source_material_compared", payload["source_refs"][0].get("preview_line") or "")
            self.assertIn("source=Persistence", payload["source_refs"][0].get("preview_line") or "")
            self.assertNotIn("embodied_context", raw_snapshot["revision_traces"][0])
            self.assertNotIn("embodied_context", raw_snapshot["source_refs"][0])

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
            self.assertIsNot(session.last_summary_state, state_values)
            self.assertEqual(
                (session.last_summary_state.get("digital_body_consequence") or {}).get("kind"),
                "embodied_growth",
            )
            self.assertEqual(
                (session.last_summary_state.get("counterpart_assessment") or {}).get("scene"),
                "repair_attempt",
            )

    def test_turn_response_surfaces_live_browser_runtime_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "current_event": {"kind": "user_utterance"},
                "autonomy_intent": {
                    "mode": "execute",
                    "origin": "counterpart_request",
                    "primary_proposal_id": "ap-browser-open-api-1",
                },
                "digital_body_state": {
                    "active_surface": "tooling",
                    "perception_channels": ["dialogue", "browser"],
                    "action_channels": ["language", "structured_action", "tooling"],
                    "world_surfaces": ["browser", "filesystem"],
                    "access_state": {
                        "mode": "tool_enabled",
                        "browser_session": "present",
                        "browser_runtime_state": {
                            "availability": "available",
                            "profile_root": "E:/runtime/browser/profiles/thread-a",
                            "context_status": "active",
                            "active_page_id": "page-1",
                            "active_tab_count": 1,
                            "downloads_dir": "E:/runtime/browser/downloads/thread-a",
                            "last_action_status": "completed",
                            "last_run_id": "ap-browser-open-api-1",
                            "manual_takeover_required": False,
                            "runner_kind": "playwright_persistent_context",
                            "isolation_level": "persistent_profile_runtime",
                        },
                    },
                    "resource_state": {
                        "artifact_continuity": "attached",
                        "active_artifact_kind": "page",
                        "active_artifact_ref": "page:page-1",
                        "active_artifact_label": "Docs",
                        "artifact_carrier": "browser_page",
                        "artifact_source_url": "https://example.com/docs",
                        "browser_profile_id": "thread-a",
                        "browser_tab_id": "tab-1",
                    },
                },
                "action_packets": [
                    {
                        "proposal_id": "ap-browser-open-api-1",
                        "origin": "counterpart_request",
                        "intent": "browser:open_url",
                        "status": "completed",
                        "risk": "read",
                        "requires_approval": False,
                        "tool_name": "browser_open_url",
                        "browser_execution_spec": {
                            "operation": "open_url",
                            "profile_id": "thread-a",
                            "navigation_url": "https://example.com/docs",
                            "allowed_roots": ["E:/runtime/workspaces/lab"],
                            "browser_downloads_root": "E:/runtime/browser/downloads/thread-a",
                            "timeout_s": 20,
                            "wait_until": "load",
                        },
                        "browser_execution_preview": {
                            "runner_kind": "playwright_persistent_context",
                            "isolation_level": "persistent_profile_runtime",
                            "operation": "open_url",
                            "profile_id": "thread-a",
                            "page_url": "https://example.com/docs",
                            "page_title": "Docs",
                            "allowed_roots": ["E:/runtime/workspaces/lab"],
                            "downloads_root": "E:/runtime/browser/downloads/thread-a",
                            "timeout_s": 20,
                            "verification_summary": "open the requested page in the persistent browser profile",
                        },
                        "browser_execution_result": {
                            "run_id": "ap-browser-open-api-1",
                            "status": "completed",
                            "profile_id": "thread-a",
                            "page_id": "page-1",
                            "tab_id": "tab-1",
                            "url": "https://example.com/docs",
                            "title": "Docs",
                            "action_kind": "open_url",
                            "target_ref": "",
                            "duration_ms": 41,
                            "active_tab_count": 1,
                            "last_action_status": "completed",
                            "download_path": "",
                            "upload_source": "",
                            "error_summary": "",
                            "manual_takeover_required": False,
                        },
                    }
                ],
                "digital_body_consequence": {
                    "kind": "browser_navigation_completed",
                    "summary": "The requested page is now open in the live browser runtime.",
                    "browser_run_id": "ap-browser-open-api-1",
                    "browser_profile_id": "thread-a",
                    "browser_page_id": "page-1",
                    "browser_tab_id": "tab-1",
                    "browser_url": "https://example.com/docs",
                    "browser_title": "Docs",
                    "browser_last_action_kind": "open_url",
                    "browser_last_exit_status": "completed",
                },
            }

            payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload

            self.assertEqual(payload["autonomy"]["action_packets"][0]["intent"], "browser:open_url")
            self.assertEqual(payload["autonomy"]["action_packets"][0]["browser_execution_result"]["run_id"], "ap-browser-open-api-1")
            self.assertEqual(payload["digital_body"]["access_state"]["browser_runtime_state"]["last_run_id"], "ap-browser-open-api-1")
            self.assertEqual(payload["digital_body"]["resource_state"]["browser_profile_id"], "thread-a")
            self.assertEqual(payload["digital_body_consequence"]["kind"], "browser_navigation_completed")
            self.assertEqual(payload["digital_body_consequence"]["browser_tab_id"], "tab-1")

    def test_turn_response_normalizes_source_material_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "session_context": {"thread_id": "thread-a", "turn_started_at": 1710000200},
                "claim_links": [
                    {
                        "content": {
                            "claim_excerpt": " 这一段引用需要收口 ",
                            "source_ids": ["9", "9", "0"],
                            "embodied_context": {
                                "kind": "source_material_compared",
                                "artifact_carrier": "source_ref",
                                "artifact_source_ref_ids": ["9", "17", "9"],
                                "preferred_source_ref_id": "9",
                                "preferred_anchor_reason": "primary_more_current",
                                "artifact_source_title": " paper ",
                            },
                            "sources": [
                                {
                                    "source_id": "9",
                                    "content": {
                                        "title": " paper ",
                                        "url": " https://example.com/paper ",
                                        "tool_name": " web_search ",
                                        "query": " amadeus source contract ",
                                        "snippet": " excerpt ",
                                        "embodied_context": {
                                            "kind": "source_material_compared",
                                            "artifact_carrier": "source_ref",
                                            "artifact_source_ref_ids": ["9", "17", "9"],
                                            "preferred_source_ref_id": "9",
                                            "preferred_anchor_reason": "primary_more_current",
                                            "artifact_source_title": " paper ",
                                        },
                                    },
                                }
                            ],
                        },
                    }
                ],
                "evidence_pack": [
                    {
                        "source_id": "9",
                        "content": {
                            "title": " paper ",
                            "url": " https://example.com/paper ",
                            "tool_name": " web_search ",
                            "query": " amadeus source contract ",
                            "snippet": " excerpt ",
                            "embodied_context": {
                                "kind": "source_material_compared",
                                "artifact_carrier": "source_ref",
                                "artifact_source_ref_ids": ["9", "17", "9"],
                                "preferred_source_ref_id": "9",
                                "preferred_anchor_reason": "primary_more_current",
                                "artifact_source_title": " paper ",
                            },
                        },
                    }
                ],
            }

            response = api.build_turn_response(
                state_values=state_values,
                streamed_text="ignored",
                meta={"source": "cli"},
            )

            self.assertEqual(response.payload["sources"][0]["id"], 9)
            self.assertEqual(response.payload["sources"][0]["source_id"], 9)
            self.assertEqual(response.payload["sources"][0]["title"], "paper")
            self.assertEqual(response.payload["sources"][0]["embodied_context"]["kind"], "source_material_compared")
            self.assertIn("bodyfx=source_material_compared", response.payload["sources"][0].get("preview_line") or "")
            self.assertIn("source=paper", response.payload["sources"][0].get("preview_line") or "")
            self.assertEqual(response.payload["claim_links"][0]["claim_excerpt"], "这一段引用需要收口")
            self.assertEqual(response.payload["claim_links"][0]["source_ids"], [9])
            self.assertEqual(response.payload["claim_links"][0]["embodied_context"]["preferred_source_ref_id"], 9)
            self.assertEqual(response.payload["claim_links"][0]["embodied_context"]["artifact_source_ref_ids"], [9, 17])
            self.assertEqual(
                response.payload["claim_links"][0]["embodied_context"]["preferred_anchor_reason"],
                "primary_more_current",
            )
            self.assertIn("bodyfx=source_material_compared", response.payload["claim_links"][0].get("preview_line") or "")
            self.assertIn("source=paper", response.payload["claim_links"][0].get("preview_line") or "")
            self.assertEqual(response.payload["claim_links"][0]["sources"][0]["source_id"], 9)
            self.assertEqual(response.payload["claim_links"][0]["sources"][0]["title"], "paper")
            self.assertEqual(
                response.payload["claim_links"][0]["sources"][0]["embodied_context"]["preferred_source_ref_id"],
                9,
            )
            self.assertIn(
                "bodyfx=source_material_compared",
                response.payload["claim_links"][0]["sources"][0].get("preview_line") or "",
            )
            self.assertIn("source=paper", response.payload["claim_links"][0]["sources"][0].get("preview_line") or "")

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
                session_state = payload["digital_body"]["access_state"]["session_state"]
                self.assertEqual(session_state["continuity"], "expiring")
                self.assertEqual(session_state["expires_in_s"], 600)
                self.assertEqual(session_state["recovery_mode"], "refresh_session")
                self.assertEqual(session_state["browser_session"], "present")
                self.assertTrue(session_state["needs_recovery"])
                account_detail = payload["digital_body"]["access_state"]["account_state_detail"]
                self.assertEqual(account_detail["login_state"], "logged_in")
                self.assertEqual(account_detail["cookie_state"], "present")
                self.assertTrue(account_detail["account_available"])
                self.assertTrue(account_detail["cookie_available"])
                self.assertEqual(payload["turn_summary"]["current_turn"]["digital_body_session_continuity"], "expiring")
                self.assertEqual(payload["turn_summary"]["current_turn"]["digital_body_session_expires_in_s"], 600)
                self.assertEqual(payload["turn_summary"]["current_turn"]["digital_body_session_recovery_mode"], "refresh_session")
                self.assertEqual(payload["digital_body_consequence"]["session_continuity"], "expired")
                self.assertEqual(payload["digital_body_consequence"]["session_recovery_mode"], "refresh_session")
                consequence_session = payload["digital_body_consequence"]["session_state"]
                self.assertEqual(consequence_session["continuity"], "expired")
                self.assertEqual(consequence_session["recovery_mode"], "refresh_session")
                self.assertTrue(consequence_session["needs_recovery"])
                consequence_account = payload["digital_body_consequence"]["account_state_detail"]
                self.assertEqual(consequence_account["login_state"], "logged_in")
                self.assertEqual(consequence_account["cookie_state"], "present")
                self.assertTrue(consequence_account["account_available"])

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
                            "pending_grants": ["api_key"],
                            "completion_ratio": 0.0,
                            "requires_operator": True,
                        },
                    },
                    "resource_state": {},
                },
                "reconsolidation_snapshot": {
                    "digital_body_consequence": {
                        "kind": "access_request_pending",
                        "summary": "当前还缺一个可用 API key，需要外部提供。",
                        "missing_access": ["api_key"],
                        "requested_access": ["api_key", "human_approval"],
                        "selected_access_proposal": {
                            "target": "api_key",
                            "mode": "operator_provide_api_key",
                            "summary": "先补一个可用 API key。",
                            "operator_action": "填入一个可用 key。",
                            "grants": ["api_key"],
                            "pending_grants": ["api_key"],
                            "completion_ratio": 0.0,
                            "requires_operator": True,
                        },
                        "permission_state": {
                            "pending_approval_count": 1,
                            "missing_access": ["api_key"],
                            "requestable_access": ["api_key", "human_approval"],
                            "selected_access_proposal": {
                                "target": "api_key",
                                "mode": "operator_provide_api_key",
                                "summary": "先补一个可用 API key。",
                                "operator_action": "填入一个可用 key。",
                                "grants": ["api_key"],
                                "pending_grants": ["api_key"],
                                "completion_ratio": 0.0,
                                "requires_operator": True,
                            },
                        },
                    }
                },
            }

            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")
            event_response = api.build_event_round_response(state_values=state_values, final_text="ignored")
            for payload in (turn_response.payload, event_response.payload):
                access_state = payload["digital_body"]["access_state"]
                self.assertEqual(access_state["access_acquire_proposals"][0]["target"], "api_key")
                self.assertEqual(access_state["selected_access_proposal"]["mode"], "operator_provide_api_key")
                permission_state = access_state["permission_state"]
                self.assertEqual(permission_state["approval_state"], "approval_pending")
                self.assertEqual(permission_state["pending_grants"], ["api_key"])
                self.assertEqual(permission_state["completion_ratio"], 0.0)
                self.assertEqual(permission_state["selected_access_proposal"]["mode"], "operator_provide_api_key")
                summary_body = payload["turn_summary"]["digital_body"]
                summary_access = (
                    summary_body["access"]
                    if isinstance(summary_body, dict) and isinstance(summary_body.get("access"), dict)
                    else summary_body["access_state"]
                )
                self.assertEqual(summary_access["access_acquire_proposals"][0]["grants"], ["api_key"])
                self.assertTrue(summary_access["selected_access_proposal"]["requires_operator"])
                self.assertEqual(summary_access["permission_state"]["approval_state"], "approval_pending")
                self.assertEqual(summary_access["permission_state"]["pending_grants"], ["api_key"])
                consequence = payload["digital_body_consequence"]
                self.assertEqual(consequence["access_acquire_proposals"][0]["target"], "api_key")
                self.assertEqual(consequence["selected_access_proposal"]["mode"], "operator_provide_api_key")
                self.assertEqual(consequence["permission_state"]["approval_state"], "approval_pending")
                self.assertEqual(consequence["permission_state"]["pending_grants"], ["api_key"])
                self.assertEqual(
                    consequence["permission_state"]["selected_access_proposal"]["mode"],
                    "operator_provide_api_key",
                )

    def test_turn_response_surfaces_access_assist_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            proposal = {
                "target": "filesystem",
                "mode": "operator_create_workspace",
                "summary": "先新建一个可写工作区。",
                "operator_action": "新建一个可写工作区。",
                "grants": ["filesystem", "workspace_write"],
                "requires_operator": True,
            }
            state_values = {
                "digital_body_state": {
                    "access_state": {
                        "mode": "approval_pending",
                        "missing_access": ["filesystem", "workspace_write"],
                        "requestable_access": ["filesystem", "workspace_write", "human_approval"],
                        "selected_access_proposal": proposal,
                        "access_acquire_proposals": [proposal],
                    },
                    "resource_state": {},
                },
                "pending_action_proposal": {
                    "proposal_id": "ap-access-assist-api",
                    "intent": "access:request_help",
                    "status": "awaiting_approval",
                    "risk": "external_mutation",
                    "requires_approval": True,
                    "access_acquire_proposals": [proposal],
                    "selected_access_proposal": proposal,
                },
            }

            payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload

            assist = payload["autonomy"]["pending_approval"]["assist_request"]
            self.assertEqual(assist["kind"], "grant_access")
            self.assertEqual(assist["resume_mode"], "auto_continue")
            self.assertEqual(assist["selected_access_proposal"]["mode"], "operator_create_workspace")
            self.assertIn("工作区写入入口", assist["message"])

    def test_turn_response_surfaces_manual_takeover_assist_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "action_packets": [
                    {
                        "proposal_id": "ap-browser-takeover-api",
                        "intent": "browser:fill",
                        "status": "blocked",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "tool_name": "browser_fill",
                        "browser_execution_preview": {
                            "operation": "fill",
                            "profile_id": "thread-browser",
                            "page_ref": "page:page-1",
                            "page_title": "Login",
                            "target_ref": "password",
                            "target_label": "密码输入框",
                            "requires_manual_takeover": True,
                        },
                        "browser_execution_result": {
                            "status": "blocked",
                            "profile_id": "thread-browser",
                            "page_id": "page-1",
                            "tab_id": "tab-1",
                            "title": "Login",
                            "target_ref": "password",
                            "manual_takeover_required": True,
                        },
                    }
                ],
                "digital_body_state": {
                    "access_state": {
                        "browser_runtime_state": {
                            "availability": "available",
                            "context_status": "manual_takeover",
                            "manual_takeover_required": True,
                            "last_run_id": "ap-browser-takeover-api",
                        }
                    },
                    "resource_state": {"active_artifact_label": "Login"},
                },
            }

            payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload

            pending = payload["autonomy"]["pending_approval"]
            self.assertEqual(pending["proposal_id"], "ap-browser-takeover-api")
            self.assertEqual(pending["assist_request"]["kind"], "manual_takeover")
            self.assertTrue(pending["assist_request"]["requires_manual_takeover"])
            self.assertEqual(pending["assist_request"]["profile_id"], "thread-browser")
            self.assertIn("密码、OTP、passkey、验证码", pending["assist_request"]["message"])

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

    def test_turn_and_event_responses_preserve_tts_presence_timing_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, session = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "current_event": {
                    "kind": "tts_presence_timing_observation",
                    "source": "tts",
                    "created_at": 1710000211,
                    "perception": {
                        "channel": "voice",
                        "modality": "TTS_presence_timing",
                        "source_role": "runtime",
                        "trust_tier": "high_runtime_telemetry",
                        "delivery_mode": "spoken",
                    },
                },
                "digital_body_state": {
                    "active_surface": "voice",
                    "perception_channels": ["voice", "TTS_presence_timing"],
                    "action_channels": ["language", "voice"],
                    "world_surfaces": ["tts"],
                    "access_state": {
                        "mode": "native_only",
                        "tts_presence_state": {
                            "availability": "available",
                            "enabled": True,
                            "backend": "dashscope_realtime",
                            "voice_profile_id": "default",
                            "queue_state": "idle",
                            "last_status": "delivered",
                            "last_run_id": "evt_tts_20260505_0001",
                        },
                    },
                    "resource_state": {
                        "tts_presence_timing": {
                            "last_event_id": "evt_tts_20260505_0001",
                            "last_delivery_mode": "spoken",
                            "last_actual_start_delay_ms": 180,
                            "last_duration_ms": 3120,
                            "last_pause_profile": "direct",
                        }
                    },
                },
                "reconsolidation_snapshot": {
                    "digital_body_consequence": {
                        "kind": "tts_presence_delivered",
                        "summary": "TTS delivered the frozen final text.",
                        "tts_presence_timing": {
                            "delivery_mode": "spoken",
                            "actual_start_delay_ms": 180,
                            "duration_ms": 3120,
                            "pause_profile": "direct",
                        },
                    }
                },
            }

            event_response = api.build_event_round_response(state_values=state_values, final_text="收到了。")
            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")

            for payload in (event_response.payload, turn_response.payload):
                self.assertEqual(payload["current_event"]["perception"]["modality"], "TTS_presence_timing")
                self.assertEqual(payload["digital_body"]["access_state"]["tts_presence_state"]["last_status"], "delivered")
                self.assertEqual(payload["digital_body"]["access_state"]["tts_presence_state"]["backend"], "dashscope_realtime")
                self.assertEqual(payload["digital_body"]["resource_state"]["tts_presence_timing"]["last_delivery_mode"], "spoken")
                self.assertEqual(payload["digital_body"]["resource_state"]["tts_presence_timing"]["last_duration_ms"], 3120)
                self.assertEqual(payload["digital_body_consequence"]["kind"], "tts_presence_delivered")
                self.assertEqual(payload["digital_body_consequence"]["tts_presence_timing"]["delivery_mode"], "spoken")
                self.assertEqual(
                    session.last_summary_state["digital_body_state"]["access_state"]["tts_presence_state"]["last_status"],
                    "delivered",
                )

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
                        "workspace_root": "E:/runtime/workspaces/lab-notes",
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
                self.assertEqual(payload["digital_body"]["resource_state"]["workspace_root"], "E:/runtime/workspaces/lab-notes")
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
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_workspace_root"],
                    "E:/runtime/workspaces/lab-notes",
                )

    def test_turn_and_event_responses_surface_workspace_file_updated_consequence(self):
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
                        "completed_packet_count": 1,
                        "external_tool_count": 1,
                        "artifact_continuity": "attached",
                        "active_artifact_kind": "file",
                        "active_artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                        "active_artifact_label": "today.md",
                        "workspace_root": "E:/runtime/workspaces/lab-notes",
                    },
                },
                "action_packets": [
                    {
                        "proposal_id": "ap-file-append-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:append_file",
                        "status": "completed",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "tool_name": "append_workspace_file",
                        "result_summary": "已把内容续写进 today.md，这条文件工作面现在接上了。",
                        "writeback_ready": True,
                        "artifact_context": {
                            "carrier": "filesystem",
                            "artifact_kind": "file",
                            "artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                            "artifact_label": "today.md",
                            "workspace_root": "E:/runtime/workspaces/lab-notes",
                            "reacquisition_mode": "reopen_file",
                            "exists": True,
                        },
                    }
                ],
            }

            event_response = api.build_event_round_response(state_values=state_values, final_text="我把文件接着往下写了。")
            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")

            for payload in (event_response.payload, turn_response.payload):
                self.assertEqual(payload["digital_body"]["resource_state"]["active_artifact_kind"], "file")
                self.assertEqual(payload["digital_body"]["resource_state"]["active_artifact_label"], "today.md")
                self.assertEqual(payload["digital_body_consequence"]["kind"], "workspace_file_updated")
                self.assertEqual(payload["digital_body_consequence"]["primary_tool_name"], "append_workspace_file")
                self.assertEqual(payload["digital_body_consequence"]["artifact_mutation_mode"], "append")
                self.assertEqual(payload["digital_body_consequence"]["active_artifact_kind"], "file")
                self.assertEqual(payload["digital_body_consequence"]["active_artifact_label"], "today.md")
                self.assertEqual(payload["digital_body_consequence"]["workspace_root"], "E:/runtime/workspaces/lab-notes")
                self.assertTrue(bool(payload["digital_body_consequence"]["procedural_growth"]))
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_consequence_kind"],
                    "workspace_file_updated",
                )
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_consequence_summary"],
                    payload["digital_body_consequence"]["summary"],
                )

    def test_turn_and_event_responses_surface_workspace_line_replace_consequence(self):
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
                        "completed_packet_count": 1,
                        "external_tool_count": 1,
                        "artifact_continuity": "attached",
                        "active_artifact_kind": "file",
                        "active_artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                        "active_artifact_label": "today.md",
                    },
                },
                "action_packets": [
                    {
                        "proposal_id": "ap-file-lines-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:replace_lines",
                        "status": "completed",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "tool_name": "replace_workspace_lines",
                        "result_summary": "已在 today.md 里替换第 2 行，这条文件工作面现在接上了。",
                        "writeback_ready": True,
                        "artifact_context": {
                            "carrier": "filesystem",
                            "artifact_kind": "file",
                            "artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                            "artifact_label": "today.md",
                            "reacquisition_mode": "reopen_file",
                            "exists": True,
                        },
                    }
                ],
            }

            event_response = api.build_event_round_response(state_values=state_values, final_text="我把第二行改掉了。")
            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")

            for payload in (event_response.payload, turn_response.payload):
                self.assertEqual(payload["digital_body"]["resource_state"]["active_artifact_kind"], "file")
                self.assertEqual(payload["digital_body"]["resource_state"]["active_artifact_label"], "today.md")
                self.assertEqual(payload["digital_body_consequence"]["kind"], "workspace_file_updated")
                self.assertEqual(payload["digital_body_consequence"]["primary_tool_name"], "replace_workspace_lines")
                self.assertEqual(payload["digital_body_consequence"]["artifact_mutation_mode"], "replace")
                self.assertEqual(payload["digital_body_consequence"]["active_artifact_kind"], "file")
                self.assertEqual(payload["digital_body_consequence"]["active_artifact_label"], "today.md")
                self.assertTrue(bool(payload["digital_body_consequence"]["procedural_growth"]))

    def test_turn_and_event_responses_surface_workspace_path_inspected_consequence(self):
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
                        "completed_packet_count": 1,
                        "artifact_continuity": "attached",
                        "active_artifact_kind": "file",
                        "active_artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                        "active_artifact_label": "today.md",
                        "workspace_root": "E:/runtime/workspaces/lab-notes",
                    },
                },
                "action_packets": [
                    {
                        "proposal_id": "ap-inspect-file-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:inspect_path",
                        "status": "completed",
                        "risk": "read",
                        "requires_approval": False,
                        "tool_name": "inspect_workspace_path",
                        "result_summary": "已查看文件 today.md，当前内容已经重新接回工作面。",
                        "writeback_ready": True,
                        "artifact_context": {
                            "carrier": "filesystem",
                            "artifact_kind": "file",
                            "artifact_ref": "E:/runtime/workspaces/lab-notes/notes/today.md",
                            "artifact_label": "today.md",
                            "workspace_root": "E:/runtime/workspaces/lab-notes",
                            "reacquisition_mode": "reopen_file",
                            "exists": True,
                        },
                    }
                ],
            }

            event_response = api.build_event_round_response(state_values=state_values, final_text="我先把这个文件重新看了一遍。")
            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")

            for payload in (event_response.payload, turn_response.payload):
                self.assertEqual(payload["digital_body"]["resource_state"]["active_artifact_kind"], "file")
                self.assertEqual(payload["digital_body"]["resource_state"]["active_artifact_label"], "today.md")
                self.assertEqual(payload["digital_body_consequence"]["kind"], "workspace_path_inspected")
                self.assertEqual(payload["digital_body_consequence"]["primary_tool_name"], "inspect_workspace_path")
                self.assertEqual(payload["digital_body_consequence"]["active_artifact_kind"], "file")
                self.assertEqual(payload["digital_body_consequence"]["active_artifact_label"], "today.md")
                self.assertEqual(payload["digital_body_consequence"]["workspace_root"], "E:/runtime/workspaces/lab-notes")
                self.assertFalse(bool(payload["digital_body_consequence"]["procedural_growth"]))
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_consequence_kind"],
                    "workspace_path_inspected",
                )
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_consequence_summary"],
                    payload["digital_body_consequence"]["summary"],
                )

    def test_turn_and_event_responses_surface_artifact_reacquired_consequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "digital_body_state": {
                    "active_surface": "tooling",
                    "perception_channels": ["dialogue", "browser"],
                    "action_channels": ["language", "structured_action", "tooling"],
                    "world_surfaces": ["browser", "source_ref"],
                    "access_state": {
                        "mode": "native_only",
                        "network_access": "enabled",
                    },
                    "resource_state": {
                        "completed_packet_count": 1,
                        "artifact_continuity": "attached",
                        "active_artifact_kind": "search_result",
                        "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "active_artifact_label": "Persistence",
                        "artifact_carrier": "source_ref",
                        "artifact_source_ref_ids": [17],
                        "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "artifact_source_query": "langgraph persistence checkpointer thread",
                        "artifact_source_title": "Persistence",
                        "artifact_source_tool_name": "search_web",
                    },
                },
                "action_packets": [
                    {
                        "proposal_id": "ap-source-reattach-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:rerun_search",
                        "status": "completed",
                        "risk": "read",
                        "requires_approval": False,
                        "tool_name": "reacquire_artifact",
                        "result_summary": "已重新接回检索结果 Persistence。",
                        "writeback_ready": True,
                        "artifact_context": {
                            "carrier": "source_ref",
                            "artifact_kind": "search_result",
                            "artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                            "artifact_label": "Persistence",
                            "reacquisition_mode": "rerun_search",
                            "source_ref_ids": [17],
                            "source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                            "source_query": "langgraph persistence checkpointer thread",
                            "source_title": "Persistence",
                            "source_tool_name": "search_web",
                        },
                    }
                ],
            }

            event_response = api.build_event_round_response(state_values=state_values, final_text="我把那条检索结果重新接回来看了一遍。")
            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")

            for payload in (event_response.payload, turn_response.payload):
                self.assertEqual(payload["digital_body"]["resource_state"]["active_artifact_kind"], "search_result")
                self.assertEqual(payload["digital_body"]["resource_state"]["active_artifact_label"], "Persistence")
                self.assertEqual(payload["digital_body_consequence"]["kind"], "artifact_reacquired")
                self.assertEqual(payload["digital_body_consequence"]["primary_tool_name"], "reacquire_artifact")
                self.assertEqual(payload["digital_body_consequence"]["artifact_carrier"], "source_ref")
                self.assertEqual(payload["digital_body_consequence"]["artifact_source_ref_ids"], [17])
                self.assertEqual(payload["digital_body_consequence"]["artifact_source_tool_name"], "search_web")
                self.assertFalse(bool(payload["digital_body_consequence"]["procedural_growth"]))
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_consequence_kind"],
                    "artifact_reacquired",
                )
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_consequence_summary"],
                    payload["digital_body_consequence"]["summary"],
                )

    def test_turn_and_event_responses_surface_source_material_inspected_consequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "digital_body_state": {
                    "active_surface": "tooling",
                    "perception_channels": ["dialogue", "browser"],
                    "action_channels": ["language", "structured_action", "tooling"],
                    "world_surfaces": ["browser", "source_ref"],
                    "access_state": {
                        "mode": "native_only",
                        "network_access": "enabled",
                    },
                    "resource_state": {
                        "completed_packet_count": 1,
                        "artifact_continuity": "attached",
                        "active_artifact_kind": "search_result",
                        "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "active_artifact_label": "Persistence",
                        "artifact_carrier": "source_ref",
                        "artifact_source_ref_ids": [17],
                        "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "artifact_source_query": "langgraph persistence checkpointer thread",
                        "artifact_source_title": "Persistence",
                        "artifact_source_tool_name": "search_web",
                    },
                },
                "action_packets": [
                    {
                        "proposal_id": "ap-inspect-source-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:inspect_source_ref",
                        "status": "completed",
                        "risk": "read",
                        "requires_approval": False,
                        "tool_name": "inspect_source_ref",
                        "result_summary": "已查看外部材料 Persistence，当前内容已经接回视野。",
                        "writeback_ready": True,
                        "artifact_context": {
                            "carrier": "source_ref",
                            "artifact_kind": "search_result",
                            "artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                            "artifact_label": "Persistence",
                            "reacquisition_mode": "inspect_source_ref",
                            "source_ref_ids": [17],
                            "source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                            "source_query": "langgraph persistence checkpointer thread",
                            "source_title": "Persistence",
                            "source_tool_name": "search_web",
                        },
                    }
                ],
            }

            event_response = api.build_event_round_response(state_values=state_values, final_text="我把那条资料重新翻出来看了一遍。")
            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")

            for payload in (event_response.payload, turn_response.payload):
                self.assertEqual(payload["digital_body"]["resource_state"]["active_artifact_kind"], "search_result")
                self.assertEqual(payload["digital_body"]["resource_state"]["active_artifact_label"], "Persistence")
                self.assertEqual(payload["digital_body_consequence"]["kind"], "source_material_inspected")
                self.assertEqual(payload["digital_body_consequence"]["primary_tool_name"], "inspect_source_ref")
                self.assertEqual(payload["digital_body_consequence"]["artifact_carrier"], "source_ref")
                self.assertEqual(payload["digital_body_consequence"]["artifact_source_ref_ids"], [17])
                self.assertEqual(payload["digital_body_consequence"]["artifact_source_tool_name"], "search_web")
                self.assertFalse(bool(payload["digital_body_consequence"]["procedural_growth"]))
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_consequence_kind"],
                    "source_material_inspected",
                )
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_consequence_summary"],
                    payload["digital_body_consequence"]["summary"],
                )

    def test_turn_and_event_responses_surface_source_material_compared_consequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "digital_body_state": {
                    "active_surface": "tooling",
                    "perception_channels": ["dialogue", "browser"],
                    "action_channels": ["language", "structured_action", "tooling"],
                    "world_surfaces": ["browser", "source_ref"],
                    "access_state": {
                        "mode": "native_only",
                        "network_access": "enabled",
                    },
                    "resource_state": {
                        "completed_packet_count": 1,
                        "artifact_continuity": "attached",
                        "active_artifact_kind": "search_result",
                        "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "active_artifact_label": "Persistence v2",
                        "artifact_carrier": "source_ref",
                        "artifact_source_ref_ids": [21, 17],
                        "preferred_source_ref_id": 21,
                        "preferred_anchor_reason": "primary_more_current",
                        "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "artifact_source_query": "langgraph persistence checkpointer thread recovery",
                        "artifact_source_title": "Persistence v2",
                        "artifact_source_tool_name": "search_web",
                    },
                },
                "action_packets": [
                    {
                        "proposal_id": "ap-compare-source-1",
                        "origin": "counterpart_request",
                        "intent": "artifact:compare_source_refs",
                        "status": "completed",
                        "risk": "read",
                        "requires_approval": False,
                        "tool_name": "compare_source_refs",
                        "result_summary": "已把 Persistence v2 和 Persistence 对照过一遍，两条材料是紧邻的延续，当前判断会优先沿着这条相连线索继续。",
                        "writeback_ready": True,
                        "artifact_context": {
                            "carrier": "source_ref",
                            "artifact_kind": "search_result",
                            "artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "artifact_label": "Persistence v2",
                        "reacquisition_mode": "compare_source_refs",
                        "source_ref_ids": [21, 17],
                        "preferred_source_ref_id": 21,
                        "preferred_anchor_reason": "primary_more_current",
                        "source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "source_query": "langgraph persistence checkpointer thread recovery",
                        "source_title": "Persistence v2",
                            "source_tool_name": "search_web",
                        },
                    }
                ],
            }

            event_response = api.build_event_round_response(state_values=state_values, final_text="我把这两条资料对照了一遍。")
            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")

            for payload in (event_response.payload, turn_response.payload):
                self.assertEqual(payload["digital_body"]["resource_state"]["active_artifact_kind"], "search_result")
                self.assertEqual(payload["digital_body"]["resource_state"]["active_artifact_label"], "Persistence v2")
                self.assertEqual(payload["digital_body"]["resource_state"]["preferred_source_ref_id"], 21)
                self.assertEqual(payload["digital_body"]["resource_state"]["preferred_anchor_reason"], "primary_more_current")
                self.assertEqual(payload["digital_body_consequence"]["kind"], "source_material_compared")
                self.assertEqual(payload["digital_body_consequence"]["primary_tool_name"], "compare_source_refs")
                self.assertEqual(payload["digital_body_consequence"]["artifact_carrier"], "source_ref")
                self.assertEqual(payload["digital_body_consequence"]["artifact_source_ref_ids"], [21, 17])
                self.assertEqual(payload["digital_body_consequence"]["preferred_source_ref_id"], 21)
                self.assertEqual(payload["digital_body_consequence"]["preferred_anchor_reason"], "primary_more_current")
                self.assertEqual(payload["digital_body_consequence"]["artifact_source_tool_name"], "search_web")
                self.assertFalse(bool(payload["digital_body_consequence"]["procedural_growth"]))
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_consequence_kind"],
                    "source_material_compared",
                )
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_consequence_summary"],
                    payload["digital_body_consequence"]["summary"],
                )
                self.assertEqual(payload["turn_summary"]["current_turn"]["digital_body_preferred_source_ref_id"], 21)
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_preferred_anchor_reason"],
                    "primary_more_current",
                )
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_consequence_preferred_source_ref_id"],
                    21,
                )
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_consequence_preferred_anchor_reason"],
                    "primary_more_current",
                )
                self.assertEqual(
                    (payload["turn_summary"].get("event_residue") or {}).get("digital_body_consequence", {}).get("preferred_source_ref_id"),
                    21,
                )
                self.assertEqual(
                    (payload["turn_summary"].get("event_residue") or {}).get("digital_body_consequence", {}).get("preferred_anchor_reason"),
                    "primary_more_current",
                )

    def test_turn_and_event_responses_surface_access_state_refreshed_consequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "digital_body_state": {
                    "active_surface": "tooling",
                    "perception_channels": ["dialogue", "runtime"],
                    "action_channels": ["language", "structured_action", "tooling"],
                    "world_surfaces": ["network", "filesystem"],
                    "access_state": {
                        "mode": "tool_enabled",
                        "api_key_state": "present",
                        "filesystem_state": "writable",
                        "network_access": "enabled",
                        "session_continuity": "stable",
                        "session_recovery_mode": "refresh_session",
                    },
                    "resource_state": {
                        "completed_packet_count": 1,
                    },
                },
                "action_packets": [
                    {
                        "proposal_id": "ap-refresh-access-1",
                        "origin": "motive_goal",
                        "intent": "access:refresh_state",
                        "status": "completed",
                        "risk": "read",
                        "requires_approval": False,
                        "tool_name": "refresh_access_state",
                        "result_summary": "已重新检查当前入口状态，眼下这条路径是稳定的。",
                        "writeback_ready": True,
                    }
                ],
            }

            event_response = api.build_event_round_response(state_values=state_values, final_text="我把当前入口状态重新核对过了。")
            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")

            for payload in (event_response.payload, turn_response.payload):
                self.assertEqual(payload["digital_body"]["access_state"]["session_continuity"], "stable")
                self.assertEqual(payload["digital_body_consequence"]["kind"], "access_state_refreshed")
                self.assertEqual(payload["digital_body_consequence"]["primary_tool_name"], "refresh_access_state")
                self.assertEqual(payload["digital_body_consequence"]["session_continuity"], "stable")
                self.assertFalse(bool(payload["digital_body_consequence"]["procedural_growth"]))
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["digital_body_consequence_kind"],
                    "access_state_refreshed",
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
                                "preferred_source_ref_id": 17,
                                "preferred_anchor_reason": "primary_more_current",
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
                                "preferred_source_ref_id": 17,
                                "preferred_anchor_reason": "primary_more_current",
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
                        "embodied_context": {
                            "kind": "source_material_compared",
                            "artifact_carrier": "source_ref",
                            "artifact_source_ref_ids": [21, 17],
                            "preferred_source_ref_id": 21,
                            "preferred_anchor_reason": "primary_more_current",
                            "artifact_source_title": "Persistence v2",
                            "artifact_source_tool_name": "search_web",
                        },
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
                        "embodied_context": {
                            "kind": "source_material_compared",
                            "artifact_carrier": "source_ref",
                            "artifact_source_ref_ids": [21, 17],
                            "preferred_source_ref_id": 21,
                            "preferred_anchor_reason": "primary_more_current",
                            "artifact_source_title": "Persistence v2",
                            "artifact_source_tool_name": "search_web",
                        },
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
                self.assertEqual(writeback["revision_traces"][0]["embodied_context"]["preferred_source_ref_id"], 17)
                self.assertEqual(
                    writeback["revision_traces"][0]["embodied_context"]["preferred_anchor_reason"],
                    "primary_more_current",
                )
                self.assertEqual(writeback["revision_traces"][0]["embodied_context"]["artifact_source_title"], "Persistence")
                self.assertEqual(writeback["revision_traces"][0]["embodied_context"]["artifact_source_tool_name"], "search_web")
                self.assertIn("bodyfx=access_request_pending", writeback["revision_traces"][0].get("preview_line") or "")
                self.assertIn("source=Persistence", writeback["revision_traces"][0].get("preview_line") or "")
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["kind"], "environmental_friction")
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["missing_access"], ["browser_session"])
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["artifact_carrier"], "source_ref")
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["artifact_source_ref_ids"], [17])
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["preferred_source_ref_id"], 17)
                self.assertEqual(
                    writeback["revision_traces"][1]["embodied_context"]["preferred_anchor_reason"],
                    "primary_more_current",
                )
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["artifact_source_title"], "Persistence")
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["artifact_source_tool_name"], "search_web")
                self.assertIn("bodyfx=environmental_friction", writeback["revision_traces"][1].get("preview_line") or "")
                self.assertIn("source=Persistence", writeback["revision_traces"][1].get("preview_line") or "")
                self.assertEqual([item["category"] for item in writeback["semantic_self_narratives"]], ["agency_style"])
                self.assertEqual(writeback["semantic_self_narratives"][0]["text"], "她有自己的节奏和靠近方式。")
                self.assertEqual(
                    [item["summary"] for item in writeback["counterpart_assessment_history"]],
                    ["她重新判断这次靠近是认真修复，不是敷衍找补。"],
                )
                self.assertEqual(
                    writeback["counterpart_assessment_history"][0]["embodied_context"]["preferred_source_ref_id"],
                    21,
                )
                self.assertEqual(
                    writeback["counterpart_assessment_history"][0]["embodied_context"]["preferred_anchor_reason"],
                    "primary_more_current",
                )
                self.assertIn(
                    "source=Persistence",
                    writeback["counterpart_assessment_history"][0].get("preview_line") or "",
                )
                self.assertIn(
                    "bodyfx=source_material_compared",
                    writeback["counterpart_assessment_history"][0].get("preview_line") or "",
                )
                self.assertEqual(
                    [item["summary"] for item in writeback["proactive_continuity_history"]],
                    ["她把这轮余温收进后续小幅回头的连续性里。"],
                )
                self.assertEqual(
                    writeback["proactive_continuity_history"][0]["embodied_context"]["preferred_source_ref_id"],
                    21,
                )
                self.assertEqual(
                    writeback["proactive_continuity_history"][0]["embodied_context"]["preferred_anchor_reason"],
                    "primary_more_current",
                )
                self.assertIn(
                    "source=Persistence",
                    writeback["proactive_continuity_history"][0].get("preview_line") or "",
                )
                self.assertIn(
                    "bodyfx=source_material_compared",
                    writeback["proactive_continuity_history"][0].get("preview_line") or "",
                )

    def test_turn_and_event_responses_preserve_access_state_writeback_trace_context(self):
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
                        "after_summary": "她会把工作面真的接回手上，而不是停在空想里。",
                        "source": "auto:passive_evolution_final",
                        "behavior_consequence": {
                            "embodied_context": {
                                "kind": "workspace_access_resolved",
                                "workspace_root": "E:/runtime/workspaces/lab-notes",
                                "artifact_continuity": "attached",
                                "active_artifact_kind": "workspace",
                                "active_artifact_ref": "E:/runtime/workspaces/lab-notes",
                                "active_artifact_label": "lab-notes",
                                "filesystem_state": "writable",
                                "session_continuity": "stable",
                                "session_recovery_mode": "refresh_session",
                                "access_acquire_proposals": [
                                    {
                                        "target": "filesystem",
                                        "mode": "operator_create_workspace",
                                        "summary": "先新建一个可写工作区。",
                                        "grants": ["filesystem", "workspace_write"],
                                        "requires_operator": True,
                                    }
                                ],
                                "selected_access_proposal": {
                                    "target": "filesystem",
                                    "mode": "operator_create_workspace",
                                    "summary": "先新建一个可写工作区。",
                                    "grants": ["filesystem", "workspace_write"],
                                    "requires_operator": True,
                                },
                                "primary_status": "completed",
                            }
                        },
                        "created_at": 631,
                    },
                    {
                        "namespace": "semantic_self_narratives",
                        "target_id": "14",
                        "after_summary": "她也会重新核对入口状态，让路径保持真实可用。",
                        "source": "auto:passive_evolution_final",
                        "interaction_carryover": {
                            "embodied_context": {
                                "kind": "access_state_refreshed",
                                "api_key_state": "present",
                                "filesystem_state": "writable",
                                "network_access": "enabled",
                                "session_continuity": "stable",
                                "session_recovery_mode": "refresh_session",
                                "access_acquire_proposals": [
                                    {
                                        "target": "filesystem",
                                        "mode": "operator_create_workspace",
                                        "summary": "需要时可以补一个新工作区。",
                                        "grants": ["filesystem", "workspace_write"],
                                        "requires_operator": True,
                                    }
                                ],
                                "selected_access_proposal": {
                                    "target": "filesystem",
                                    "mode": "operator_create_workspace",
                                    "summary": "需要时可以补一个新工作区。",
                                    "grants": ["filesystem", "workspace_write"],
                                    "requires_operator": True,
                                },
                                "primary_status": "completed",
                            }
                        },
                        "updated_at": 632,
                    },
                ],
                list_semantic_self_narratives=lambda limit=20: [],
                list_counterpart_assessment_history=lambda limit=12: [],
                list_proactive_continuity_history=lambda limit=12: [],
            )
            state_values = {
                "session_context": {
                    "thread_id": "thread-a",
                    "turn_id": "thread-a:630",
                    "turn_started_at": 630,
                },
                "current_event": {
                    "kind": "user_utterance",
                    "created_at": 630,
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
                self.assertEqual(len(writeback["revision_traces"]), 2)
                self.assertEqual(writeback["revision_traces"][0]["embodied_context"]["kind"], "workspace_access_resolved")
                self.assertEqual(writeback["revision_traces"][0]["embodied_context"]["workspace_root"], "E:/runtime/workspaces/lab-notes")
                self.assertEqual(writeback["revision_traces"][0]["embodied_context"]["filesystem_state"], "writable")
                self.assertEqual(writeback["revision_traces"][0]["embodied_context"]["session_continuity"], "stable")
                self.assertEqual(
                    writeback["revision_traces"][0]["embodied_context"]["selected_access_proposal"]["mode"],
                    "operator_create_workspace",
                )
                self.assertEqual(
                    writeback["revision_traces"][0]["embodied_context"]["access_acquire_proposals"][0]["target"],
                    "filesystem",
                )
                self.assertIn("bodyfx=workspace_access_resolved", writeback["revision_traces"][0].get("preview_line") or "")
                self.assertIn("proposal=operator_create_workspace@filesystem", writeback["revision_traces"][0].get("preview_line") or "")
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["kind"], "access_state_refreshed")
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["api_key_state"], "present")
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["filesystem_state"], "writable")
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["network_access"], "enabled")
                self.assertEqual(writeback["revision_traces"][1]["embodied_context"]["session_recovery_mode"], "refresh_session")
                self.assertEqual(
                    writeback["revision_traces"][1]["embodied_context"]["selected_access_proposal"]["mode"],
                    "operator_create_workspace",
                )
                self.assertIn("bodyfx=access_state_refreshed", writeback["revision_traces"][1].get("preview_line") or "")
                self.assertIn("proposal=operator_create_workspace@filesystem", writeback["revision_traces"][1].get("preview_line") or "")

    def test_turn_and_event_responses_preserve_access_state_history_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, session = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            session.memory_store = SimpleNamespace(
                list_revision_traces=lambda limit=60: [],
                list_semantic_self_narratives=lambda limit=20: [],
                list_counterpart_assessment_history=lambda limit=12: [
                    {
                        "summary": "她确认这次工作面已经真的接回来了。",
                        "stance": "open",
                        "scene": "co_work",
                        "embodied_context": {
                            "kind": "workspace_access_resolved",
                            "workspace_root": "E:/runtime/workspaces/lab-notes",
                            "artifact_continuity": "attached",
                            "active_artifact_kind": "workspace",
                            "active_artifact_ref": "E:/runtime/workspaces/lab-notes",
                            "active_artifact_label": "lab-notes",
                            "filesystem_state": "writable",
                            "session_continuity": "stable",
                            "session_recovery_mode": "refresh_session",
                            "access_acquire_proposals": [
                                {
                                    "target": "filesystem",
                                    "mode": "operator_create_workspace",
                                    "summary": "先新建一个可写工作区。",
                                    "grants": ["filesystem", "workspace_write"],
                                    "requires_operator": True,
                                }
                            ],
                            "selected_access_proposal": {
                                "target": "filesystem",
                                "mode": "operator_create_workspace",
                                "summary": "先新建一个可写工作区。",
                                "grants": ["filesystem", "workspace_write"],
                                "requires_operator": True,
                            },
                        },
                        "created_at": 731,
                    }
                ],
                list_proactive_continuity_history=lambda limit=12: [
                    {
                        "summary": "她把这条稳定可用的入口继续带进后续连续性里。",
                        "kind": "promoted",
                        "trace_family": "access_state_refresh_followthrough",
                        "embodied_context": {
                            "kind": "access_state_refreshed",
                            "api_key_state": "present",
                            "filesystem_state": "writable",
                            "network_access": "enabled",
                            "session_continuity": "stable",
                            "session_recovery_mode": "refresh_session",
                            "access_acquire_proposals": [
                                {
                                    "target": "filesystem",
                                    "mode": "operator_create_workspace",
                                    "summary": "需要时可以补一个新工作区。",
                                    "grants": ["filesystem", "workspace_write"],
                                    "requires_operator": True,
                                }
                            ],
                            "selected_access_proposal": {
                                "target": "filesystem",
                                "mode": "operator_create_workspace",
                                "summary": "需要时可以补一个新工作区。",
                                "grants": ["filesystem", "workspace_write"],
                                "requires_operator": True,
                            },
                        },
                        "created_at": 732,
                    }
                ],
            )
            state_values = {
                "session_context": {
                    "thread_id": "thread-a",
                    "turn_id": "thread-a:730",
                    "turn_started_at": 730,
                },
                "current_event": {
                    "kind": "user_utterance",
                    "created_at": 730,
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
                self.assertEqual(
                    writeback["counterpart_assessment_history"][0]["embodied_context"]["kind"],
                    "workspace_access_resolved",
                )
                self.assertEqual(
                    writeback["counterpart_assessment_history"][0]["embodied_context"]["filesystem_state"],
                    "writable",
                )
                self.assertEqual(
                    writeback["counterpart_assessment_history"][0]["embodied_context"]["session_recovery_mode"],
                    "refresh_session",
                )
                self.assertEqual(
                    writeback["counterpart_assessment_history"][0]["embodied_context"]["selected_access_proposal"]["mode"],
                    "operator_create_workspace",
                )
                self.assertIn(
                    "bodyfx=workspace_access_resolved",
                    writeback["counterpart_assessment_history"][0].get("preview_line") or "",
                )
                self.assertIn(
                    "root=E:/runtime/workspaces/lab-notes",
                    writeback["counterpart_assessment_history"][0].get("preview_line") or "",
                )
                self.assertEqual(
                    writeback["proactive_continuity_history"][0]["embodied_context"]["kind"],
                    "access_state_refreshed",
                )
                self.assertEqual(
                    writeback["proactive_continuity_history"][0]["embodied_context"]["api_key_state"],
                    "present",
                )
                self.assertEqual(
                    writeback["proactive_continuity_history"][0]["embodied_context"]["network_access"],
                    "enabled",
                )
                self.assertEqual(
                    writeback["proactive_continuity_history"][0]["embodied_context"]["selected_access_proposal"]["mode"],
                    "operator_create_workspace",
                )
                self.assertIn(
                    "bodyfx=access_state_refreshed",
                    writeback["proactive_continuity_history"][0].get("preview_line") or "",
                )
                self.assertIn(
                    "proposal=operator_create_workspace@filesystem",
                    writeback["proactive_continuity_history"][0].get("preview_line") or "",
                )

    def test_turn_and_event_responses_normalize_content_only_history_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, session = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            session.memory_store = SimpleNamespace(
                list_revision_traces=lambda limit=60: [],
                list_semantic_self_narratives=lambda limit=20: [],
                list_counterpart_assessment_history=lambda limit=12: [
                    {
                        "id": 41,
                        "content": {
                            "summary": "她确认这次工作面已经真的接回来了。",
                            "stance": "open",
                            "scene": "co_work",
                            "respect_level": "0.76",
                            "assessment_profile": {
                                "dominant_scene_signal": " Care ",
                                "openness_drive": "0.74",
                                "scene_strengths": {"care": "0.81"},
                            },
                            "embodied_context": {
                                "kind": "workspace_access_resolved",
                                "workspace_root": "E:/runtime/workspaces/lab-notes",
                                "filesystem_state": "writable",
                                "session_recovery_mode": "refresh_session",
                            },
                        },
                        "created_at": 831,
                    }
                ],
                list_proactive_continuity_history=lambda limit=12: [
                    {
                        "id": 42,
                        "content": {
                            "summary": "她把这条稳定入口继续带进后续连续性里。",
                            "kind": "promoted",
                            "trace_family": "access_state_refresh_followthrough",
                            "carryover_mode": "continue_work_surface",
                            "carryover_strength": "0.53",
                            "embodied_context": {
                                "kind": "access_state_refreshed",
                                "api_key_state": "present",
                                "filesystem_state": "writable",
                                "network_access": "enabled",
                            },
                        },
                        "created_at": 832,
                    }
                ],
            )
            state_values = {
                "session_context": {
                    "thread_id": "thread-a",
                    "turn_id": "thread-a:830",
                    "turn_started_at": 830,
                },
                "current_event": {
                    "kind": "user_utterance",
                    "created_at": 830,
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
                self.assertEqual(writeback["counterpart_assessment_history"][0]["scene"], "co_work")
                self.assertEqual(
                    writeback["counterpart_assessment_history"][0]["embodied_context"]["kind"],
                    "workspace_access_resolved",
                )
                self.assertEqual(
                    writeback["counterpart_assessment_history"][0]["embodied_context"]["workspace_root"],
                    "E:/runtime/workspaces/lab-notes",
                )
                self.assertEqual(writeback["counterpart_assessment_history"][0]["respect_level"], 0.76)
                self.assertEqual(
                    writeback["counterpart_assessment_history"][0]["assessment_profile"]["dominant_scene_signal"],
                    "care",
                )
                self.assertEqual(
                    writeback["proactive_continuity_history"][0]["trace_family"],
                    "access_state_refresh_followthrough",
                )
                self.assertEqual(writeback["proactive_continuity_history"][0]["carryover_strength"], 0.53)
                self.assertEqual(
                    writeback["proactive_continuity_history"][0]["embodied_context"]["kind"],
                    "access_state_refreshed",
                )
                self.assertEqual(
                    writeback["proactive_continuity_history"][0]["embodied_context"]["api_key_state"],
                    "present",
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

    def test_turn_response_surfaces_skills_envelope_and_live_pending_skill_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "session_skill_state": {
                    "catalog_version": "skills-v1",
                    "catalog_entries": [
                        {
                            "skill_id": "pytest-helper",
                            "name": "pytest-helper",
                            "description": "Helps with pytest workflows",
                            "version": "1.0.0",
                            "status": "installed",
                        }
                    ],
                    "matched_skill_entries": [
                        {
                            "skill_id": "pytest-helper",
                            "name": "pytest-helper",
                            "description": "Helps with pytest workflows",
                            "version": "1.0.0",
                            "status": "installed",
                        }
                    ],
                    "active_skill_entries": [],
                    "manual_overrides": {"enabled": [], "disabled": [], "pinned": []},
                },
                "pending_action_proposal": {
                    "proposal_id": "ap-skill-install-1",
                    "tool_name": "install_skill",
                    "tool_args": {
                        "skill_id": "pytest-helper",
                        "resolved_version": "1.1.0",
                        "source": "official_registry",
                        "hash": "abc123",
                        "requested_permissions": ["filesystem_read"],
                        "sandbox_profiles": ["workspace_write"],
                        "verification_summary": "registry verified",
                    },
                },
            }

            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")
            skills = turn_response.payload["skills"]

            self.assertEqual(skills["installed"][0]["skill_id"], "pytest-helper")
            self.assertEqual(skills["matched"][0]["skill_id"], "pytest-helper")
            self.assertEqual(skills["active"], [])
            self.assertEqual(skills["pending_approval"]["proposal_id"], "ap-skill-install-1")
            self.assertEqual(skills["pending_approval"]["resolved_version"], "1.1.0")
            self.assertEqual(skills["pending_approval"]["sandbox_profiles"], ["workspace_write"])

    def test_turn_response_surfaces_completed_skill_usage_as_digital_body_consequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "session_skill_state": {
                    "catalog_version": "skills-v1",
                    "catalog_entries": [
                        {
                            "skill_id": "source-ref-anchor-review",
                            "name": "source-ref-anchor-review",
                            "description": "Read continuity-focused source materials",
                            "version": "1.0.0",
                            "status": "authored_local",
                        }
                    ],
                    "active_skill_ids": ["source-ref-anchor-review"],
                    "active_skill_entries": [
                        {
                            "skill_id": "source-ref-anchor-review",
                            "name": "source-ref-anchor-review",
                            "description": "Read continuity-focused source materials",
                            "version": "1.0.0",
                            "status": "authored_local",
                            "allowed_tools": ["search_web", "inspect_source_ref"],
                            "skill_excerpt": "Inspect the preferred saved source first.",
                        }
                    ],
                },
                "digital_body_state": {
                    "active_surface": "tooling",
                    "perception_channels": ["dialogue", "source_ref"],
                    "action_channels": ["language", "structured_action", "tooling"],
                    "world_surfaces": ["source_ref", "saved_material"],
                    "access_state": {"mode": "tool_enabled", "network_access": "enabled"},
                    "resource_state": {
                        "artifact_continuity": "attached",
                        "active_artifact_kind": "search_result",
                        "active_artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "active_artifact_label": "LangGraph Persistence",
                        "artifact_carrier": "source_ref",
                        "artifact_source_ref_ids": [21, 17],
                        "preferred_source_ref_id": 21,
                        "preferred_anchor_reason": "primary_more_current",
                        "artifact_source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                        "artifact_source_query": "langgraph persistence checkpointer thread",
                        "artifact_source_title": "LangGraph Persistence",
                        "artifact_source_tool_name": "search_web",
                    },
                },
                "action_packets": [
                    {
                        "proposal_id": "ap-skill-usage-1",
                        "origin": "motive_goal",
                        "intent": "tool:search_web",
                        "status": "completed",
                        "risk": "read",
                        "requires_approval": False,
                        "tool_name": "search_web",
                        "tool_args": {"query": "langgraph persistence checkpointer"},
                        "result_summary": "searched continuity materials",
                        "writeback_ready": True,
                        "artifact_context": {
                            "carrier": "source_ref",
                            "artifact_kind": "search_result",
                            "artifact_ref": "https://docs.langchain.com/oss/python/langgraph/persistence",
                            "artifact_label": "LangGraph Persistence",
                            "source_ref_ids": [21, 17],
                            "preferred_source_ref_id": 21,
                            "preferred_anchor_reason": "primary_more_current",
                            "source_url": "https://docs.langchain.com/oss/python/langgraph/persistence",
                            "source_query": "langgraph persistence checkpointer thread",
                            "source_title": "LangGraph Persistence",
                            "source_tool_name": "search_web",
                        },
                    }
                ],
            }

            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")
            consequence = turn_response.payload["digital_body_consequence"]
            self.assertEqual(consequence["kind"], "skill_usage_completed")
            self.assertEqual(consequence["skill_effects"][0]["skill_id"], "source-ref-anchor-review")
            self.assertEqual(turn_response.payload["skills"]["active"][0]["skill_id"], "source-ref-anchor-review")

    def test_turn_response_surfaces_browser_matrix_consequence_families(self):
        def _state(*, tool_name, proposal_id, status, action_kind, result_summary="", manual=False, block_reason="", download_path="", upload_source=""):
            return {
                "digital_body_state": {
                    "active_surface": "tooling",
                    "perception_channels": ["dialogue", "browser"],
                    "action_channels": ["language", "structured_action", "tooling"],
                    "world_surfaces": ["browser", "filesystem"],
                    "access_state": {
                        "mode": "tool_enabled",
                        "browser_session": "present",
                        "filesystem_state": "writable",
                        "browser_runtime_state": {
                            "availability": "available",
                            "profile_root": "E:/runtime/browser/profiles/thread-browser",
                            "context_status": "manual_takeover" if manual else "active",
                            "active_page_id": "page-1",
                            "active_tab_count": 1,
                            "downloads_dir": "E:/runtime/browser/downloads/thread-browser",
                            "last_action_status": "manual_takeover_required" if manual else status,
                            "last_run_id": proposal_id,
                            "manual_takeover_required": manual,
                            "runner_kind": "playwright_persistent_context",
                            "isolation_level": "persistent_profile_runtime",
                        },
                    },
                    "resource_state": {
                        "completed_packet_count": 1 if status == "completed" else 0,
                        "blocked_packet_count": 1 if status == "blocked" else 0,
                        "artifact_continuity": "attached",
                        "active_artifact_kind": "file" if download_path else "page",
                        "active_artifact_ref": download_path or "page:page-1",
                        "active_artifact_label": "payload.txt" if download_path else "Docs",
                        "artifact_carrier": "filesystem" if download_path else "browser_page",
                        "artifact_source_url": "https://example.com/docs",
                        "artifact_source_title": "Docs",
                        "artifact_source_tool_name": tool_name,
                        "workspace_root": "E:/runtime/workspaces/browser-smoke",
                        "browser_profile_id": "thread-browser",
                        "browser_tab_id": "tab-1",
                    },
                },
                "action_packets": [
                    {
                        "proposal_id": proposal_id,
                        "origin": "motive_goal",
                        "intent": f"browser:{tool_name.removeprefix('browser_')}",
                        "status": status,
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "tool_name": tool_name,
                        "result_summary": result_summary,
                        "block_reason": block_reason,
                        "writeback_ready": status == "completed",
                        "browser_execution_spec": {
                            "operation": action_kind,
                            "profile_id": "thread-browser",
                            "page_ref": "page:page-1",
                            "target_ref": "e2",
                            "upload_source": upload_source,
                            "download_target": download_path,
                            "allowed_roots": ["E:/runtime/workspaces/browser-smoke"],
                            "browser_downloads_root": "E:/runtime/browser/downloads/thread-browser",
                            "timeout_s": 20,
                        },
                        "browser_execution_preview": {
                            "runner_kind": "playwright_persistent_context",
                            "isolation_level": "persistent_profile_runtime",
                            "operation": action_kind,
                            "profile_id": "thread-browser",
                            "page_ref": "page:page-1",
                            "page_url": "https://example.com/docs",
                            "page_title": "Docs",
                            "target_ref": "e2",
                            "target_label": "Approve action",
                            "download_target": download_path,
                            "upload_source": upload_source,
                            "allowed_roots": ["E:/runtime/workspaces/browser-smoke"],
                            "downloads_root": "E:/runtime/browser/downloads/thread-browser",
                            "timeout_s": 20,
                            "requires_manual_takeover": manual,
                        },
                        "browser_execution_result": {
                            "run_id": proposal_id,
                            "status": status,
                            "profile_id": "thread-browser",
                            "page_id": "page-1",
                            "tab_id": "tab-1",
                            "url": "https://example.com/docs",
                            "title": "Docs",
                            "action_kind": action_kind,
                            "target_ref": "e2",
                            "duration_ms": 45,
                            "active_tab_count": 1,
                            "last_action_status": "manual_takeover_required" if manual else status,
                            "download_path": download_path,
                            "upload_source": upload_source,
                            "error_summary": block_reason,
                            "manual_takeover_required": manual,
                        },
                    }
                ],
            }

        cases = [
            ("browser_click", "ap-browser-click-api", "completed", "click", "browser_interaction_completed", "clicked Docs button", False, "", "", ""),
            ("browser_download_click", "ap-browser-download-api", "completed", "download_click", "browser_download_completed", "downloaded payload", False, "", "E:/runtime/workspaces/browser-smoke/downloads/payload.txt", ""),
            ("browser_upload_file", "ap-browser-upload-api", "completed", "upload_file", "browser_upload_completed", "uploaded payload", False, "", "", "E:/runtime/workspaces/browser-smoke/payload.txt"),
            ("browser_fill", "ap-browser-takeover-api", "blocked", "fill", "browser_takeover_requested", "", True, "sensitive credential entry requires manual browser takeover", "", ""),
            ("browser_click", "ap-browser-blocked-api", "blocked", "click", "browser_action_blocked", "", False, "browser action timed out after 20s", "", ""),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)

            for tool_name, proposal_id, status, action_kind, expected_kind, summary, manual, block_reason, download_path, upload_source in cases:
                with self.subTest(kind=expected_kind):
                    payload = api.build_turn_response(
                        state_values=_state(
                            tool_name=tool_name,
                            proposal_id=proposal_id,
                            status=status,
                            action_kind=action_kind,
                            result_summary=summary,
                            manual=manual,
                            block_reason=block_reason,
                            download_path=download_path,
                            upload_source=upload_source,
                        ),
                        streamed_text="ignored",
                    ).payload

                    packet = payload["autonomy"]["action_packets"][0]
                    consequence = payload["digital_body_consequence"]
                    self.assertEqual(packet["proposal_id"], proposal_id)
                    self.assertEqual(packet["status"], status)
                    self.assertEqual(packet["browser_execution_result"]["run_id"], proposal_id)
                    self.assertEqual(consequence["kind"], expected_kind)
                    self.assertEqual(consequence["browser_run_id"], proposal_id)
                    self.assertEqual(consequence["browser_profile_id"], "thread-browser")
                    self.assertEqual(consequence["browser_page_id"], "page-1")
                    self.assertEqual(consequence["browser_tab_id"], "tab-1")
                    self.assertEqual(consequence["browser_last_action_kind"], action_kind)
                    self.assertEqual(consequence["browser_last_exit_status"], status)
                    self.assertEqual(bool(consequence["requested_help"]), manual)
                    if expected_kind in {"browser_takeover_requested", "browser_action_blocked"}:
                        self.assertTrue(bool(consequence["environmental_friction"]))
                    if expected_kind == "browser_takeover_requested":
                        self.assertTrue(consequence["browser_runtime_state"]["manual_takeover_required"])
                    if expected_kind == "browser_download_completed":
                        self.assertEqual(consequence["active_artifact_ref"], download_path)
                    if expected_kind == "browser_upload_completed":
                        self.assertEqual(packet["browser_execution_result"]["upload_source"], upload_source)

    def test_turn_response_surfaces_sandbox_phase2_docker_fields(self):
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
                    "world_surfaces": ["filesystem", "sandbox"],
                    "access_state": {
                        "mode": "tool_enabled",
                        "filesystem_state": "writable",
                        "sandbox_mode": "restricted",
                        "sandbox_state": {
                            "availability": "restricted",
                            "allowed_roots": ["E:/repo/amadeus-thread0"],
                            "execution_policy": "approval_required",
                            "last_status": "completed",
                            "runner_kind": "docker_isolated_runner",
                            "isolation_level": "docker_local_isolated",
                            "image_ref": "amadeus-thread0/sandbox-phase2:py312",
                            "network_policy": "none",
                            "workspace_root_kind": "attached_repo_root",
                            "last_command_profile": "pytest",
                            "last_exit_code": 0,
                            "last_run_id": "ap-sandbox-phase2-api",
                            "arbitrary_execution": False,
                        },
                    },
                    "resource_state": {
                        "artifact_continuity": "attached",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": "E:/repo/amadeus-thread0",
                        "active_artifact_label": "amadeus-thread0",
                        "artifact_carrier": "filesystem",
                        "workspace_root": "E:/repo/amadeus-thread0",
                    },
                },
                "action_packets": [
                    {
                        "proposal_id": "ap-sandbox-phase2-api",
                        "intent": "sandbox:execute_workspace_command",
                        "status": "completed",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "tool_name": "execute_workspace_command",
                        "execution_spec": {
                            "executor": "pytest",
                            "profile": "pytest",
                            "runner_kind": "docker_isolated_runner",
                            "isolation_level": "docker_local_isolated",
                            "image_ref": "amadeus-thread0/sandbox-phase2:py312",
                            "network_policy": "none",
                            "workspace_root_kind": "attached_repo_root",
                            "argv": ["pytest", "-q", "tests/test_sandbox_phase2_repo_fixture.py"],
                            "cwd": "E:/repo/amadeus-thread0",
                            "allowed_roots": ["E:/repo/amadeus-thread0"],
                            "timeout_s": 60,
                            "writes_expected": False,
                            "expected_artifacts": [],
                        },
                        "execution_preview": {
                            "runner_kind": "docker_isolated_runner",
                            "isolation_level": "docker_local_isolated",
                            "image_ref": "amadeus-thread0/sandbox-phase2:py312",
                            "network_policy": "none",
                            "workspace_root_kind": "attached_repo_root",
                            "argv": ["pytest", "-q", "tests/test_sandbox_phase2_repo_fixture.py"],
                            "cwd": "E:/repo/amadeus-thread0",
                            "allowed_roots": ["E:/repo/amadeus-thread0"],
                            "timeout_s": 60,
                            "writes_expected": False,
                            "expected_artifacts": [],
                        },
                        "execution_result": {
                            "run_id": "ap-sandbox-phase2-api",
                            "status": "completed",
                            "exit_code": 0,
                            "duration_ms": 88,
                            "stdout_log_ref": "E:/repo/amadeus-thread0/.amadeus/sandbox-runs/ap-sandbox-phase2-api/stdout.txt",
                            "stderr_log_ref": "E:/repo/amadeus-thread0/.amadeus/sandbox-runs/ap-sandbox-phase2-api/stderr.txt",
                            "produced_artifacts": [],
                            "error_summary": "",
                        },
                    }
                ],
                "digital_body_consequence": {
                    "kind": "sandbox_execution_completed",
                    "summary": "Docker 隔离执行已经完成。",
                    "sandbox_runner_kind": "docker_isolated_runner",
                    "sandbox_network_policy": "none",
                    "workspace_root_kind": "attached_repo_root",
                },
            }

            payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload

            self.assertEqual(
                payload["autonomy"]["action_packets"][0]["execution_preview"]["runner_kind"],
                "docker_isolated_runner",
            )
            self.assertEqual(
                payload["digital_body"]["access_state"]["sandbox_state"]["workspace_root_kind"],
                "attached_repo_root",
            )
            self.assertEqual(
                payload["digital_body"]["access_state"]["sandbox_state"]["network_policy"],
                "none",
            )
            self.assertEqual(payload["digital_body_consequence"]["sandbox_runner_kind"], "docker_isolated_runner")

    def test_turn_and_event_responses_surface_procedural_growth_payload(self):
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
                    "world_surfaces": ["filesystem", "sandbox"],
                    "access_state": {
                        "mode": "tool_enabled",
                        "filesystem_state": "writable",
                        "sandbox_mode": "restricted",
                        "sandbox_state": {
                            "availability": "restricted",
                            "execution_policy": "approval_required",
                            "runner_kind": "docker_isolated_runner",
                            "isolation_level": "docker_local_isolated",
                            "image_ref": "amadeus-thread0/sandbox-phase2:py312",
                            "network_policy": "none",
                            "workspace_root_kind": "attached_repo_root",
                        },
                    },
                    "resource_state": {
                        "completed_packet_count": 1,
                        "artifact_continuity": "attached",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": "E:/repo/amadeus-thread0",
                        "active_artifact_label": "amadeus-thread0",
                        "artifact_carrier": "filesystem",
                        "workspace_root": "E:/repo/amadeus-thread0",
                    },
                },
                "action_packets": [
                    {
                        "proposal_id": "ap-procedural-api",
                        "origin": "motive_goal",
                        "intent": "sandbox:execute_workspace_command",
                        "status": "completed",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "tool_name": "execute_workspace_command",
                        "result_summary": "pytest passed",
                        "execution_spec": {
                            "executor": "pytest",
                            "profile": "pytest",
                            "runner_kind": "docker_isolated_runner",
                            "isolation_level": "docker_local_isolated",
                            "image_ref": "amadeus-thread0/sandbox-phase2:py312",
                            "network_policy": "none",
                            "workspace_root_kind": "attached_repo_root",
                            "argv": ["pytest", "-q", "tests/test_demo.py"],
                            "cwd": "E:/repo/amadeus-thread0",
                            "allowed_roots": ["E:/repo/amadeus-thread0"],
                        },
                        "execution_result": {
                            "run_id": "run-procedural-api",
                            "status": "completed",
                            "exit_code": 0,
                            "stdout_log_ref": "E:/repo/.amadeus/sandbox-runs/run-procedural-api/stdout.txt",
                            "stderr_log_ref": "E:/repo/.amadeus/sandbox-runs/run-procedural-api/stderr.txt",
                        },
                    }
                ],
            }

            event_response = api.build_event_round_response(
                state_values=state_values,
                final_text="我把 pytest 跑完了。",
            )
            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")

            for payload in (event_response.payload, turn_response.payload):
                procedural = payload["procedural_growth"]
                self.assertTrue(procedural["procedural_growth"])
                self.assertEqual(procedural["traces"][0]["trace_kind"], "sandbox_execution_pattern")
                self.assertEqual(procedural["traces"][0]["source_run_id"], "run-procedural-api")
                self.assertTrue(procedural["procedural_hint"]["must_request_approval"])
                self.assertTrue(procedural["procedural_hint"]["capability_claim"])
                self.assertEqual(
                    payload["digital_body_consequence"]["procedural_continuity"]["traces"][0]["source_run_id"],
                    "run-procedural-api",
                )

    def test_turn_and_event_responses_surface_procedural_planning_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "autonomy_intent": {
                    "mode": "approval_pending",
                    "origin": "counterpart_request",
                    "requires_approval": True,
                    "primary_proposal_id": "ap-phase2-planning",
                },
                "procedural_planning": {
                    "planning_bias": True,
                    "bias_kind": "sandbox_execute",
                    "trace_id": "proc_phase2_api",
                    "trace_kind": "sandbox_execution_pattern",
                    "source_run_id": "run-phase2-api",
                    "source_tool_name": "execute_workspace_command",
                    "suggested_capability_family": "sandbox",
                    "suggested_pattern": "pytest",
                    "suggested_executor": "pytest",
                    "suggested_argv": ["pytest"],
                    "must_request_approval": True,
                    "requires_approval": True,
                    "capability_claim": True,
                    "confidence": 0.78,
                },
                "action_trace": [
                    {
                        "proposal_id": "ap-phase2-planning",
                        "event": "derived_from_procedural_planning",
                        "status": "awaiting_approval",
                        "procedural_planning": {
                            "planning_bias": True,
                            "bias_kind": "sandbox_execute",
                            "trace_id": "proc_phase2_api",
                            "trace_kind": "sandbox_execution_pattern",
                            "source_run_id": "run-phase2-api",
                            "source_tool_name": "execute_workspace_command",
                            "suggested_capability_family": "sandbox",
                            "suggested_pattern": "pytest",
                            "suggested_executor": "pytest",
                            "suggested_argv": ["pytest"],
                            "must_request_approval": True,
                            "requires_approval": True,
                            "capability_claim": True,
                            "confidence": 0.78,
                        },
                    }
                ],
            }

            event_response = api.build_event_round_response(
                state_values=state_values,
                final_text="我会按刚才的 pytest 轨迹继续，但先等审批。",
            )
            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")

            for payload in (event_response.payload, turn_response.payload):
                planning = payload["autonomy"]["procedural_planning"]
                self.assertEqual(planning["bias_kind"], "sandbox_execute")
                self.assertEqual(planning["trace_id"], "proc_phase2_api")
                self.assertTrue(planning["must_request_approval"])
                self.assertEqual(
                    payload["turn_summary"]["autonomy"]["procedural_planning"]["source_run_id"],
                    "run-phase2-api",
                )

    def test_turn_and_event_responses_surface_procedural_outcome_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "action_packets": [
                    {
                        "proposal_id": "ap-phase3-api",
                        "origin": "motive_goal",
                        "intent": "sandbox:execute_workspace_command",
                        "status": "completed",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "tool_name": "execute_workspace_command",
                        "result_summary": "pytest passed",
                        "tool_args": {
                            "procedural_planning": {
                                "planning_bias": True,
                                "bias_kind": "sandbox_execute",
                                "trace_id": "proc_phase3_api",
                                "trace_kind": "sandbox_execution_pattern",
                                "source_run_id": "run-phase3-prior",
                                "source_tool_name": "execute_workspace_command",
                                "suggested_capability_family": "sandbox",
                                "suggested_pattern": "pytest",
                                "suggested_executor": "pytest",
                                "suggested_argv": ["pytest"],
                                "must_request_approval": True,
                                "requires_approval": True,
                                "capability_claim": True,
                                "confidence": 0.7,
                            }
                        },
                        "execution_spec": {
                            "executor": "pytest",
                            "profile": "pytest",
                            "argv": ["pytest"],
                            "cwd": "E:/repo/amadeus-thread0",
                            "allowed_roots": ["E:/repo/amadeus-thread0"],
                        },
                        "execution_result": {
                            "run_id": "run-phase3-api",
                            "status": "completed",
                            "exit_code": 0,
                            "stdout_log_ref": "E:/repo/.amadeus/sandbox-runs/run-phase3-api/stdout.txt",
                        },
                    }
                ],
            }

            event_response = api.build_event_round_response(
                state_values=state_values,
                final_text="这次 pytest 跑通了。",
            )
            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")

            for payload in (event_response.payload, turn_response.payload):
                outcome = payload["procedural_outcome"]
                self.assertTrue(outcome["procedural_outcome"])
                self.assertEqual(outcome["last_outcome_kind"], "confirmed_success")
                self.assertEqual(outcome["source_trace_id"], "proc_phase3_api")
                self.assertEqual(outcome["source_run_id"], "run-phase3-api")
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["procedural_outcome"]["source_run_id"],
                    "run-phase3-api",
                )
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["procedural_outcome"]["outcome_kind"],
                    "confirmed_success",
                )

    def test_turn_and_event_responses_surface_procedural_recovery_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "action_packets": [
                    {
                        "proposal_id": "ap-phase4-api",
                        "origin": "motive_goal",
                        "intent": "sandbox:execute_workspace_command",
                        "status": "completed",
                        "risk": "external_mutation",
                        "requires_approval": True,
                        "tool_name": "execute_workspace_command",
                        "result_summary": "pytest failed",
                        "tool_args": {
                            "procedural_planning": {
                                "planning_bias": True,
                                "bias_kind": "sandbox_execute",
                                "trace_id": "proc_phase4_api",
                                "trace_kind": "sandbox_execution_pattern",
                                "source_run_id": "run-phase4-prior",
                                "source_tool_name": "execute_workspace_command",
                                "suggested_capability_family": "sandbox",
                                "suggested_pattern": "pytest",
                                "suggested_executor": "pytest",
                                "suggested_argv": ["pytest"],
                                "must_request_approval": True,
                                "requires_approval": True,
                                "capability_claim": True,
                                "confidence": 0.7,
                            }
                        },
                        "execution_spec": {
                            "executor": "pytest",
                            "profile": "pytest",
                            "argv": ["pytest"],
                            "cwd": "E:/repo/amadeus-thread0",
                            "allowed_roots": ["E:/repo/amadeus-thread0"],
                        },
                        "execution_result": {
                            "run_id": "run-phase4-api",
                            "status": "failed",
                            "exit_code": 2,
                            "stdout_log_ref": "E:/repo/.amadeus/sandbox-runs/run-phase4-api/stdout.txt",
                            "stderr_log_ref": "E:/repo/.amadeus/sandbox-runs/run-phase4-api/stderr.txt",
                            "error_summary": "process exited with code 2",
                        },
                    }
                ],
            }

            event_response = api.build_event_round_response(
                state_values=state_values,
                final_text="这次 pytest 没跑通，我先看日志。",
            )
            turn_response = api.build_turn_response(state_values=state_values, streamed_text="ignored")

            for payload in (event_response.payload, turn_response.payload):
                recovery = payload["procedural_recovery"]
                self.assertTrue(recovery["procedural_recovery"])
                self.assertEqual(recovery["last_recovery_kind"], "inspect_failure_artifact")
                self.assertEqual(recovery["source_trace_id"], "proc_phase4_api")
                self.assertEqual(recovery["source_run_id"], "run-phase4-api")
                self.assertFalse(recovery["safe_to_reuse"])
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["procedural_recovery"]["source_run_id"],
                    "run-phase4-api",
                )
                self.assertEqual(
                    payload["turn_summary"]["current_turn"]["procedural_recovery"]["recovery_kind"],
                    "inspect_failure_artifact",
                )

    def test_turn_and_event_responses_attach_embodied_interaction_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "final_text": "嗯，我听见了。",
                "current_event": {
                    "kind": "multimodal_observation",
                    "text": "panel.png",
                    "digital_body_hints": {
                        "multimodal_sources": [
                            {
                                "source_id": "img-backend-1",
                                "modality": "image",
                                "path": "fixtures/panel.png",
                                "consent_scope": "single_turn",
                                "capture_method": "operator_attached_file",
                                "label": "panel.png",
                            }
                        ]
                    },
                },
                "digital_body_state": {
                    "active_surface": "image",
                    "perception_channels": ["image"],
                    "action_channels": ["language"],
                    "world_surfaces": [],
                    "access_state": {"mode": "native_only"},
                    "resource_state": {
                        "artifact_continuity": "attached",
                        "active_artifact_kind": "image",
                        "active_artifact_ref": "fixtures/panel.png",
                        "active_artifact_label": "panel.png",
                    },
                },
                "interaction_carryover": {"embodied_context": {"kind": "multimodal_observation"}},
                "reconsolidation_snapshot": {"final_text": "嗯，我听见了。"},
            }

            turn_payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload
            event_payload = api.build_event_round_response(
                state_values=state_values,
                final_text="嗯，我听见了。",
            ).payload

            for payload in (turn_payload, event_payload):
                readback = payload["embodied_interaction"]
                self.assertEqual(readback["schema"], "embodied_interaction.runtime.v1")
                self.assertEqual(
                    readback["readiness_status"],
                    "embodied_interaction_runtime_phase1_ready",
                )
                self.assertEqual(
                    payload["current_event"]["perception_sources"][0]["source_ref_id"],
                    "img-backend-1",
                )
                self.assertEqual(payload["current_event"]["perception_sources"][0]["source_kind"], "image_file")
                self.assertEqual(
                    payload["digital_body"]["resource_state"]["multimodal_source_refs"],
                    ["img-backend-1"],
                )
                self.assertEqual(
                    payload["interaction_carryover"]["embodied_context"]["multimodal_sources"][0][
                        "source_ref_id"
                    ],
                    "img-backend-1",
                )

    def test_turn_response_applies_chinese_semantic_floor_to_final_and_snapshot_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_db = root / "checkpoints.sqlite"
            checkpoint_db.write_bytes(b"x")
            api, _ = self._build_api(base_data_dir=root, checkpoint_db_path=checkpoint_db)
            state_values = {
                "final_text": "请问有什么可以帮你？",
                "reconsolidation_snapshot": {"final_text": "请问有什么可以帮你？"},
            }

            payload = api.build_turn_response(state_values=state_values, streamed_text="ignored").payload

            self.assertEqual(payload["final_text"], "嗯，我在。你直接说吧，我会顺着这轮的语境接住。")
            self.assertEqual(payload["reconsolidation_snapshot"]["final_text"], payload["final_text"])
            self.assertTrue(payload["embodied_interaction"]["chinese_semantic_surface"]["applied_floor"])


if __name__ == "__main__":
    unittest.main()
