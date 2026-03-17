from __future__ import annotations

import os
from pathlib import Path


def project_env_path() -> Path:
    explicit = str(os.getenv("AMADEUS_ENV_FILE", "") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return Path(__file__).resolve().parents[1] / ".env"


def load_project_dotenv(*, override: bool = False) -> Path | None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return None

    path = project_env_path()
    if not path.exists():
        return None
    load_dotenv(dotenv_path=path, override=override)
    return path
