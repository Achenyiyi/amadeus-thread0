from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import zipfile
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote
from urllib.parse import urlparse

import requests

from .dynamic_skill_candidates import freeze_skill_candidate_payload, verify_candidate_approval
from .settings import BASE_DIR, get_settings


class SkillRegistryError(RuntimeError):
    pass


class SkillSecurityError(SkillRegistryError):
    pass


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clean_text(value: Any, *, limit: int = 240) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _clean_id(value: Any, *, fallback: str = "") -> str:
    text = re.sub(r"[^a-z0-9._-]+", "-", str(value or "").strip().lower())
    text = re.sub(r"-{2,}", "-", text).strip("-.")
    return text or fallback


def _dedupe_lower_list(values: Any, *, limit: int = 24) -> list[str]:
    out: list[str] = []
    for item in _list_or_empty(values):
        text = _clean_text(item, limit=120).lower()
        if text and text not in out:
            out.append(text)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _parse_version(value: Any) -> tuple[int, ...]:
    text = _clean_text(value, limit=80)
    parts = re.findall(r"\d+", text)
    if not parts:
        return (0,)
    return tuple(int(part) for part in parts[:8])


def _sort_versions_desc(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda item: (_parse_version(item.get("version")), int(item.get("installed_at") or 0)),
        reverse=True,
    )


def _read_json(path: Path, *, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _frontmatter_split(text: str) -> tuple[dict[str, Any], str]:
    raw = str(text or "")
    if not raw.startswith("---"):
        return {}, raw
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, raw
    end_index = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_index = idx
            break
    if end_index <= 0:
        return {}, raw
    frontmatter = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).strip()
    return _parse_frontmatter_block(frontmatter), body


def _parse_scalar(raw: str) -> Any:
    text = str(raw or "").strip()
    if not text:
        return ""
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1]
    lower = text.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    if re.fullmatch(r"-?\d+", text):
        try:
            return int(text)
        except Exception:
            return text
    if re.fullmatch(r"-?\d+\.\d+", text):
        try:
            return float(text)
        except Exception:
            return text
    if text.startswith("[") or text.startswith("{"):
        try:
            return json.loads(text)
        except Exception:
            return text
    return text


def _parse_frontmatter_block(block: str) -> dict[str, Any]:
    lines = block.splitlines()
    out: dict[str, Any] = {}
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if not line.strip():
            idx += 1
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            idx += 1
            continue
        key = str(match.group(1)).strip()
        tail = str(match.group(2) or "").strip()
        if tail:
            out[key] = _parse_scalar(tail)
            idx += 1
            continue

        block_lines: list[str] = []
        idx += 1
        while idx < len(lines):
            probe = lines[idx]
            if re.match(r"^[A-Za-z0-9_-]+:\s*(.*)$", probe) and not probe.startswith((" ", "\t")):
                break
            block_lines.append(probe)
            idx += 1

        list_items: list[Any] = []
        nested_mapping: dict[str, Any] = {}
        scalar_lines: list[str] = []
        for raw_line in block_lines:
            stripped = raw_line.strip()
            if not stripped:
                continue
            if stripped.startswith("- "):
                list_items.append(_parse_scalar(stripped[2:].strip()))
                continue
            nested_match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", stripped)
            if nested_match:
                nested_mapping[str(nested_match.group(1)).strip()] = _parse_scalar(str(nested_match.group(2) or "").strip())
                continue
            scalar_lines.append(stripped)

        if list_items:
            out[key] = list_items
        elif nested_mapping:
            out[key] = nested_mapping
        else:
            out[key] = "\n".join(scalar_lines).strip()
    return out


def _excerpt_markdown(text: str, *, limit: int = 1800) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    compact = re.sub(r"\n{3,}", "\n\n", raw)
    return compact[:limit]


def _looks_like_windows_local_path(raw: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:[\\/]", str(raw or "").strip()))


def _local_path_from_urlish(raw: str) -> Path:
    text = str(raw or "").strip()
    if not text:
        raise SkillRegistryError("empty local path")
    if _looks_like_windows_local_path(text):
        return Path(text).expanduser()
    parsed = urlparse(text)
    if parsed.scheme == "file":
        joined = f"{parsed.netloc}{parsed.path}"
        local_text = unquote(joined)
        if re.match(r"^/[A-Za-z]:", local_text):
            local_text = local_text[1:]
        return Path(local_text).expanduser()
    return Path(text).expanduser()


def _read_skill_frontmatter(skill_md: Path) -> dict[str, Any]:
    try:
        with skill_md.open("r", encoding="utf-8") as handle:
            first = handle.readline()
            if first.strip() != "---":
                return {}
            lines: list[str] = []
            for raw_line in handle:
                if raw_line.strip() == "---":
                    break
                lines.append(raw_line.rstrip("\n"))
    except Exception:
        return {}
    return _parse_frontmatter_block("\n".join(lines))


def _list_relative_files(root: Path, subdir: str) -> list[str]:
    target = root / subdir
    if not target.exists() or not target.is_dir():
        return []
    out: list[str] = []
    for path in sorted(target.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        if rel not in out:
            out.append(rel)
        if len(out) >= 64:
            break
    return out


def _directory_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return ""
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        digest.update(rel.encode("utf-8", errors="ignore"))
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except Exception:
            continue
        digest.update(b"\0")
    return digest.hexdigest()


def _path_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except Exception:
        return False


def _ensure_directory_inside(root: Path, path: Path) -> None:
    resolved_root = root.resolve(strict=False)
    resolved_path = path.resolve(strict=False)
    if not _path_within_root(resolved_path, resolved_root):
        raise SkillSecurityError(f"path escapes skill root: {resolved_path}")


def _zip_member_is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (int(info.external_attr) >> 16) & 0o170000
    return mode == 0o120000


def _normalize_requested_permissions(value: Any) -> list[str]:
    return _dedupe_lower_list(value, limit=16)


def _normalize_skill_record(value: Any) -> dict[str, Any]:
    row = _dict_or_empty(value)
    if not row:
        return {}
    skill_id = _clean_id(row.get("skill_id") or row.get("id") or row.get("name"))
    if not skill_id:
        return {}
    source_value = row.get("source")
    source = ""
    source_detail: dict[str, Any] = {}
    if isinstance(source_value, dict):
        source_detail = {str(k): v for k, v in source_value.items() if str(k).strip()}
        source = _clean_text(source_detail.get("type") or source_detail.get("label") or source_detail.get("registry") or "remote", limit=120)
    else:
        source = _clean_text(source_value, limit=160)
    record = {
        "skill_id": skill_id,
        "name": _clean_text(row.get("name") or skill_id, limit=160),
        "description": _clean_text(row.get("description"), limit=400),
        "version": _clean_text(row.get("version") or "0.0.0", limit=80),
        "kind": _clean_text(row.get("kind") or "executable", limit=80).lower() or "executable",
        "source": source or "unknown",
        "source_detail": source_detail,
        "trust_tier": _clean_text(row.get("trust_tier") or "unverified", limit=80).lower() or "unverified",
        "status": _clean_text(row.get("status") or "available", limit=80).lower() or "available",
        "installed_path": _clean_text(row.get("installed_path"), limit=320),
        "required_surfaces": _dedupe_lower_list(row.get("required_surfaces"), limit=16),
        "allowed_tools": _dedupe_lower_list(row.get("allowed_tools"), limit=32),
        "sandbox_profiles": _dedupe_lower_list(row.get("sandbox_profiles"), limit=16),
        "requested_permissions": _normalize_requested_permissions(row.get("requested_permissions")),
        "triggers": _dedupe_lower_list(row.get("triggers"), limit=24),
        "hash": _clean_text(row.get("hash") or row.get("package_sha256"), limit=128).lower(),
        "verification_summary": _clean_text(row.get("verification_summary"), limit=320),
        "package_url": _clean_text(row.get("package_url") or source_detail.get("package_url"), limit=500),
        "catalog_url": _clean_text(row.get("catalog_url") or source_detail.get("catalog_url"), limit=500),
        "skill_md_path": _clean_text(row.get("skill_md_path"), limit=320),
        "scripts": [str(item).replace("\\", "/") for item in _list_or_empty(row.get("scripts")) if _clean_text(item, limit=320)][:64],
        "templates": [str(item).replace("\\", "/") for item in _list_or_empty(row.get("templates")) if _clean_text(item, limit=320)][:64],
        "assets": [str(item).replace("\\", "/") for item in _list_or_empty(row.get("assets")) if _clean_text(item, limit=320)][:64],
        "skill_excerpt": _excerpt_markdown(row.get("skill_excerpt") or row.get("body") or "", limit=1800),
        "installed_at": int(row.get("installed_at") or 0),
    }
    return record


class SkillRegistryManager:
    def __init__(
        self,
        *,
        base_dir: Path | None = None,
        data_dir: Path | None = None,
        registry_url: str | None = None,
        allow_insecure_remote: bool = False,
        allow_local_remote_source: bool = False,
    ) -> None:
        settings = get_settings()
        self.base_dir = Path(base_dir or BASE_DIR)
        self.data_dir = Path(data_dir or settings.data_dir)
        self.registry_url = str(registry_url or os.getenv("AMADEUS_SKILL_REGISTRY_URL", "")).strip()
        self.allow_insecure_remote = bool(allow_insecure_remote)
        self.allow_local_remote_source = bool(allow_local_remote_source)
        self.skills_root = self.data_dir / "skills"
        self.installed_root = self.skills_root / "installed"
        self.registry_path = self.skills_root / "registry.json"
        self.catalog_cache_dir = self.skills_root / "catalog-cache"
        self.catalog_cache_path = self.catalog_cache_dir / "official.json"
        self.sessions_root = self.skills_root / "sessions"
        self.local_authored_root = self.base_dir / "skills"

    def ensure_layout(self) -> None:
        self.installed_root.mkdir(parents=True, exist_ok=True)
        self.catalog_cache_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_root.mkdir(parents=True, exist_ok=True)

    def registry_snapshot(self) -> dict[str, Any]:
        self.ensure_layout()
        snapshot = _read_json(
            self.registry_path,
            default={"updated_at": 0, "catalog_version": "", "skills": []},
        )
        if not isinstance(snapshot, dict):
            snapshot = {"updated_at": 0, "catalog_version": "", "skills": []}
        skills = [_normalize_skill_record(item) for item in _list_or_empty(snapshot.get("skills"))]
        snapshot["skills"] = [item for item in skills if item]
        return snapshot

    def _write_registry_snapshot(self, snapshot: dict[str, Any]) -> None:
        payload = dict(snapshot or {})
        payload["updated_at"] = int(time.time())
        payload["skills"] = [_normalize_skill_record(item) for item in _list_or_empty(payload.get("skills")) if _normalize_skill_record(item)]
        _write_json(self.registry_path, payload)

    def session_state_path(self, thread_id: str) -> Path:
        thread_key = _clean_id(thread_id, fallback="thread")
        return self.sessions_root / f"{thread_key}.json"

    def session_state(self, thread_id: str) -> dict[str, Any]:
        self.ensure_layout()
        payload = _read_json(
            self.session_state_path(thread_id),
            default={
                "catalog_version": "",
                "manual_enabled": [],
                "manual_disabled": [],
                "pinned_skill_ids": [],
                "updated_at": 0,
            },
        )
        if not isinstance(payload, dict):
            payload = {}
        return {
            "catalog_version": _clean_text(payload.get("catalog_version"), limit=120),
            "manual_enabled": _dedupe_lower_list(payload.get("manual_enabled"), limit=64),
            "manual_disabled": _dedupe_lower_list(payload.get("manual_disabled"), limit=64),
            "pinned_skill_ids": _dedupe_lower_list(payload.get("pinned_skill_ids"), limit=64),
            "updated_at": int(payload.get("updated_at") or 0),
        }

    def _write_session_state(self, thread_id: str, payload: dict[str, Any]) -> None:
        self.ensure_layout()
        materialized = {
            "catalog_version": _clean_text(payload.get("catalog_version"), limit=120),
            "manual_enabled": _dedupe_lower_list(payload.get("manual_enabled"), limit=64),
            "manual_disabled": _dedupe_lower_list(payload.get("manual_disabled"), limit=64),
            "pinned_skill_ids": _dedupe_lower_list(payload.get("pinned_skill_ids"), limit=64),
            "updated_at": int(time.time()),
        }
        _write_json(self.session_state_path(thread_id), materialized)

    def discover_local_skills(self) -> list[dict[str, Any]]:
        if not self.local_authored_root.exists() or not self.local_authored_root.is_dir():
            return []
        out: list[dict[str, Any]] = []
        for skill_root in sorted(self.local_authored_root.iterdir()):
            if not skill_root.is_dir():
                continue
            if skill_root.is_symlink():
                continue
            try:
                package = self._load_skill_directory(skill_root, status="authored_local", source="local_authored")
            except SkillRegistryError:
                continue
            if package:
                out.append(package)
        return out

    def installed_skills(self) -> list[dict[str, Any]]:
        snapshot = self.registry_snapshot()
        return _sort_versions_desc([item for item in _list_or_empty(snapshot.get("skills")) if _normalize_skill_record(item)])

    def runtime_catalog(self) -> list[dict[str, Any]]:
        local = self.discover_local_skills()
        installed = self.installed_skills()
        by_key: dict[str, dict[str, Any]] = {}
        for item in [*installed, *local]:
            record = _normalize_skill_record(item)
            if not record:
                continue
            skill_id = str(record.get("skill_id") or "").strip()
            existing = by_key.get(skill_id)
            if existing is None:
                by_key[skill_id] = record
                continue
            existing_status = str(existing.get("status") or "")
            status = str(record.get("status") or "")
            if existing_status == "installed" and status == "authored_local":
                by_key[skill_id] = record
                continue
            if _parse_version(record.get("version")) >= _parse_version(existing.get("version")):
                by_key[skill_id] = record
        return sorted(by_key.values(), key=lambda item: (str(item.get("skill_id") or ""), _parse_version(item.get("version"))))

    def catalog_entries(self) -> list[dict[str, Any]]:
        local = self.discover_local_skills()
        installed = self.installed_skills()
        remote = self.remote_catalog()
        rows = [*local, *installed, *remote]
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        for item in rows:
            record = _normalize_skill_record(item)
            if not record:
                continue
            key = (str(record.get("skill_id") or ""), str(record.get("version") or ""))
            existing = merged.get(key)
            if existing is None:
                merged[key] = record
                continue
            if str(record.get("status") or "") in {"authored_local", "installed"}:
                merged[key] = record
        return _sort_versions_desc(list(merged.values()))

    def catalog_version(self) -> str:
        compact = [
            {
                "skill_id": item.get("skill_id"),
                "version": item.get("version"),
                "status": item.get("status"),
                "hash": item.get("hash"),
            }
            for item in self.catalog_entries()
        ]
        return _sha256_bytes(json.dumps(compact, sort_keys=True).encode("utf-8"))[:16]

    def search(self, query: str, *, limit: int = 8) -> dict[str, Any]:
        q = _clean_text(query, limit=240).lower()
        rows = self.catalog_entries()
        scored: list[tuple[float, dict[str, Any]]] = []
        for item in rows:
            score = self._skill_match_score(item, q, include_description=True)
            if q and score <= 0:
                continue
            if not q:
                score = 0.1
            scored.append((score, self._compact_entry(item)))
        scored.sort(key=lambda row: (row[0], _parse_version(row[1].get("version"))), reverse=True)
        return {
            "query": str(query or ""),
            "catalog_version": self.catalog_version(),
            "items": [item for _, item in scored[: max(1, min(int(limit or 8), 20))]],
        }

    def inspect(self, skill_id: str, *, version: str = "") -> dict[str, Any]:
        record = self._resolve_skill(skill_id=skill_id, version=version, include_remote=True)
        if not record:
            raise SkillRegistryError(f"unknown skill: {skill_id}")
        skill_excerpt = str(record.get("skill_excerpt") or "")
        skill_md_path = Path(str(record.get("skill_md_path") or "")).expanduser()
        if not skill_excerpt and skill_md_path.exists():
            try:
                _, body = _frontmatter_split(skill_md_path.read_text(encoding="utf-8"))
                skill_excerpt = _excerpt_markdown(body, limit=2400)
            except Exception:
                skill_excerpt = ""
        return {
            **self._compact_entry(record),
            "skill_excerpt": skill_excerpt,
            "scripts": list(record.get("scripts") or []),
            "templates": list(record.get("templates") or []),
            "assets": list(record.get("assets") or []),
            "requested_permissions": list(record.get("requested_permissions") or []),
            "verification_summary": str(record.get("verification_summary") or ""),
        }

    def preview_operation(
        self,
        *,
        operation: str,
        skill_id: str,
        version: str = "",
        thread_id: str = "",
    ) -> dict[str, Any]:
        op_name = _clean_id(operation, fallback="inspect")
        sid = _clean_id(skill_id)
        if not sid:
            raise SkillRegistryError("empty skill_id")
        if op_name in {"install", "update"}:
            resolved = self._resolve_remote_skill(skill_id=sid, version=version)
            if not resolved:
                raise SkillRegistryError(f"remote skill not found: {sid}")
            current = self._resolve_skill(skill_id=sid, version="", include_remote=False)
            if op_name == "install" and current and str(current.get("version") or "") == str(resolved.get("version") or ""):
                raise SkillRegistryError(f"skill already available: {sid}@{resolved.get('version')}")
            if op_name == "update" and current and _parse_version(resolved.get("version")) <= _parse_version(current.get("version")):
                raise SkillRegistryError(f"no newer version available for {sid}")
            return {
                "operation": op_name,
                "skill_id": sid,
                "resolved_version": str(resolved.get("version") or ""),
                "source": str(resolved.get("source") or ""),
                "hash": str(resolved.get("hash") or ""),
                "requested_permissions": list(resolved.get("requested_permissions") or []),
                "sandbox_profiles": list(resolved.get("sandbox_profiles") or []),
                "verification_summary": str(resolved.get("verification_summary") or ""),
                "package_url": str(resolved.get("package_url") or ""),
                "trust_tier": str(resolved.get("trust_tier") or ""),
            }
        resolved = self._resolve_skill(skill_id=sid, version=version, include_remote=False)
        if not resolved:
            raise SkillRegistryError(f"skill not installed or authored locally: {sid}")
        session = self.session_state(thread_id or get_settings().thread_id)
        return {
            "operation": op_name,
            "skill_id": sid,
            "resolved_version": str(resolved.get("version") or ""),
            "source": str(resolved.get("source") or ""),
            "hash": str(resolved.get("hash") or ""),
            "requested_permissions": list(resolved.get("requested_permissions") or []),
            "sandbox_profiles": list(resolved.get("sandbox_profiles") or []),
            "verification_summary": str(resolved.get("verification_summary") or ""),
            "manual_enabled": sid in set(session.get("manual_enabled") or []),
            "manual_disabled": sid in set(session.get("manual_disabled") or []),
            "pinned": sid in set(session.get("pinned_skill_ids") or []),
        }

    def install(
        self,
        *,
        skill_id: str,
        resolved_version: str = "",
        source: str = "",
        hash_value: str = "",
        requested_permissions: list[str] | None = None,
        sandbox_profiles: list[str] | None = None,
        verification_summary: str = "",
        operation: str = "install",
    ) -> dict[str, Any]:
        op_name = _clean_id(operation, fallback="install")
        if op_name not in {"install", "update"}:
            raise SkillRegistryError(f"unsupported skill operation: {operation}")
        preview = self.preview_operation(
            operation=op_name,
            skill_id=skill_id,
            version=resolved_version,
        )
        if resolved_version and str(preview.get("resolved_version") or "") != str(resolved_version):
            raise SkillRegistryError("resolved_version drift detected")
        if hash_value and str(preview.get("hash") or "").lower() != str(hash_value).lower():
            raise SkillRegistryError("hash drift detected")
        if source and str(preview.get("source") or "") != str(source):
            raise SkillRegistryError("source drift detected")
        if requested_permissions and _normalize_requested_permissions(requested_permissions) != _normalize_requested_permissions(preview.get("requested_permissions")):
            raise SkillRegistryError("requested_permissions drift detected")
        if sandbox_profiles and _dedupe_lower_list(sandbox_profiles) != _dedupe_lower_list(preview.get("sandbox_profiles")):
            raise SkillRegistryError("sandbox_profiles drift detected")
        if verification_summary and str(preview.get("verification_summary") or "") != str(verification_summary):
            raise SkillRegistryError("verification_summary drift detected")

        resolved = self._resolve_remote_skill(
            skill_id=_clean_id(skill_id),
            version=str(preview.get("resolved_version") or ""),
        )
        if not resolved:
            raise SkillRegistryError(f"remote skill not found: {skill_id}")
        package_url = str(resolved.get("package_url") or "").strip()
        if not package_url:
            raise SkillRegistryError(f"remote skill has no package_url: {skill_id}")

        self.ensure_layout()
        skill_key = _clean_id(skill_id)
        version_key = _clean_id(str(preview.get("resolved_version") or "0.0.0"), fallback="0.0.0")
        target_root = self.installed_root / skill_key / version_key
        if target_root.exists():
            shutil.rmtree(target_root)
        try:
            target_root.mkdir(parents=True, exist_ok=True)

            with tempfile.TemporaryDirectory(prefix=f"amadeus-skill-{skill_key}-", dir=str(self.skills_root)) as temp_dir_raw:
                temp_dir = Path(temp_dir_raw)
                archive_path = temp_dir / "package.zip"
                self._download_skill_archive(package_url, archive_path, expected_hash=str(preview.get("hash") or ""))
                extract_root = temp_dir / "extract"
                extract_root.mkdir(parents=True, exist_ok=True)
                self._safe_extract_zip(archive_path, extract_root)
                package_root = self._locate_package_root(extract_root)
                shutil.copytree(package_root, target_root, dirs_exist_ok=True)

            installed = self._load_skill_directory(
                target_root,
                status="installed",
                source=str(preview.get("source") or "registry"),
            )
            if str(installed.get("skill_id") or "") != skill_key:
                raise SkillRegistryError("installed package skill_id mismatch")
            installed["requested_permissions"] = list(preview.get("requested_permissions") or [])
            installed["sandbox_profiles"] = list(preview.get("sandbox_profiles") or [])
            installed["verification_summary"] = str(preview.get("verification_summary") or "")
            installed["hash"] = str(preview.get("hash") or installed.get("hash") or "")
            installed["installed_at"] = int(time.time())
            installed["status"] = "installed"
            installed["source"] = str(preview.get("source") or installed.get("source") or "registry")
            installed["package_url"] = package_url
            lock_payload = {
                "skill_id": installed.get("skill_id"),
                "version": installed.get("version"),
                "source": installed.get("source"),
                "hash": installed.get("hash"),
                "installed_at": installed.get("installed_at"),
                "verification_status": "verified",
                "requested_permissions": list(installed.get("requested_permissions") or []),
                "sandbox_profiles": list(installed.get("sandbox_profiles") or []),
                "verification_summary": str(installed.get("verification_summary") or ""),
                "package_url": package_url,
            }
            _write_json(target_root / "skill.lock.json", lock_payload)
            self._upsert_installed_registry_entry(installed)
            return self._compact_entry(installed)
        except Exception:
            shutil.rmtree(target_root, ignore_errors=True)
            raise

    def update(self, **kwargs: Any) -> dict[str, Any]:
        return self.install(operation="update", **kwargs)

    def install_candidate(
        self,
        candidate: dict[str, Any] | None,
        approval_payload: dict[str, Any] | None,
        *,
        thread_id: str = "",
        enable: bool = False,
    ) -> dict[str, Any]:
        frozen = freeze_skill_candidate_payload(candidate)
        verification = verify_candidate_approval(frozen, approval_payload)
        if not verification.get("verified", False):
            reasons = ",".join(str(item) for item in (verification.get("failure_reasons") or []) if str(item))
            raise SkillRegistryError(f"dynamic candidate approval drift detected: {reasons or 'unknown'}")
        skill_key = _clean_id(frozen.get("skill_id"))
        version_key = _clean_id(str(frozen.get("version") or "0.1.0"), fallback="0.1.0")
        draft_skill_md = str(frozen.get("draft_skill_md") or "").strip()
        if not skill_key:
            raise SkillRegistryError("empty dynamic candidate skill_id")
        if not draft_skill_md:
            raise SkillRegistryError("empty dynamic candidate SKILL.md")

        self.ensure_layout()
        target_root = self.installed_root / skill_key / version_key
        _ensure_directory_inside(self.installed_root, target_root)
        if target_root.exists():
            shutil.rmtree(target_root)
        try:
            target_root.mkdir(parents=True, exist_ok=True)
            (target_root / "SKILL.md").write_text(draft_skill_md + "\n", encoding="utf-8")

            installed = self._load_skill_directory(
                target_root,
                status="installed",
                source="dynamic_candidate",
            )
            if str(installed.get("skill_id") or "") != skill_key:
                raise SkillRegistryError("dynamic candidate skill_id mismatch")
            if str(installed.get("version") or "") != str(frozen.get("version") or ""):
                raise SkillRegistryError("dynamic candidate version mismatch")
            installed["requested_permissions"] = list(frozen.get("requested_permissions") or [])
            installed["sandbox_profiles"] = list(frozen.get("sandbox_profiles") or [])
            installed["verification_summary"] = str(frozen.get("verification_summary") or "")
            installed["hash"] = str(frozen.get("hash") or "")
            installed["installed_at"] = int(time.time())
            installed["status"] = "installed"
            installed["source"] = "dynamic_candidate"
            installed["trust_tier"] = "approved_candidate"
            installed["candidate_id"] = str(frozen.get("candidate_id") or "")
            installed["source_evidence_refs"] = list(frozen.get("source_evidence_refs") or [])
            lock_payload = {
                "skill_id": installed.get("skill_id"),
                "version": installed.get("version"),
                "source": installed.get("source"),
                "trust_tier": installed.get("trust_tier"),
                "hash": installed.get("hash"),
                "candidate_id": installed.get("candidate_id"),
                "source_evidence_refs": list(installed.get("source_evidence_refs") or []),
                "installed_at": installed.get("installed_at"),
                "verification_status": "verified",
                "requested_permissions": list(installed.get("requested_permissions") or []),
                "sandbox_profiles": list(installed.get("sandbox_profiles") or []),
                "verification_summary": str(installed.get("verification_summary") or ""),
            }
            _write_json(target_root / "skill.lock.json", lock_payload)
            self._upsert_installed_registry_entry(installed)
            result = self._compact_entry(installed)
            result["candidate_id"] = str(frozen.get("candidate_id") or "")
            result["source_evidence_refs"] = list(frozen.get("source_evidence_refs") or [])
            result["enabled"] = False
            if enable and str(thread_id or "").strip():
                result["session_state"] = self.enable(skill_id=skill_key, thread_id=str(thread_id or "").strip())
                result["enabled"] = True
            return result
        except Exception:
            shutil.rmtree(target_root, ignore_errors=True)
            raise

    def enable(self, *, skill_id: str, thread_id: str) -> dict[str, Any]:
        return self._update_session_override(thread_id=thread_id, skill_id=skill_id, enable=True)

    def disable(self, *, skill_id: str, thread_id: str) -> dict[str, Any]:
        return self._update_session_override(thread_id=thread_id, skill_id=skill_id, enable=False)

    def pin(self, *, skill_id: str, thread_id: str) -> dict[str, Any]:
        return self._update_session_override(thread_id=thread_id, skill_id=skill_id, enable=True, pin=True)

    def unpin(self, *, skill_id: str, thread_id: str) -> dict[str, Any]:
        return self._update_session_override(thread_id=thread_id, skill_id=skill_id, pin=False)

    def compute_session_skill_state(
        self,
        *,
        thread_id: str,
        query_text: str = "",
        current_event: dict[str, Any] | None = None,
        digital_body_state: dict[str, Any] | None = None,
        pending_skill_proposal: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session = self.session_state(thread_id)
        catalog = self.runtime_catalog()
        catalog_version = self.catalog_version()
        session["catalog_version"] = catalog_version
        available = {str(item.get("skill_id") or ""): item for item in catalog}
        manual_enabled = [sid for sid in _dedupe_lower_list(session.get("manual_enabled")) if sid in available]
        manual_disabled = [sid for sid in _dedupe_lower_list(session.get("manual_disabled")) if sid in available]
        pinned = [sid for sid in _dedupe_lower_list(session.get("pinned_skill_ids")) if sid in available and sid not in manual_disabled]
        matched = self._match_runtime_skills(
            catalog=catalog,
            query_text=query_text,
            current_event=current_event,
            digital_body_state=digital_body_state,
        )
        active_ids: list[str] = []
        for sid in [*pinned, *manual_enabled, *matched]:
            if sid in active_ids or sid in manual_disabled:
                continue
            if sid not in available:
                continue
            active_ids.append(sid)

        active_entries = [self._full_runtime_entry(available[sid]) for sid in active_ids if sid in available]
        matched_entries = [self._compact_entry(available[sid]) for sid in matched if sid in available]
        installed_entries = [self._compact_entry(item) for item in catalog]
        return {
            "catalog_version": catalog_version,
            "catalog_entries": installed_entries,
            "manual_enabled": manual_enabled,
            "manual_disabled": manual_disabled,
            "pinned_skill_ids": pinned,
            "matched_skill_ids": matched,
            "matched_skill_entries": matched_entries,
            "active_skill_ids": active_ids,
            "active_skill_entries": active_entries,
            "pending_skill_proposal": dict(pending_skill_proposal or {}) if isinstance(pending_skill_proposal, dict) else {},
            "manual_overrides": {
                "enabled": manual_enabled,
                "disabled": manual_disabled,
                "pinned": pinned,
            },
        }

    def list_runtime(
        self,
        *,
        thread_id: str,
        query_text: str = "",
        current_event: dict[str, Any] | None = None,
        digital_body_state: dict[str, Any] | None = None,
        pending_skill_proposal: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = self.compute_session_skill_state(
            thread_id=thread_id,
            query_text=query_text,
            current_event=current_event,
            digital_body_state=digital_body_state,
            pending_skill_proposal=pending_skill_proposal,
        )
        return {
            "catalog_version": str(state.get("catalog_version") or ""),
            "installed": list(state.get("catalog_entries") or []),
            "matched": list(state.get("matched_skill_entries") or []),
            "active": [self._compact_entry(item) | {"skill_excerpt": str(item.get("skill_excerpt") or "")} for item in _list_or_empty(state.get("active_skill_entries"))],
            "manual_overrides": dict(state.get("manual_overrides") or {}),
            "pending_approval": dict(state.get("pending_skill_proposal") or {}),
        }

    def remote_catalog(self) -> list[dict[str, Any]]:
        if not self.registry_url and self.catalog_cache_path.exists():
            cached = _read_json(self.catalog_cache_path, default={})
            return self._normalize_remote_catalog(cached)
        if not self.registry_url:
            return []
        parsed = urlparse(self.registry_url)
        if parsed.scheme == "https":
            raw = requests.get(self.registry_url, timeout=20)
            raw.raise_for_status()
            payload = raw.json()
            _write_json(self.catalog_cache_path, payload)
            return self._normalize_remote_catalog(payload)
        if self.allow_insecure_remote and parsed.scheme in {"http"}:
            raw = requests.get(self.registry_url, timeout=20)
            raw.raise_for_status()
            payload = raw.json()
            _write_json(self.catalog_cache_path, payload)
            return self._normalize_remote_catalog(payload)
        if self.allow_local_remote_source and (parsed.scheme == "file" or not parsed.scheme or _looks_like_windows_local_path(self.registry_url)):
            local_path = _local_path_from_urlish(self.registry_url)
            payload = _read_json(local_path, default={})
            _write_json(self.catalog_cache_path, payload)
            return self._normalize_remote_catalog(payload)
        raise SkillSecurityError("remote skill registry must use HTTPS")

    def _normalize_remote_catalog(self, payload: Any) -> list[dict[str, Any]]:
        raw_items = payload.get("skills") if isinstance(payload, dict) else payload
        if not isinstance(raw_items, list):
            return []
        out: list[dict[str, Any]] = []
        for item in raw_items:
            record = _normalize_skill_record({**_dict_or_empty(item), "status": "catalog_remote"})
            if record:
                out.append(record)
        return out

    def _resolve_skill(self, *, skill_id: str, version: str = "", include_remote: bool) -> dict[str, Any]:
        sid = _clean_id(skill_id)
        rows = self.catalog_entries() if include_remote else self.runtime_catalog()
        candidates = [item for item in rows if str(item.get("skill_id") or "") == sid]
        if version:
            candidates = [item for item in candidates if str(item.get("version") or "") == str(version)]
        if not candidates:
            return {}
        return _sort_versions_desc(candidates)[0]

    def _resolve_remote_skill(self, *, skill_id: str, version: str = "") -> dict[str, Any]:
        sid = _clean_id(skill_id)
        candidates = [item for item in self.remote_catalog() if str(item.get("skill_id") or "") == sid]
        if version:
            candidates = [item for item in candidates if str(item.get("version") or "") == str(version)]
        if not candidates:
            return {}
        return _sort_versions_desc(candidates)[0]

    def _update_session_override(
        self,
        *,
        thread_id: str,
        skill_id: str,
        enable: bool | None = None,
        pin: bool | None = None,
    ) -> dict[str, Any]:
        sid = _clean_id(skill_id)
        if not sid:
            raise SkillRegistryError("empty skill_id")
        if not self._resolve_skill(skill_id=sid, include_remote=False):
            raise SkillRegistryError(f"skill not installed or authored locally: {sid}")
        session = self.session_state(thread_id)
        enabled = set(session.get("manual_enabled") or [])
        disabled = set(session.get("manual_disabled") or [])
        pinned = set(session.get("pinned_skill_ids") or [])

        if enable is True:
            enabled.add(sid)
            disabled.discard(sid)
        elif enable is False:
            disabled.add(sid)
            enabled.discard(sid)
            pinned.discard(sid)

        if pin is True:
            pinned.add(sid)
            enabled.add(sid)
            disabled.discard(sid)
        elif pin is False:
            pinned.discard(sid)

        updated = {
            "catalog_version": self.catalog_version(),
            "manual_enabled": sorted(enabled),
            "manual_disabled": sorted(disabled),
            "pinned_skill_ids": sorted(pinned),
        }
        self._write_session_state(thread_id, updated)
        return self.list_runtime(thread_id=thread_id)

    def _skill_match_score(
        self,
        item: dict[str, Any],
        query_text: str,
        *,
        include_description: bool,
        surfaces: set[str] | None = None,
    ) -> float:
        if not query_text:
            return 0.0
        q = str(query_text or "").lower()
        score = 0.0
        skill_id = str(item.get("skill_id") or "")
        name = str(item.get("name") or "").lower()
        description = str(item.get("description") or "").lower()
        if skill_id and skill_id in q:
            score += 4.0
        if name and name in q:
            score += 3.0
        for trigger in _dedupe_lower_list(item.get("triggers"), limit=24):
            if trigger and trigger in q:
                score += 2.0
        if include_description:
            for token in [tok for tok in re.split(r"[^a-z0-9_/-]+", q) if len(tok) >= 4][:16]:
                if token in description:
                    score += 0.5
        if surfaces:
            overlap = surfaces.intersection(set(_dedupe_lower_list(item.get("required_surfaces"), limit=16)))
            score += float(len(overlap)) * 0.75
        return score

    def _match_runtime_skills(
        self,
        *,
        catalog: list[dict[str, Any]],
        query_text: str,
        current_event: dict[str, Any] | None,
        digital_body_state: dict[str, Any] | None,
    ) -> list[str]:
        event = _dict_or_empty(current_event)
        text_parts = [
            str(query_text or ""),
            str(event.get("text") or ""),
            str(event.get("effective_text") or ""),
            str(event.get("semantic_goal") or ""),
        ]
        perception = event.get("perception") if isinstance(event.get("perception"), dict) else {}
        text_parts.append(str(perception.get("channel") or ""))
        for tag in _list_or_empty(event.get("tags"))[:8]:
            text_parts.append(str(tag or ""))
        haystack = " ".join(part for part in text_parts if str(part or "").strip()).lower()
        surfaces = self._derive_surface_labels(digital_body_state)
        scored: list[tuple[float, str]] = []
        for item in catalog:
            score = self._skill_match_score(item, haystack, include_description=True, surfaces=surfaces)
            if score <= 0:
                continue
            scored.append((score, str(item.get("skill_id") or "")))
        scored.sort(key=lambda row: row[0], reverse=True)
        matched: list[str] = []
        for _, sid in scored:
            if sid and sid not in matched:
                matched.append(sid)
            if len(matched) >= 6:
                break
        return matched

    def _derive_surface_labels(self, digital_body_state: dict[str, Any] | None) -> set[str]:
        body = _dict_or_empty(digital_body_state)
        access = body.get("access_state") if isinstance(body.get("access_state"), dict) else {}
        resources = body.get("resource_state") if isinstance(body.get("resource_state"), dict) else {}
        labels = set(_dedupe_lower_list(body.get("world_surfaces"), limit=32))
        labels.update(_dedupe_lower_list(body.get("available_toolsets"), limit=32))
        labels.update(_dedupe_lower_list(body.get("active_tools"), limit=32))
        labels.update(_dedupe_lower_list(body.get("action_channels"), limit=32))
        labels.update(_dedupe_lower_list(body.get("perception_channels"), limit=32))
        labels.update(_dedupe_lower_list(access.get("granted_toolsets"), limit=32))
        for key in (
            "artifact_carrier",
            "active_artifact_kind",
            "filesystem_state",
            "network_access",
            "sandbox_mode",
        ):
            text = _clean_text((resources if key.startswith("artifact") else access).get(key), limit=80).lower()
            if text:
                labels.add(text)
        if str(resources.get("workspace_root") or "").strip():
            labels.add("filesystem")
            labels.add("workspace")
        if str(resources.get("artifact_carrier") or "").strip().lower() == "source_ref":
            labels.add("source_ref")
            labels.add("saved_material")
        return labels

    def _download_skill_archive(self, package_url: str, target_path: Path, *, expected_hash: str) -> None:
        parsed = urlparse(package_url)
        if parsed.scheme == "https":
            raw = requests.get(package_url, timeout=30)
            raw.raise_for_status()
            data = raw.content
        elif self.allow_insecure_remote and parsed.scheme == "http":
            raw = requests.get(package_url, timeout=30)
            raw.raise_for_status()
            data = raw.content
        elif self.allow_local_remote_source and (parsed.scheme == "file" or not parsed.scheme or _looks_like_windows_local_path(package_url)):
            source_path = _local_path_from_urlish(package_url)
            data = source_path.read_bytes()
        else:
            raise SkillSecurityError("skill package_url must use HTTPS")
        if expected_hash:
            digest = _sha256_bytes(data)
            if digest.lower() != str(expected_hash).lower():
                raise SkillSecurityError("skill package hash mismatch")
        target_path.write_bytes(data)

    def _safe_extract_zip(self, archive_path: Path, extract_root: Path) -> None:
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                if _zip_member_is_symlink(info):
                    raise SkillSecurityError(f"zip contains symlink: {info.filename}")
                normalized_name = str(info.filename or "").replace("\\", "/")
                if re.match(r"^[A-Za-z]:", normalized_name):
                    raise SkillSecurityError(f"zip contains drive-qualified path: {info.filename}")
                member_path = PurePosixPath(normalized_name)
                if member_path.is_absolute():
                    raise SkillSecurityError(f"zip contains absolute path: {info.filename}")
                if any(part in {"..", ""} for part in member_path.parts):
                    raise SkillSecurityError(f"zip contains unsafe member: {info.filename}")
                destination = extract_root / Path(*member_path.parts)
                _ensure_directory_inside(extract_root, destination)
                if info.is_dir():
                    continue
            archive.extractall(extract_root)

    def _locate_package_root(self, extract_root: Path) -> Path:
        direct = extract_root / "SKILL.md"
        if direct.exists():
            return extract_root
        child_dirs = [path for path in extract_root.iterdir() if path.is_dir()]
        if len(child_dirs) == 1 and (child_dirs[0] / "SKILL.md").exists():
            return child_dirs[0]
        raise SkillRegistryError("downloaded skill package does not contain SKILL.md")

    def _upsert_installed_registry_entry(self, record: dict[str, Any]) -> None:
        snapshot = self.registry_snapshot()
        existing = [item for item in _list_or_empty(snapshot.get("skills")) if str(item.get("skill_id") or "") != str(record.get("skill_id") or "")]
        existing.insert(0, _normalize_skill_record(record))
        snapshot["skills"] = existing[:200]
        compact = [
            {
                "skill_id": item.get("skill_id"),
                "version": item.get("version"),
                "status": item.get("status"),
                "hash": item.get("hash"),
            }
            for item in snapshot["skills"]
        ]
        snapshot["catalog_version"] = _sha256_bytes(json.dumps(compact, sort_keys=True).encode("utf-8"))[:16]
        self._write_registry_snapshot(snapshot)

    def _full_runtime_entry(self, item: dict[str, Any]) -> dict[str, Any]:
        record = _normalize_skill_record(item)
        if not record:
            return {}
        skill_md_path = Path(str(record.get("skill_md_path") or "")).expanduser()
        if skill_md_path.exists():
            try:
                _, body = _frontmatter_split(skill_md_path.read_text(encoding="utf-8"))
                record["skill_excerpt"] = _excerpt_markdown(body, limit=2200)
            except Exception:
                pass
        return record

    def _compact_entry(self, item: dict[str, Any]) -> dict[str, Any]:
        record = _normalize_skill_record(item)
        if not record:
            return {}
        return {
            "skill_id": str(record.get("skill_id") or ""),
            "name": str(record.get("name") or ""),
            "description": str(record.get("description") or ""),
            "version": str(record.get("version") or ""),
            "kind": str(record.get("kind") or ""),
            "source": str(record.get("source") or ""),
            "trust_tier": str(record.get("trust_tier") or ""),
            "installed_path": str(record.get("installed_path") or ""),
            "status": str(record.get("status") or ""),
            "required_surfaces": list(record.get("required_surfaces") or []),
            "allowed_tools": list(record.get("allowed_tools") or []),
            "sandbox_profiles": list(record.get("sandbox_profiles") or []),
            "hash": str(record.get("hash") or ""),
            "triggers": list(record.get("triggers") or []),
            "requested_permissions": list(record.get("requested_permissions") or []),
            "verification_summary": str(record.get("verification_summary") or ""),
        }

    def _load_skill_directory(self, skill_root: Path, *, status: str, source: str) -> dict[str, Any]:
        skill_root = skill_root.resolve(strict=False)
        skill_md = skill_root / "SKILL.md"
        if not skill_md.exists() or not skill_md.is_file():
            raise SkillRegistryError(f"missing SKILL.md: {skill_root}")
        if skill_md.is_symlink():
            raise SkillSecurityError(f"symlink SKILL.md rejected: {skill_md}")
        _ensure_directory_inside(skill_root, skill_md)
        frontmatter = _read_skill_frontmatter(skill_md)
        name = _clean_text(frontmatter.get("name") or skill_root.name, limit=160)
        description = _clean_text(frontmatter.get("description"), limit=400)
        version = _clean_text(frontmatter.get("version") or "0.0.0", limit=80)
        skill_id = _clean_id(frontmatter.get("skill_id") or skill_root.name, fallback=_clean_id(name, fallback=skill_root.name.lower()))
        requested_permissions = _normalize_requested_permissions(
            frontmatter.get("requested_permissions") or frontmatter.get("required_permissions")
        )
        source_value = frontmatter.get("source")
        normalized_source = _clean_text(source_value if not isinstance(source_value, dict) else source, limit=160) or source
        record = {
            "skill_id": skill_id,
            "name": name or skill_id,
            "description": description,
            "version": version,
            "kind": _clean_text(frontmatter.get("kind") or "executable", limit=80).lower() or "executable",
            "triggers": _dedupe_lower_list(frontmatter.get("triggers"), limit=24),
            "required_surfaces": _dedupe_lower_list(frontmatter.get("required_surfaces"), limit=16),
            "allowed_tools": _dedupe_lower_list(frontmatter.get("allowed_tools"), limit=32),
            "sandbox_profiles": _dedupe_lower_list(frontmatter.get("sandbox_profiles"), limit=16),
            "source": normalized_source,
            "trust_tier": _clean_text(frontmatter.get("trust_tier") or "authored", limit=80).lower() or "authored",
            "status": status,
            "installed_path": str(skill_root).replace("\\", "/"),
            "skill_md_path": str(skill_md).replace("\\", "/"),
            "scripts": _list_relative_files(skill_root, "scripts"),
            "templates": _list_relative_files(skill_root, "templates"),
            "assets": _list_relative_files(skill_root, "assets"),
            "requested_permissions": requested_permissions,
            "verification_summary": _clean_text(frontmatter.get("verification_summary"), limit=320),
            "hash": _directory_fingerprint(skill_root),
            "installed_at": int((skill_root / "skill.lock.json").stat().st_mtime if (skill_root / "skill.lock.json").exists() else 0),
        }
        return _normalize_skill_record(record)


@lru_cache(maxsize=1)
def get_skill_registry_manager() -> SkillRegistryManager:
    return SkillRegistryManager()


def reset_skill_registry_cache() -> None:
    get_skill_registry_manager.cache_clear()


__all__ = [
    "SkillRegistryError",
    "SkillRegistryManager",
    "SkillSecurityError",
    "get_skill_registry_manager",
    "reset_skill_registry_cache",
]
