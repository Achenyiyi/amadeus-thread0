from __future__ import annotations

import unittest
from types import SimpleNamespace

from amadeus_thread0.runtime.memory_admin import (
    MemoryAdminError,
    MemoryAdminService,
    ReflectionProposal,
)


class FakeMemoryStore:
    def __init__(self):
        self.profile = {
            "nickname": "旧昵称",
            "user_model_rules": [
                {"text": "不要太晚睡", "importance": 0.8, "reflection_id": 1, "derived_from": [1], "created_at": 1}
            ],
        }
        self.profile_meta = {
            "nickname": {
                "old_value": "更早的昵称",
                "new_value": "旧昵称",
                "source": "user_correction",
            }
        }
        self.moments = [
            {"id": 1, "summary": "她提醒我早点休息"},
            {"id": 2, "summary": "她不喜欢被轻浮地打趣"},
        ]
        self.reflections = [
            {"id": 10, "text": "她对轻浮玩笑比较敏感", "importance": 0.72, "derived_from": [2]},
        ]
        self.added_reflections: list[tuple[str, list[int], float]] = []
        self.set_profile_calls: list[tuple[str, object]] = []
        self.set_profile_meta_calls: list[tuple[str, dict]] = []

    def snapshot(self):
        return {
            "profile": dict(self.profile),
            "relationship": {"stage": "warming"},
            "moments": list(self.moments),
        }

    def get_profile(self):
        return dict(self.profile)

    def get_profile_meta(self):
        return dict(self.profile_meta)

    def set_profile(self, key, value):
        self.profile[key] = value
        self.set_profile_calls.append((key, value))

    def set_profile_meta(self, key, meta):
        self.profile_meta[key] = dict(meta)
        self.set_profile_meta_calls.append((key, dict(meta)))

    def delete_profile(self, key):
        existed = key in self.profile
        self.profile.pop(key, None)
        return existed

    def list_moments(self, limit=20):
        return list(self.moments[:limit])

    def delete_moment(self, moment_id):
        before = len(self.moments)
        self.moments = [item for item in self.moments if int(item.get("id")) != int(moment_id)]
        return len(self.moments) != before

    def list_reflections(self, limit=20):
        return list(self.reflections[:limit])

    def delete_reflection(self, reflection_id):
        before = len(self.reflections)
        self.reflections = [item for item in self.reflections if int(item.get("id")) != int(reflection_id)]
        return len(self.reflections) != before

    def add_reflection(self, text, derived_from=None, importance=None):
        reflection_id = 100 + len(self.added_reflections)
        self.added_reflections.append((text, list(derived_from or []), float(importance or 0.0)))
        return reflection_id


class FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        content = self._responses.pop(0)
        return SimpleNamespace(content=content)


class MemoryAdminServiceTests(unittest.TestCase):
    def test_prepare_and_apply_profile_correction(self):
        store = FakeMemoryStore()
        service = MemoryAdminService(memory_store=store, llm_factory=lambda **_: None)

        preview = service.prepare_profile_correction("nickname", "新昵称", reason="用户更正")
        self.assertEqual(preview.old_value, "旧昵称")
        self.assertEqual(preview.new_value, "新昵称")

        service.apply_profile_correction(preview, confirmed_by="tester")
        self.assertEqual(store.profile["nickname"], "新昵称")
        self.assertEqual(store.profile_meta["nickname"]["source"], "user_correction")
        self.assertEqual(store.profile_meta["nickname"]["confirmed_by"], "tester")

    def test_snapshot_view_normalizes_revision_trace_exports(self):
        raw_snapshot = {
            "profile": {"nickname": "旧昵称"},
            "worldline_events": [
                {
                    "id": 5,
                    "content": {
                        "summary": "她把这次入口接通记成了一次真实发生过的共事。 ",
                        "category": "shared_event",
                        "importance": 0.73,
                    },
                }
            ],
            "commitments": [
                {
                    "id": 6,
                    "content": {
                        "text": "晚点继续看 lab-notes。",
                        "status": "open",
                    },
                }
            ],
            "counterpart_assessment_history": [
                {
                    "id": 8,
                    "content": {
                        "summary": "她确认这次工作面真的接回来了。",
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
                            "session_continuity": "stable",
                        },
                    },
                }
            ],
            "proactive_continuity_history": [
                {
                    "id": 9,
                    "content": {
                        "summary": "她把这条稳定入口继续带进后续连续性里。",
                        "kind": "promoted",
                        "trace_family": "access_state_refresh_followthrough",
                        "carryover_strength": "0.53",
                        "embodied_context": {
                            "kind": "access_state_refreshed",
                            "api_key_state": "present",
                            "network_access": "enabled",
                            "filesystem_state": "writable",
                        },
                    },
                }
            ],
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
                    "interaction_carryover": {
                        "embodied_context": {
                            "kind": "access_state_refreshed",
                            "api_key_state": "present",
                            "quota_state": "healthy",
                            "filesystem_state": "writable",
                            "network_access": "enabled",
                        }
                    },
                }
            ],
        }
        store = FakeMemoryStore()
        store.snapshot = lambda: raw_snapshot
        service = MemoryAdminService(memory_store=store, llm_factory=lambda **_: None)

        snapshot = service.snapshot_view()

        self.assertEqual(snapshot["revision_traces"][0]["embodied_context"]["kind"], "access_state_refreshed")
        self.assertEqual(snapshot["revision_traces"][0]["embodied_context"]["api_key_state"], "present")
        self.assertEqual(snapshot["revision_traces"][0]["embodied_context"]["quota_state"], "healthy")
        self.assertIn("bodyfx=access_state_refreshed", snapshot["revision_traces"][0].get("preview_line") or "")
        self.assertEqual(snapshot["worldline_events"][0]["summary"], "她把这次入口接通记成了一次真实发生过的共事。")
        self.assertEqual(snapshot["worldline_events"][0]["category"], "shared_event")
        self.assertEqual(snapshot["commitments"][0]["text"], "晚点继续看 lab-notes。")
        self.assertEqual(snapshot["commitments"][0]["status"], "open")
        self.assertEqual(snapshot["counterpart_assessment_history"][0]["scene"], "co_work")
        self.assertEqual(snapshot["counterpart_assessment_history"][0]["embodied_context"]["kind"], "workspace_access_resolved")
        self.assertIn(
            "bodyfx=workspace_access_resolved",
            snapshot["counterpart_assessment_history"][0].get("preview_line") or "",
        )
        self.assertEqual(snapshot["proactive_continuity_history"][0]["trace_family"], "access_state_refresh_followthrough")
        self.assertEqual(snapshot["proactive_continuity_history"][0]["carryover_strength"], 0.53)
        self.assertEqual(snapshot["proactive_continuity_history"][0]["embodied_context"]["kind"], "access_state_refreshed")
        self.assertIn(
            "bodyfx=access_state_refreshed",
            snapshot["proactive_continuity_history"][0].get("preview_line") or "",
        )
        self.assertEqual(snapshot["counterpart_assessment_history"][0]["respect_level"], 0.76)
        self.assertEqual(
            snapshot["counterpart_assessment_history"][0]["assessment_profile"]["dominant_scene_signal"],
            "care",
        )
        self.assertEqual(
            snapshot["counterpart_assessment_history"][0]["content"]["assessment_profile"]["dominant_scene_signal"],
            "care",
        )
        self.assertEqual(snapshot["source_refs"][0]["id"], 17)
        self.assertEqual(snapshot["source_refs"][0]["source_id"], 17)
        self.assertEqual(snapshot["source_refs"][0]["title"], "Persistence")
        self.assertEqual(snapshot["source_refs"][0]["tool_name"], "search_web")
        self.assertEqual(snapshot["source_refs"][0]["embodied_context"]["preferred_source_ref_id"], 17)
        self.assertEqual(snapshot["source_refs"][0]["embodied_context"]["artifact_source_ref_ids"], [17, 9])
        self.assertEqual(snapshot["source_refs"][0]["embodied_context"]["preferred_anchor_reason"], "currently_active")
        self.assertIn("bodyfx=source_material_compared", snapshot["source_refs"][0].get("preview_line") or "")
        self.assertIn("source=Persistence", snapshot["source_refs"][0].get("preview_line") or "")
        self.assertNotIn("embodied_context", raw_snapshot["revision_traces"][0])
        self.assertNotIn("embodied_context", raw_snapshot["counterpart_assessment_history"][0])
        self.assertNotIn("embodied_context", raw_snapshot["proactive_continuity_history"][0])
        self.assertNotIn("embodied_context", raw_snapshot["source_refs"][0])

    def test_prepare_undo_profile_correction_raises_with_details_on_conflict(self):
        store = FakeMemoryStore()
        store.profile["nickname"] = "已经变了"
        service = MemoryAdminService(memory_store=store, llm_factory=lambda **_: None)

        with self.assertRaises(MemoryAdminError) as ctx:
            service.prepare_undo_profile_correction("nickname", reason="回滚")

        self.assertIn("拒绝自动撤销", str(ctx.exception))
        self.assertEqual(ctx.exception.details["current"], "已经变了")
        self.assertEqual(ctx.exception.details["meta_new_value"], "旧昵称")

    def test_apply_undo_profile_correction_restores_old_value(self):
        store = FakeMemoryStore()
        service = MemoryAdminService(memory_store=store, llm_factory=lambda **_: None)

        preview = service.prepare_undo_profile_correction("nickname", reason="回滚")
        service.apply_undo_profile_correction(preview, confirmed_by="tester")

        self.assertEqual(store.profile["nickname"], "更早的昵称")
        self.assertEqual(store.profile_meta["nickname"]["source"], "undo_correction")
        self.assertEqual(store.profile_meta["nickname"]["confirmed_by"], "tester")

    def test_generate_reflection_proposals_retries_then_parses(self):
        store = FakeMemoryStore()
        llm = FakeLLM(
            [
                "not-json",
                '[{"text":"她会记住你的作息","derived_from":[1,2],"importance":0.88}]',
            ]
        )
        service = MemoryAdminService(memory_store=store, llm_factory=lambda **_: llm)

        proposals = service.generate_reflection_proposals(moment_limit=10)

        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].text, "她会记住你的作息")
        self.assertEqual(proposals[0].derived_from, [1, 2])
        self.assertEqual(proposals[0].importance, 0.88)
        self.assertEqual(len(llm.calls), 2)

    def test_write_reflection_can_append_deduped_user_model_rule(self):
        store = FakeMemoryStore()
        service = MemoryAdminService(memory_store=store, llm_factory=lambda **_: None)

        first = service.write_reflection(
            ReflectionProposal(text="不要太晚睡", derived_from=[1], importance=0.7),
            write_user_model_rule=True,
        )
        second = service.write_reflection(
            ReflectionProposal(text="她会在意你有没有吃饭", derived_from=[1, 2], importance=0.9),
            write_user_model_rule=True,
        )

        self.assertTrue(first.wrote_user_model_rule)
        self.assertTrue(second.wrote_user_model_rule)
        rules = store.profile["user_model_rules"]
        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[0]["text"], "不要太晚睡")
        self.assertEqual(rules[1]["text"], "她会在意你有没有吃饭")
        self.assertEqual(store.profile_meta["user_model_rules"]["source"], "reflect_batch")

    def test_list_and_delete_memory_items(self):
        store = FakeMemoryStore()
        service = MemoryAdminService(memory_store=store, llm_factory=lambda **_: None)

        self.assertEqual(service.list_moments(limit=20)[0]["id"], 2)
        self.assertTrue(service.delete_moment(1))
        self.assertFalse(service.delete_moment(999))

        self.assertEqual(service.list_reflections(limit=20)[0]["id"], 10)
        self.assertTrue(service.delete_reflection(10))
        self.assertFalse(service.delete_reflection(999))


if __name__ == "__main__":
    unittest.main()
