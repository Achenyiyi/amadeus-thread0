from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amadeus_thread0.graph_parts.skill_runtime import (
    active_skill_prompt_block,
    backend_skill_envelope,
    derive_procedural_continuity,
)
from amadeus_thread0.runtime.skill_registry import SkillRegistryManager
from amadeus_thread0.utils.tools import add_skill, list_skills


class _FakeSkillStore:
    def __init__(self):
        self._skills: list[dict[str, object]] = []

    def list_skills(self) -> list[dict[str, object]]:
        return list(self._skills)

    def add_skill(self, name: str, description: str, steps: list[str] | None = None) -> None:
        self._skills = [
            {"name": name, "description": description, "steps": list(steps or [])},
        ]

    def append_memory_ledger(self, **_: object) -> None:
        return None


class SkillRuntimeTests(unittest.TestCase):
    def test_backend_skill_envelope_keeps_pending_skill_proposal_outside_active_state(self):
        payload = backend_skill_envelope(
            {
                "catalog_version": "catalog-v1",
                "catalog_entries": [
                    {
                        "skill_id": "pytest-helper",
                        "name": "pytest-helper",
                        "description": "Helps with pytest workflows",
                        "version": "1.0.0",
                        "status": "installed",
                    }
                ],
                "matched_skill_entries": [],
                "active_skill_entries": [],
                "manual_overrides": {"enabled": [], "disabled": [], "pinned": []},
            },
            pending_action_proposal={
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
        )

        self.assertEqual(payload["installed"][0]["skill_id"], "pytest-helper")
        self.assertEqual(payload["active"], [])
        self.assertEqual(payload["pending_approval"]["proposal_id"], "ap-skill-install-1")
        self.assertEqual(payload["pending_approval"]["resolved_version"], "1.1.0")

    def test_active_skill_prompt_block_only_uses_active_entries(self):
        block = active_skill_prompt_block(
            {
                "catalog_entries": [
                    {
                        "skill_id": "catalog-only",
                        "name": "catalog-only",
                        "description": "Should stay out of prompt",
                    }
                ],
                "active_skill_entries": [
                    {
                        "skill_id": "pytest-helper",
                        "name": "pytest-helper",
                        "description": "Helps with pytest workflows",
                        "triggers": ["pytest", "testing"],
                        "required_surfaces": ["filesystem"],
                        "allowed_tools": ["execute_workspace_command"],
                        "skill_excerpt": "Run pytest first, then inspect failures.",
                    }
                ],
            }
        )

        self.assertIn("pytest-helper", block)
        self.assertIn("Run pytest first", block)
        self.assertNotIn("catalog-only", block)

    def test_active_skill_prompt_block_preserves_persona_core_isolation(self):
        block = active_skill_prompt_block(
            {
                "active_skill_entries": [
                    {
                        "skill_id": "source-ref-anchor-review",
                        "name": "source-ref-anchor-review",
                        "description": "Read continuity-focused source material",
                        "triggers": ["source_ref"],
                        "required_surfaces": ["source_ref"],
                        "allowed_tools": ["inspect_source_ref", "search_web"],
                        "skill_excerpt": "Inspect the preferred saved source first.",
                    }
                ]
            }
        )

        self.assertIn("skills 只影响工具选择、执行策略和资源绑定", block)
        self.assertIn("不改写人格核心、关系立场或最终审批边界", block)

    def test_legacy_skill_notes_remain_isolated_from_runtime_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _FakeSkillStore()
            manager = SkillRegistryManager(base_dir=Path(tmp) / "repo", data_dir=Path(tmp) / "data")

            with patch("amadeus_thread0.utils.tools._get_store", return_value=store):
                add_skill.invoke(
                    {
                        "name": "legacy note",
                        "description": "Compatibility-only skill note",
                        "steps": ["remember this old note"],
                    }
                )
                legacy = list_skills.invoke({"limit": 10})

            self.assertEqual(legacy[0]["name"], "legacy note")
            self.assertEqual(manager.runtime_catalog(), [])

    def test_completed_skill_usage_derives_identity_safe_procedural_continuity(self):
        continuity = derive_procedural_continuity(
            {
                "kind": "skill_usage_completed",
                "primary_status": "completed",
                "primary_tool_name": "inspect_source_ref",
                "primary_proposal_id": "ap-skill-use-1",
                "skill_effects": [
                    {
                        "skill_id": "source-ref-anchor-review",
                        "operation": "use",
                        "status": "completed",
                        "use_kind": "source_ref_continuity",
                        "tool_name": "inspect_source_ref",
                    }
                ],
                "artifact_carrier": "source_ref",
                "active_artifact_label": "LangGraph Persistence",
            }
        )

        self.assertEqual(continuity["capability_family"], "skill")
        self.assertEqual(continuity["pattern"], "source_ref_continuity")
        self.assertEqual(continuity["last_success_ref"], "ap-skill-use-1")
        self.assertTrue(continuity["identity_safe"])
        self.assertGreater(continuity["confidence"], 0.0)

    def test_blocked_skill_mutation_does_not_derive_procedural_continuity(self):
        continuity = derive_procedural_continuity(
            {
                "kind": "skill_mutation_blocked",
                "primary_status": "blocked",
                "primary_tool_name": "install_skill",
                "primary_proposal_id": "ap-skill-blocked-1",
                "skill_effects": [
                    {
                        "skill_id": "blocked-anchor-pack",
                        "operation": "install",
                        "status": "blocked",
                        "tool_name": "install_skill",
                    }
                ],
            }
        )

        self.assertEqual(continuity, {})


if __name__ == "__main__":
    unittest.main()
