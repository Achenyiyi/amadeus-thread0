from __future__ import annotations

import os
import json
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_eval_import_bootstraps_project_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                'AMADEUS_MODEL_PROVIDER="qwen_native"',
                'AMADEUS_MODEL_NAME="qwen3.5-plus"',
                'AMADEUS_MODEL_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"',
            ]
        ),
        encoding="utf-8",
    )

    child_env = os.environ.copy()
    child_env["AMADEUS_ENV_FILE"] = str(env_file)
    for key in (
        "AMADEUS_MODEL_PROVIDER",
        "AMADEUS_MODEL_NAME",
        "AMADEUS_MODEL_BASE_URL",
        "AMADEUS_MODEL_API_KEY",
        "DEEPSEEK_API_KEY",
        "DASHSCOPE_API_KEY",
    ):
        child_env.pop(key, None)

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import evals.run_langsmith_evals as runner; "
                "from amadeus_thread0.runtime.modeling import runtime_model_summary; "
                "print(runtime_model_summary())"
            ),
        ],
        cwd=str(PROJECT_ROOT),
        env=child_env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "qwen_native:qwen3.5-plus" in proc.stdout.strip()


def test_memory_store_bootstrap_keeps_user_site_numpy_when_preferring_conda_torch() -> None:
    user_site = Path(sys.executable).resolve().parent.parent.parent / "Usersite-Does-Not-Exist"
    try:
        import site

        user_site = Path(site.getusersitepackages())
    except Exception:
        pass
    conda_site = Path(sys.executable).resolve().parent / "Lib" / "site-packages"

    if not (user_site / "numpy" / "__init__.py").exists():
        pytest.skip("user-site numpy not available in this environment")
    if not (user_site / "torch" / "__init__.py").exists():
        pytest.skip("user-site torch shadow build not available in this environment")
    if not (conda_site / "torch" / "__init__.py").exists():
        pytest.skip("conda torch not available in this environment")
    if not (conda_site / "numpy" / "__init__.py").exists():
        pytest.skip("conda numpy not available in this environment")

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json; "
                "import amadeus_thread0.memory_store; "
                "import numpy; "
                "print(json.dumps({'numpy_file': numpy.__file__, 'numpy_version': numpy.__version__}, ensure_ascii=False))"
            ),
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(proc.stdout.strip())
    assert str(user_site).lower() in str(payload["numpy_file"]).lower()
    assert str(payload["numpy_version"]) == "1.26.4"
