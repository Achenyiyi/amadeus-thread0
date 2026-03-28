from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from amadeus_thread0.utils.tools import create_workspace_access


def test_create_workspace_access_creates_bounded_runtime_workspace():
    proposal = {
        "target": "filesystem",
        "mode": "operator_create_workspace",
        "path_kind": "create_new",
        "summary": "先新建一个可写工作区。",
        "operator_action": "新建一个可写工作区。",
        "grants": ["filesystem", "workspace_write"],
        "requires_operator": True,
    }

    with TemporaryDirectory() as td:
        runtime_dir = Path(td) / "runtime"
        runtime_dir.mkdir()
        env = {
            "AMADEUS_DATA_DIR": str(runtime_dir),
            "AMADEUS_MODEL_PROVIDER": "openai_compatible",
        }
        with patch.dict(os.environ, env, clear=True):
            payload = create_workspace_access.invoke(
                {
                    "workspace_name": "Lab Notes",
                    "access_hints": {
                        "filesystem_state": "missing",
                        "missing_access": ["filesystem", "workspace_write"],
                        "requestable_access": ["filesystem", "workspace_write", "human_approval"],
                        "access_acquire_proposals": [proposal],
                        "selected_access_proposal": proposal,
                    },
                }
            )
            workspace_path = Path(payload["workspace_path"])
            assert workspace_path.exists()
            assert workspace_path.is_dir()
            assert workspace_path.parent.name == "workspaces"
            assert payload["workspace_name"] == workspace_path.name
            assert payload["created_new"] is True
            assert payload["access_hints"]["filesystem_state"] == "writable"
            assert payload["access_hints"]["active_artifact_kind"] == "workspace"
            assert "selected_access_proposal" not in payload["access_hints"]
            assert payload["access_state"]["filesystem_state"] == "writable"
            assert payload["resource_state"]["active_artifact_kind"] == "workspace"
            assert payload["artifact_context"]["artifact_kind"] == "workspace"
            assert payload["artifact_context"]["artifact_ref"] == str(workspace_path)
