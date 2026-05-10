from __future__ import annotations

import io
import json
from typing import Any, Callable
from urllib.parse import parse_qs

from .transport_adapter import BackendTransportAdapter


HTTP_TRANSPORT_PHASE1_READINESS = "http_transport_thin_wrapper_phase1_ready"

HTTP_TRANSPORT_AUTHORITY_BOUNDARY = {
    "transport_role": "thin_wrapper",
    "backend_semantics_owner": False,
    "frontend_semantics_owner": False,
    "memory_write_authority": False,
    "persona_core_mutation_allowed": False,
    "live_capture_enabled": False,
    "multimodal_model_auto_call_enabled": False,
    "dynamic_skill_registry_auto_write_enabled": False,
    "external_executor_auto_enabled": False,
    "sse_or_websocket_streaming_enabled": False,
}

StartResponse = Callable[[str, list[tuple[str, str]]], None]
WsgiApp = Callable[[dict[str, Any], StartResponse], list[bytes]]


def _json_response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {"status": int(status), "body": body}


def _parse_json_body(environ: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    method = str(environ.get("REQUEST_METHOD") or "GET").upper()
    if method in {"GET", "HEAD"}:
        return {}, None
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except Exception:
        length = 0
    if length <= 0:
        return {}, None
    stream = environ.get("wsgi.input")
    raw = stream.read(length) if hasattr(stream, "read") else b""
    try:
        decoded = raw.decode("utf-8")
        payload = json.loads(decoded) if decoded.strip() else {}
    except Exception as exc:
        return None, {"error": {"code": "INVALID_JSON", "message": str(exc)}}
    if not isinstance(payload, dict):
        return None, {"error": {"code": "INVALID_JSON", "message": "JSON request body must be an object"}}
    return payload, None


def _parse_query(environ: dict[str, Any]) -> dict[str, Any]:
    raw_query = str(environ.get("QUERY_STRING") or "")
    parsed = parse_qs(raw_query, keep_blank_values=True)
    query: dict[str, Any] = {}
    for key, values in parsed.items():
        if not values:
            query[key] = ""
        elif len(values) == 1:
            query[key] = values[0]
        else:
            query[key] = list(values)
    return query


def _status_line(status: int) -> str:
    reason = {
        200: "OK",
        400: "Bad Request",
        404: "Not Found",
        405: "Method Not Allowed",
        500: "Internal Server Error",
    }.get(int(status), "OK")
    return f"{int(status)} {reason}"


def build_wsgi_app(transport_adapter: BackendTransportAdapter) -> WsgiApp:
    def app(environ: dict[str, Any], start_response: StartResponse) -> list[bytes]:
        body, body_error = _parse_json_body(environ)
        if body_error is not None:
            response = _json_response(400, body_error)
        else:
            try:
                response = transport_adapter.handle(
                    str(environ.get("REQUEST_METHOD") or "GET"),
                    str(environ.get("PATH_INFO") or "/"),
                    body=body,
                    query=_parse_query(environ),
                )
            except Exception as exc:
                response = _json_response(
                    500,
                    {
                        "error": {
                            "code": "BACKEND_RUNTIME_ERROR",
                            "message": str(exc),
                            "path": str(environ.get("PATH_INFO") or "/"),
                        }
                    },
                )
        status = int(response.get("status") or 500)
        response_body = response.get("body") if isinstance(response.get("body"), dict) else {}
        payload = json.dumps(response_body, ensure_ascii=False).encode("utf-8")
        start_response(
            _status_line(status),
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(payload))),
                ("X-Amadeus-Transport", "thin-wrapper"),
            ],
        )
        return [payload]

    return app


def create_http_transport_app(backend_api: Any) -> WsgiApp:
    return build_wsgi_app(BackendTransportAdapter(backend_api))


def call_wsgi_app(
    app: WsgiApp,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    raw_body: bytes | None = None,
    query_string: str = "",
) -> dict[str, Any]:
    encoded_body = raw_body
    if encoded_body is None:
        encoded_body = json.dumps(body or {}, ensure_ascii=False).encode("utf-8") if body is not None else b""
    captured: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status_line"] = status
        captured["headers"] = {key.lower(): value for key, value in headers}

    environ = {
        "REQUEST_METHOD": str(method or "GET").upper(),
        "PATH_INFO": "/" + str(path or "").strip().strip("/"),
        "QUERY_STRING": str(query_string or ""),
        "CONTENT_LENGTH": str(len(encoded_body)),
        "CONTENT_TYPE": "application/json",
        "wsgi.input": io.BytesIO(encoded_body),
    }
    chunks = app(environ, start_response)
    raw_response = b"".join(chunks)
    status_line = str(captured.get("status_line") or "500 Internal Server Error")
    status_code = int(status_line.split(" ", 1)[0])
    decoded = json.loads(raw_response.decode("utf-8")) if raw_response else {}
    return {
        "status": status_code,
        "status_line": status_line,
        "headers": dict(captured.get("headers") or {}),
        "body": decoded if isinstance(decoded, dict) else {},
    }


__all__ = [
    "HTTP_TRANSPORT_AUTHORITY_BOUNDARY",
    "HTTP_TRANSPORT_PHASE1_READINESS",
    "build_wsgi_app",
    "call_wsgi_app",
    "create_http_transport_app",
]
