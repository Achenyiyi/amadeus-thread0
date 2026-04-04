from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from amadeus_thread0.utils.tools import inspect_workspace_path, write_workspace_file


def test_inspect_workspace_path_reads_file_inside_bounded_workspace():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        target = workspace / "notes" / "today.md"
        target.parent.mkdir(parents=True)
        target.write_text("hello from workspace\n" * 12, encoding="utf-8")
        env = {
            "AMADEUS_DATA_DIR": str(runtime_dir),
            "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        }
        with patch.dict(os.environ, env, clear=True):
            payload = inspect_workspace_path.invoke(
                {
                    "relative_path": "notes/today.md",
                    "access_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": str(workspace),
                        "active_artifact_label": "lab-notes",
                    },
                }
            )

        assert payload["workspace_name"] == "lab-notes"
        assert payload["relative_path"] == "notes/today.md"
        assert payload["artifact_kind"] == "file"
        assert payload["artifact_ref"] == str(target)
        assert "hello from workspace" in payload["artifact_preview"]
        assert payload["artifact_context"]["artifact_kind"] == "file"
        assert payload["artifact_context"]["source_tool_name"] == "inspect_workspace_path"
        assert payload["artifact_context"]["workspace_root"] == str(workspace)
        assert payload["access_hints"]["active_artifact_kind"] == "file"
        assert payload["access_hints"]["artifact_source_tool_name"] == "inspect_workspace_path"
        assert payload["access_hints"]["workspace_root"] == str(workspace)


def test_inspect_workspace_path_reads_directory_inside_bounded_workspace():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        folder = workspace / "notes" / "drafts"
        folder.mkdir(parents=True)
        (folder / "a.txt").write_text("a", encoding="utf-8")
        (folder / "b.txt").write_text("b", encoding="utf-8")
        env = {
            "AMADEUS_DATA_DIR": str(runtime_dir),
            "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        }
        with patch.dict(os.environ, env, clear=True):
            payload = inspect_workspace_path.invoke(
                {
                    "relative_path": "notes/drafts",
                    "access_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": str(workspace),
                        "active_artifact_label": "lab-notes",
                    },
                }
            )

        assert payload["artifact_kind"] == "workspace"
        assert payload["artifact_ref"] == str(folder)
        assert payload["artifact_context"]["artifact_kind"] == "workspace"
        assert payload["artifact_context"]["source_tool_name"] == "inspect_workspace_path"
        assert payload["artifact_context"]["workspace_root"] == str(workspace)
        assert "a.txt" in payload["artifact_preview"]
        assert "b.txt" in payload["artifact_preview"]
        assert payload["access_hints"]["active_artifact_kind"] == "workspace"
        assert payload["access_hints"]["active_artifact_ref"] == str(folder)
        assert payload["access_hints"]["workspace_path"] == str(folder)
        assert payload["access_hints"]["workspace_root"] == str(workspace)


def test_inspect_workspace_path_rejects_workspace_escape():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        workspace.mkdir(parents=True)
        env = {
            "AMADEUS_DATA_DIR": str(runtime_dir),
            "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="BAD_INPUT|INVALID_TARGET"):
                inspect_workspace_path.invoke(
                    {
                        "relative_path": "..\\outside.txt",
                        "access_hints": {
                            "filesystem_state": "writable",
                            "active_artifact_kind": "workspace",
                            "active_artifact_ref": str(workspace),
                            "active_artifact_label": "lab-notes",
                        },
                    }
                )


def test_write_workspace_file_keeps_workspace_root_when_active_surface_is_subdirectory():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        folder = workspace / "notes" / "drafts"
        folder.mkdir(parents=True)
        (folder / "a.txt").write_text("a", encoding="utf-8")
        env = {
            "AMADEUS_DATA_DIR": str(runtime_dir),
            "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        }
        with patch.dict(os.environ, env, clear=True):
            inspection = inspect_workspace_path.invoke(
                {
                    "relative_path": "notes/drafts",
                    "access_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": str(workspace),
                        "active_artifact_label": "lab-notes",
                    },
                }
            )
            payload = write_workspace_file.invoke(
                {
                    "relative_path": "todo.md",
                    "content": "top-level file",
                    "access_hints": inspection["access_hints"],
                }
            )

        target = workspace / "todo.md"
        assert target.exists()
        assert target.read_text(encoding="utf-8") == "top-level file"
        assert payload["file_path"] == str(target)
        assert inspection["access_hints"]["workspace_root"] == str(workspace)
        assert payload["access_hints"]["workspace_root"] == str(workspace)
