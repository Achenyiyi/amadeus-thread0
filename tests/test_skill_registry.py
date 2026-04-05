from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from amadeus_thread0.runtime.skill_registry import SkillRegistryManager, SkillSecurityError


def _skill_markdown(
    *,
    name: str,
    description: str,
    version: str,
    skill_id: str,
    triggers: list[str] | None = None,
    required_surfaces: list[str] | None = None,
    allowed_tools: list[str] | None = None,
    sandbox_profiles: list[str] | None = None,
    source: str = "local_authored",
    trust_tier: str = "authored",
    body: str = "## Instructions\nUse this skill carefully.\n",
) -> str:
    return "\n".join(
        [
            "---",
            f"name: {name}",
            f"description: {description}",
            f"version: {version}",
            f"skill_id: {skill_id}",
            "kind: executable",
            f"triggers: {json.dumps(triggers or [], ensure_ascii=False)}",
            f"required_surfaces: {json.dumps(required_surfaces or [], ensure_ascii=False)}",
            f"allowed_tools: {json.dumps(allowed_tools or [], ensure_ascii=False)}",
            f"sandbox_profiles: {json.dumps(sandbox_profiles or [], ensure_ascii=False)}",
            f"source: {source}",
            f"trust_tier: {trust_tier}",
            "---",
            body.strip(),
            "",
        ]
    )


class SkillRegistryTests(unittest.TestCase):
    def _write_local_skill(
        self,
        repo_root: Path,
        *,
        skill_id: str,
        name: str | None = None,
        description: str = "Runtime skill",
        version: str = "1.0.0",
        triggers: list[str] | None = None,
        required_surfaces: list[str] | None = None,
        allowed_tools: list[str] | None = None,
        sandbox_profiles: list[str] | None = None,
        body: str = "## Instructions\nUse this skill carefully.\n",
    ) -> Path:
        skill_root = repo_root / "skills" / skill_id
        skill_root.mkdir(parents=True, exist_ok=True)
        (skill_root / "SKILL.md").write_text(
            _skill_markdown(
                name=name or skill_id,
                description=description,
                version=version,
                skill_id=skill_id,
                triggers=triggers,
                required_surfaces=required_surfaces,
                allowed_tools=allowed_tools,
                sandbox_profiles=sandbox_profiles,
                body=body,
            ),
            encoding="utf-8",
        )
        return skill_root

    def _write_remote_catalog(
        self,
        *,
        path: Path,
        skill_id: str,
        version: str,
        package_url: str,
        package_hash: str,
        description: str = "Remote runtime skill",
        requested_permissions: list[str] | None = None,
        sandbox_profiles: list[str] | None = None,
    ) -> None:
        payload = {
            "skills": [
                {
                    "skill_id": skill_id,
                    "name": skill_id,
                    "description": description,
                    "version": version,
                    "kind": "executable",
                    "source": "official_registry",
                    "trust_tier": "verified",
                    "status": "catalog_remote",
                    "required_surfaces": ["filesystem"],
                    "allowed_tools": ["execute_workspace_command"],
                    "sandbox_profiles": sandbox_profiles or ["workspace_write"],
                    "requested_permissions": requested_permissions or ["filesystem_read"],
                    "hash": package_hash,
                    "package_url": package_url,
                    "verification_summary": "registry verified",
                }
            ]
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _build_remote_archive(
        self,
        root: Path,
        *,
        skill_id: str,
        version: str,
        extra_entries: list[tuple[zipfile.ZipInfo | str, str]] | None = None,
    ) -> tuple[Path, str]:
        archive_path = root / f"{skill_id}-{version}.zip"
        body = f"## Instructions\nUse {skill_id} {version}.\n"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr(
                "SKILL.md",
                _skill_markdown(
                    name=skill_id,
                    description=f"{skill_id} {version}",
                    version=version,
                    skill_id=skill_id,
                    triggers=["pytest", "test"],
                    required_surfaces=["filesystem"],
                    allowed_tools=["execute_workspace_command"],
                    sandbox_profiles=["workspace_write"],
                    source="official_registry",
                    trust_tier="verified",
                    body=body,
                ),
            )
            archive.writestr("scripts/run.py", "print('ok')\n")
            for entry, content in extra_entries or []:
                archive.writestr(entry, content)
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        return archive_path, digest

    def test_local_discovery_uses_progressive_disclosure(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            data_root = Path(tmp) / "data"
            repo_root.mkdir(parents=True, exist_ok=True)
            data_root.mkdir(parents=True, exist_ok=True)
            self._write_local_skill(
                repo_root,
                skill_id="pytest-helper",
                description="Helps with pytest workflows",
                triggers=["pytest", "testing"],
                required_surfaces=["filesystem"],
                allowed_tools=["execute_workspace_command"],
                sandbox_profiles=["workspace_write"],
                body="## Instructions\nRun pytest first, then inspect failures.\n",
            )
            manager = SkillRegistryManager(base_dir=repo_root, data_dir=data_root)

            state = manager.compute_session_skill_state(
                thread_id="thread-a",
                query_text="please use pytest testing on this workspace",
                current_event={"text": "use pytest"},
                digital_body_state={"resource_state": {"workspace_root": "E:/runtime/workspace"}},
            )

            self.assertEqual(state["catalog_entries"][0]["skill_id"], "pytest-helper")
            self.assertFalse(state["catalog_entries"][0].get("skill_excerpt"))
            self.assertEqual(state["active_skill_ids"], ["pytest-helper"])
            self.assertIn("Run pytest first", state["active_skill_entries"][0]["skill_excerpt"])

            inspected = manager.inspect("pytest-helper")
            self.assertIn("Run pytest first", inspected["skill_excerpt"])

    def test_auto_match_respects_manual_disable_and_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            data_root = Path(tmp) / "data"
            repo_root.mkdir(parents=True, exist_ok=True)
            data_root.mkdir(parents=True, exist_ok=True)
            self._write_local_skill(
                repo_root,
                skill_id="pytest-helper",
                description="Helps with pytest workflows",
                triggers=["pytest", "testing"],
                required_surfaces=["filesystem"],
            )
            self._write_local_skill(
                repo_root,
                skill_id="web-research",
                description="Helps with web research",
                triggers=["research", "web"],
                required_surfaces=["source_ref"],
            )
            manager = SkillRegistryManager(base_dir=repo_root, data_dir=data_root)

            matched = manager.compute_session_skill_state(
                thread_id="thread-a",
                query_text="pytest this project",
                current_event={"text": "pytest this project"},
                digital_body_state={"resource_state": {"workspace_root": "E:/runtime/workspace"}},
            )
            self.assertEqual(matched["active_skill_ids"], ["pytest-helper"])

            manager.disable(skill_id="pytest-helper", thread_id="thread-a")
            disabled = manager.compute_session_skill_state(
                thread_id="thread-a",
                query_text="pytest this project",
                current_event={"text": "pytest this project"},
                digital_body_state={"resource_state": {"workspace_root": "E:/runtime/workspace"}},
            )
            self.assertEqual(disabled["active_skill_ids"], [])

            manager.pin(skill_id="web-research", thread_id="thread-a")
            pinned = manager.compute_session_skill_state(
                thread_id="thread-a",
                query_text="pytest this project",
                current_event={"text": "pytest this project"},
                digital_body_state={"resource_state": {"workspace_root": "E:/runtime/workspace"}},
            )
            self.assertEqual(pinned["active_skill_ids"][0], "web-research")
            self.assertIn("web-research", pinned["manual_overrides"]["pinned"])

    def test_remote_install_and_update_keep_registry_and_lock_in_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            data_root = Path(tmp) / "data"
            catalog_path = Path(tmp) / "catalog.json"
            repo_root.mkdir(parents=True, exist_ok=True)
            data_root.mkdir(parents=True, exist_ok=True)

            v1_archive, v1_hash = self._build_remote_archive(Path(tmp), skill_id="research-pack", version="1.0.0")
            self._write_remote_catalog(
                path=catalog_path,
                skill_id="research-pack",
                version="1.0.0",
                package_url=str(v1_archive),
                package_hash=v1_hash,
            )
            manager = SkillRegistryManager(
                base_dir=repo_root,
                data_dir=data_root,
                registry_url=str(catalog_path),
                allow_local_remote_source=True,
            )

            install_preview = manager.preview_operation(operation="install", skill_id="research-pack")
            installed = manager.install(
                skill_id="research-pack",
                resolved_version=install_preview["resolved_version"],
                source=install_preview["source"],
                hash_value=install_preview["hash"],
                requested_permissions=install_preview["requested_permissions"],
                sandbox_profiles=install_preview["sandbox_profiles"],
                verification_summary=install_preview["verification_summary"],
            )
            self.assertEqual(installed["version"], "1.0.0")

            v2_archive, v2_hash = self._build_remote_archive(Path(tmp), skill_id="research-pack", version="1.1.0")
            self._write_remote_catalog(
                path=catalog_path,
                skill_id="research-pack",
                version="1.1.0",
                package_url=str(v2_archive),
                package_hash=v2_hash,
            )
            update_preview = manager.preview_operation(operation="update", skill_id="research-pack")
            updated = manager.update(
                skill_id="research-pack",
                resolved_version=update_preview["resolved_version"],
                source=update_preview["source"],
                hash_value=update_preview["hash"],
                requested_permissions=update_preview["requested_permissions"],
                sandbox_profiles=update_preview["sandbox_profiles"],
                verification_summary=update_preview["verification_summary"],
            )
            self.assertEqual(updated["version"], "1.1.0")

            registry = json.loads((data_root / "skills" / "registry.json").read_text(encoding="utf-8"))
            registry_entry = registry["skills"][0]
            lock_payload = json.loads(
                (data_root / "skills" / "installed" / "research-pack" / "1.1.0" / "skill.lock.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(registry_entry["version"], "1.1.0")
            self.assertEqual(lock_payload["version"], "1.1.0")
            self.assertEqual(registry_entry["hash"], lock_payload["hash"])
            self.assertEqual(registry_entry["source"], lock_payload["source"])
            self.assertEqual(registry["catalog_version"], manager.registry_snapshot()["catalog_version"])

    def test_install_rejects_zip_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            data_root = Path(tmp) / "data"
            catalog_path = Path(tmp) / "catalog.json"
            repo_root.mkdir(parents=True, exist_ok=True)
            data_root.mkdir(parents=True, exist_ok=True)
            archive_path, digest = self._build_remote_archive(
                Path(tmp),
                skill_id="unsafe-pack",
                version="1.0.0",
                extra_entries=[("../escape.txt", "boom")],
            )
            self._write_remote_catalog(
                path=catalog_path,
                skill_id="unsafe-pack",
                version="1.0.0",
                package_url=str(archive_path),
                package_hash=digest,
            )
            manager = SkillRegistryManager(
                base_dir=repo_root,
                data_dir=data_root,
                registry_url=str(catalog_path),
                allow_local_remote_source=True,
            )

            preview = manager.preview_operation(operation="install", skill_id="unsafe-pack")
            with self.assertRaises(SkillSecurityError):
                manager.install(
                    skill_id="unsafe-pack",
                    resolved_version=preview["resolved_version"],
                    source=preview["source"],
                    hash_value=preview["hash"],
                )

    def test_install_rejects_zip_symlink_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            data_root = Path(tmp) / "data"
            catalog_path = Path(tmp) / "catalog.json"
            repo_root.mkdir(parents=True, exist_ok=True)
            data_root.mkdir(parents=True, exist_ok=True)

            symlink_dir = zipfile.ZipInfo("evil-link/")
            symlink_dir.create_system = 3
            symlink_dir.external_attr = 0o120777 << 16

            archive_path, digest = self._build_remote_archive(
                Path(tmp),
                skill_id="unsafe-symlink",
                version="1.0.0",
                extra_entries=[(symlink_dir, "")],
            )
            self._write_remote_catalog(
                path=catalog_path,
                skill_id="unsafe-symlink",
                version="1.0.0",
                package_url=str(archive_path),
                package_hash=digest,
            )
            manager = SkillRegistryManager(
                base_dir=repo_root,
                data_dir=data_root,
                registry_url=str(catalog_path),
                allow_local_remote_source=True,
            )

            preview = manager.preview_operation(operation="install", skill_id="unsafe-symlink")
            with self.assertRaises(SkillSecurityError):
                manager.install(
                    skill_id="unsafe-symlink",
                    resolved_version=preview["resolved_version"],
                    source=preview["source"],
                    hash_value=preview["hash"],
                )


if __name__ == "__main__":
    unittest.main()
