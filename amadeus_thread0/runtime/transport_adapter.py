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

        envelope = handler(self.backend_api, request_body, request_query)
        return {"status": 200, "body": _envelope_to_body(envelope)}


def _error_response(status: int, code: str, **details: Any) -> dict[str, Any]:
    error = {"code": str(code or "ERROR").strip().upper()}
    error.update({key: value for key, value in details.items() if value not in (None, "")})
    return {"status": int(status), "body": {"error": error}}


def _read_route(method_name: str) -> Callable[[Any, dict[str, Any], dict[str, Any]], Any]:
    def handler(backend_api: Any, body: dict[str, Any], query: dict[str, Any]) -> Any:
        target = getattr(backend_api, method_name)
        if method_name in {"behavior_queue", "current_checkpoint"}:
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


_ROUTES: dict[str, tuple[str, Callable[[Any, dict[str, Any], dict[str, Any]], Any]]] = {
    "/api/thread-inventory": ("GET", _read_route("thread_inventory")),
    "/api/runtime-layout": ("GET", _read_route("runtime_layout")),
    "/api/environment-summary": ("GET", _read_route("environment_summary")),
    "/api/persona-view": ("GET", _read_route("persona")),
    "/api/worldline-view": ("GET", _read_route("worldline")),
    "/api/bond-view": ("GET", _read_route("bond")),
    "/api/sources-view": ("GET", _read_route("sources")),
    "/api/appraisal-view": ("GET", _read_route("appraisal")),
    "/api/behavior-queue": ("GET", _read_route("behavior_queue")),
    "/api/checkpoints/current": ("GET", _read_route("current_checkpoint")),
    "/api/checkpoints/history": ("GET", _read_route("checkpoint_history")),
    "/api/turns/finalize": ("POST", _turn_finalize),
    "/api/event-rounds/finalize": ("POST", _event_round_finalize),
}


__all__ = ["BackendTransportAdapter"]
