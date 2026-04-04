from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from amadeus_thread0.utils.tools import (
    append_workspace_file,
    replace_workspace_lines,
    replace_workspace_text,
    write_workspace_file,
)


def test_write_workspace_file_writes_inside_bounded_runtime_workspace():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        workspace.mkdir(parents=True)
        env = {
            "AMADEUS_DATA_DIR": str(runtime_dir),
            "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        }
        with patch.dict(os.environ, env, clear=True):
            payload = write_workspace_file.invoke(
                {
                    "relative_path": "notes/today.md",
                    "content": "hello from amadeus",
                    "access_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": str(workspace),
                        "active_artifact_label": "lab-notes",
                    },
                }
            )

        target_path = workspace / "notes" / "today.md"
        assert target_path.exists()
        assert target_path.read_text(encoding="utf-8") == "hello from amadeus"
        assert payload["workspace_name"] == "lab-notes"
        assert payload["relative_path"] == "notes/today.md"
        assert payload["file_path"] == str(target_path)
        assert payload["filesystem_state"] == "writable"
        assert payload["access_hints"]["active_artifact_kind"] == "file"
        assert payload["resource_state"]["active_artifact_kind"] == "file"
        assert payload["artifact_context"]["artifact_kind"] == "file"
        assert payload["artifact_context"]["artifact_ref"] == str(target_path)
        assert payload["artifact_context"]["workspace_root"] == str(workspace)


def test_write_workspace_file_rejects_workspace_escape():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        workspace.mkdir(parents=True)
        env = {
            "AMADEUS_DATA_DIR": str(runtime_dir),
            "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="BAD_INPUT"):
                write_workspace_file.invoke(
                    {
                        "relative_path": "..\\outside.txt",
                        "content": "escape",
                        "access_hints": {
                            "filesystem_state": "writable",
                            "active_artifact_kind": "workspace",
                            "active_artifact_ref": str(workspace),
                            "active_artifact_label": "lab-notes",
                        },
                    }
                )


def test_append_workspace_file_appends_inside_bounded_runtime_workspace():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        workspace.mkdir(parents=True)
        target = workspace / "notes" / "today.md"
        target.parent.mkdir(parents=True)
        target.write_text("hello", encoding="utf-8")
        env = {
            "AMADEUS_DATA_DIR": str(runtime_dir),
            "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        }
        with patch.dict(os.environ, env, clear=True):
            payload = append_workspace_file.invoke(
                {
                    "relative_path": "notes/today.md",
                    "content": " world",
                    "access_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": str(workspace),
                        "active_artifact_label": "lab-notes",
                    },
                }
            )

        assert target.read_text(encoding="utf-8") == "hello world"
        assert payload["created_new"] is False
        assert payload["bytes_written"] == len(" world".encode("utf-8"))
        assert payload["artifact_context"]["artifact_kind"] == "file"
        assert payload["artifact_context"]["workspace_root"] == str(workspace)
        assert "续写" in payload["summary"]


def test_replace_workspace_text_replaces_inside_bounded_runtime_workspace():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        workspace.mkdir(parents=True)
        target = workspace / "notes" / "today.md"
        target.parent.mkdir(parents=True)
        target.write_text("hello old world", encoding="utf-8")
        env = {
            "AMADEUS_DATA_DIR": str(runtime_dir),
            "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        }
        with patch.dict(os.environ, env, clear=True):
            payload = replace_workspace_text.invoke(
                {
                    "relative_path": "notes/today.md",
                    "old_text": "old",
                    "new_text": "new",
                    "access_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": str(workspace),
                        "active_artifact_label": "lab-notes",
                    },
                }
            )

        assert target.read_text(encoding="utf-8") == "hello new world"
        assert payload["match_count"] == 1
        assert payload["replace_count"] == 1
        assert payload["artifact_context"]["artifact_kind"] == "file"
        assert payload["artifact_context"]["source_tool_name"] == "replace_workspace_text"
        assert payload["artifact_context"]["workspace_root"] == str(workspace)
        assert payload["access_hints"]["artifact_source_tool_name"] == "replace_workspace_text"


def test_replace_workspace_text_resolves_workspace_root_from_active_file_hint():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        workspace.mkdir(parents=True)
        target = workspace / "notes" / "today.md"
        target.parent.mkdir(parents=True)
        target.write_text("hello old world", encoding="utf-8")
        env = {
            "AMADEUS_DATA_DIR": str(runtime_dir),
            "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        }
        with patch.dict(os.environ, env, clear=True):
            payload = replace_workspace_text.invoke(
                {
                    "relative_path": "notes/today.md",
                    "old_text": "old",
                    "new_text": "new",
                    "access_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "file",
                        "active_artifact_ref": str(target),
                        "active_artifact_label": "today.md",
                    },
                }
            )

        assert target.read_text(encoding="utf-8") == "hello new world"
        assert payload["workspace_name"] == "lab-notes"
        assert payload["file_path"] == str(target)


def test_replace_workspace_text_rejects_missing_text():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        workspace.mkdir(parents=True)
        target = workspace / "notes" / "today.md"
        target.parent.mkdir(parents=True)
        target.write_text("hello world", encoding="utf-8")
        env = {
            "AMADEUS_DATA_DIR": str(runtime_dir),
            "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="TEXT_NOT_FOUND"):
                replace_workspace_text.invoke(
                    {
                        "relative_path": "notes/today.md",
                        "old_text": "missing",
                        "new_text": "new",
                        "access_hints": {
                            "filesystem_state": "writable",
                            "active_artifact_kind": "workspace",
                            "active_artifact_ref": str(workspace),
                            "active_artifact_label": "lab-notes",
                        },
                    }
                )


def test_replace_workspace_lines_replaces_requested_line_span_inside_workspace():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        workspace.mkdir(parents=True)
        target = workspace / "notes" / "today.md"
        target.parent.mkdir(parents=True)
        target.write_bytes("alpha\r\nbeta\r\ngamma\r\n".encode("utf-8"))
        env = {
            "AMADEUS_DATA_DIR": str(runtime_dir),
            "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        }
        with patch.dict(os.environ, env, clear=True):
            payload = replace_workspace_lines.invoke(
                {
                    "relative_path": "notes/today.md",
                    "start_line": 2,
                    "end_line": 2,
                    "new_text": "beta v2",
                    "access_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "workspace",
                        "active_artifact_ref": str(workspace),
                        "active_artifact_label": "lab-notes",
                    },
                }
            )

        assert target.read_text(encoding="utf-8") == "alpha\nbeta v2\ngamma\n"
        assert payload["start_line"] == 2
        assert payload["end_line"] == 2
        assert payload["replaced_line_count"] == 1
        assert payload["inserted_line_count"] == 1
        assert payload["artifact_context"]["source_tool_name"] == "replace_workspace_lines"
        assert payload["artifact_context"]["workspace_root"] == str(workspace)
        assert payload["access_hints"]["artifact_source_tool_name"] == "replace_workspace_lines"


def test_replace_workspace_lines_resolves_workspace_root_from_active_file_hint():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        workspace.mkdir(parents=True)
        target = workspace / "notes" / "today.md"
        target.parent.mkdir(parents=True)
        target.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")
        env = {
            "AMADEUS_DATA_DIR": str(runtime_dir),
            "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        }
        with patch.dict(os.environ, env, clear=True):
            payload = replace_workspace_lines.invoke(
                {
                    "relative_path": "notes/today.md",
                    "start_line": 2,
                    "end_line": 3,
                    "new_text": "line two\nline three",
                    "access_hints": {
                        "filesystem_state": "writable",
                        "active_artifact_kind": "file",
                        "active_artifact_ref": str(target),
                        "active_artifact_label": "today.md",
                    },
                }
            )

        assert target.read_text(encoding="utf-8") == "line 1\nline two\nline three\n"
        assert payload["workspace_name"] == "lab-notes"
        assert payload["file_path"] == str(target)


def test_replace_workspace_lines_rejects_out_of_range_span():
    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        workspace = runtime_dir / "workspaces" / "lab-notes"
        workspace.mkdir(parents=True)
        target = workspace / "notes" / "today.md"
        target.parent.mkdir(parents=True)
        target.write_text("line 1\nline 2\n", encoding="utf-8")
        env = {
            "AMADEUS_DATA_DIR": str(runtime_dir),
            "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="BAD_INPUT"):
                replace_workspace_lines.invoke(
                    {
                        "relative_path": "notes/today.md",
                        "start_line": 3,
                        "end_line": 4,
                        "new_text": "line 3",
                        "access_hints": {
                            "filesystem_state": "writable",
                            "active_artifact_kind": "workspace",
                            "active_artifact_ref": str(workspace),
                            "active_artifact_label": "lab-notes",
                        },
                    }
                )
