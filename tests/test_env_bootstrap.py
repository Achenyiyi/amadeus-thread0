from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


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
