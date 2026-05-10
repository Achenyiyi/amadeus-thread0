from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _envelope_to_body(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        payload = value.to_dict()
        return dict(payload) if isinstance(payload, dict) else {}
    return dict(value) if isinstance(value, dict) else {}


@dataclass
class BackendTransportAdapter:
    """Transport-neutral route adapter over the existing BackendAPI surface."""

    backend_api: Any

    def handle(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_method = str(method or "").strip().upper() or "GET"
        normalized_path = "/" + str(path or "").strip().strip("/")
        request_body = _dict_or_empty(body)
        request_query = _dict_or_empty(query)

        route = _ROUTES.get(normalized_path)
        if route is None:
            return _error_response(404, "ROUTE_NOT_FOUND", path=normalized_path)
        expected_method, handler = route
        if normalized_method != expected_method:
            return _error_response(
                405,
                "METHOD_NOT_ALLOWED",
                path=normalized_path,
                method=normalized_method,
                expected_method=expected_method,
            )

        response = handler(self.backend_api, request_body, request_query)
        if _is_transport_response(response):
            return response
        return {"status": 200, "body": _envelope_to_body(response)}


def _error_response(status: int, code: str, **details: Any) -> dict[str, Any]:
    error = {"code": str(code or "ERROR").strip().upper()}
    error.update({key: value for key, value in details.items() if value not in (None, "")})
    return {"status": int(status), "body": {"error": error}}


def _is_transport_response(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("body"), dict)
        and str(value.get("status") or "").strip().isdigit()
    )


def _read_route(method_name: str) -> Callable[[Any, dict[str, Any], dict[str, Any]], Any]:
    def handler(backend_api: Any, body: dict[str, Any], query: dict[str, Any]) -> Any:
        target = getattr(backend_api, method_name)
        if method_name in {"behavior_queue", "current_checkpoint", "current_turn"}:
            return target(config=query.get("config") if isinstance(query.get("config"), dict) else None)
        if method_name == "checkpoint_history":
            limit = query.get("limit", 10)
            try:
                parsed_limit = int(limit)
            except Exception:
                parsed_limit = 10
            return target(
                limit=max(1, min(parsed_limit, 100)),
                config=query.get("config") if isinstance(query.get("config"), dict) else None,
            )
        return target()

    return handler


def _turn_finalize(backend_api: Any, body: dict[str, Any], query: dict[str, Any]) -> Any:
    return backend_api.build_turn_response(
        state_values=body.get("state_values") if isinstance(body.get("state_values"), dict) else {},
        streamed_text=str(body.get("streamed_text") or ""),
        meta=body.get("meta") if isinstance(body.get("meta"), dict) else None,
    )


def _event_round_finalize(backend_api: Any, body: dict[str, Any], query: dict[str, Any]) -> Any:
    return backend_api.build_event_round_response(
        state_values=body.get("state_values") if isinstance(body.get("state_values"), dict) else {},
        final_text=str(body.get("final_text") or ""),
        meta=body.get("meta") if isinstance(body.get("meta"), dict) else None,
    )


def _chat_send(backend_api: Any, body: dict[str, Any], query: dict[str, Any]) -> Any:
    message = str(body.get("message") or "").strip()
    if not message:
        return _error_response(
            400,
            "INVALID_CHAT_MESSAGE",
            path="/api/chat/send",
            message="Chat message must be a non-empty string.",
        )
    return backend_api.send_chat(
        message=message,
        config=body.get("config") if isinstance(body.get("config"), dict) else None,
        meta=body.get("meta") if isinstance(body.get("meta"), dict) else None,
    )


def _body_route(method_name: str) -> Callable[[Any, dict[str, Any], dict[str, Any]], Any]:
    def handler(backend_api: Any, body: dict[str, Any], query: dict[str, Any]) -> Any:
        target = getattr(backend_api, method_name)
        return target(body=body)

    return handler


_ROUTES: dict[str, tuple[str, Callable[[Any, dict[str, Any], dict[str, Any]], Any]]] = {
    "/api/thread-inventory": ("GET", _read_route("thread_inventory")),
    "/api/runtime-layout": ("GET", _read_route("runtime_layout")),
    "/api/environment-summary": ("GET", _read_route("environment_summary")),
    "/api/runtime-productization": ("GET", _read_route("runtime_productization")),
    "/api/operator-console-rc": ("GET", _read_route("operator_console_rc")),
    "/api/persona-view": ("GET", _read_route("persona")),
    "/api/worldline-view": ("GET", _read_route("worldline")),
    "/api/bond-view": ("GET", _read_route("bond")),
    "/api/sources-view": ("GET", _read_route("sources")),
    "/api/appraisal-view": ("GET", _read_route("appraisal")),
    "/api/behavior-queue": ("GET", _read_route("behavior_queue")),
    "/api/checkpoints/current": ("GET", _read_route("current_checkpoint")),
    "/api/checkpoints/history": ("GET", _read_route("checkpoint_history")),
    "/api/turns/current": ("GET", _read_route("current_turn")),
    "/api/chat/send": ("POST", _chat_send),
    "/api/turns/finalize": ("POST", _turn_finalize),
    "/api/event-rounds/finalize": ("POST", _event_round_finalize),
    "/api/desktop/capabilities": ("GET", _read_route("desktop_capabilities")),
    "/api/desktop/permissions/request": ("POST", _body_route("request_desktop_permissions")),
    "/api/media/session/current": ("GET", _read_route("current_media_session")),
    "/api/media/session/start": ("POST", _body_route("start_media_session")),
    "/api/media/session/stop": ("POST", _body_route("stop_media_session")),
    "/api/media/audio/input": ("POST", _body_route("submit_media_audio")),
    "/api/media/video/frame": ("POST", _body_route("submit_media_video_frame")),
    "/api/media/tts/synthesize": ("POST", _body_route("synthesize_media_tts")),
    "/api/artifacts/submit": ("POST", _body_route("submit_artifact")),
}


__all__ = ["BackendTransportAdapter"]
