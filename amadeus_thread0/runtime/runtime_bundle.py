from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ..graph_parts import build_graph, reset_runtime_caches
from ..memory_store import MemoryStore
from ..utils.tools import reset_tool_runtime_caches
from .backend_session import BackendSession
from .memory_admin import MemoryAdminService
from .settings import get_settings
from .thread_runtime import ThreadSwitchPlan, activate_thread_runtime

if TYPE_CHECKING:
    from .backend_api import BackendAPI


@dataclass
class RuntimeBundle:
    settings: Any
    graph: Any
    memory_store: MemoryStore
    backend_session: BackendSession
    memory_admin: MemoryAdminService

    @classmethod
    def create(
        cls,
        *,
        thread_id: str,
        settings: Any | None = None,
        graph_factory: Callable[[], Any] = build_graph,
        memory_store_factory: Callable[[Any], MemoryStore] = MemoryStore,
        backend_session_factory: Callable[..., BackendSession] = BackendSession,
        memory_admin_factory: Callable[..., MemoryAdminService] = MemoryAdminService,
    ) -> RuntimeBundle:
        current_settings = settings or get_settings()
        graph = graph_factory()
        memory_store = memory_store_factory(current_settings.memory_db_path)
        backend_session = backend_session_factory(
            graph=graph,
            memory_store=memory_store,
            thread_id=thread_id,
            user_id=current_settings.user_id,
        )
        memory_admin = memory_admin_factory(memory_store=memory_store)
        return cls(
            settings=current_settings,
            graph=graph,
            memory_store=memory_store,
            backend_session=backend_session,
            memory_admin=memory_admin,
        )

    @property
    def thread_id(self) -> str:
        return str(self.backend_session.thread_id)

    def config(self) -> dict[str, Any]:
        return {
            "configurable": {
                "thread_id": self.thread_id,
                "user_id": self.settings.user_id,
            }
        }

    def backend_api(self, *, base_data_dir: Path, cwd: Path | None = None) -> BackendAPI:
        from .backend_api import BackendAPI

        return BackendAPI(runtime_bundle=self, base_data_dir=Path(base_data_dir), cwd=cwd)

    def close(self) -> None:
        try:
            self.memory_store.close()
        except Exception:
            pass

    def switch_thread(
        self,
        *,
        base_data_dir: Any,
        requested_thread_id: str,
        fallback_prefix: str = "thread",
        now_ts: int | None = None,
        suffix: str | None = None,
        settings_factory: Callable[[], Any] = get_settings,
        graph_factory: Callable[[], Any] = build_graph,
        memory_store_factory: Callable[[Any], MemoryStore] = MemoryStore,
        backend_session_factory: Callable[..., BackendSession] = BackendSession,
        memory_admin_factory: Callable[..., MemoryAdminService] = MemoryAdminService,
        reset_tool_runtime_caches_fn: Callable[[], None] = reset_tool_runtime_caches,
        reset_runtime_caches_fn: Callable[[], None] = reset_runtime_caches,
    ) -> ThreadSwitchPlan:
        switch_plan = activate_thread_runtime(
            base_data_dir,
            requested_thread_id,
            fallback_prefix=fallback_prefix,
            now_ts=now_ts,
            suffix=suffix,
        )
        self.close()
        reset_tool_runtime_caches_fn()
        reset_runtime_caches_fn()
        current_settings = settings_factory()
        graph = graph_factory()
        memory_store = memory_store_factory(current_settings.memory_db_path)
        backend_session = backend_session_factory(
            graph=graph,
            memory_store=memory_store,
            thread_id=switch_plan.thread_id,
            user_id=current_settings.user_id,
        )
        memory_admin = memory_admin_factory(memory_store=memory_store)
        self.settings = current_settings
        self.graph = graph
        self.memory_store = memory_store
        self.backend_session = backend_session
        self.memory_admin = memory_admin
        return switch_plan


__all__ = ["RuntimeBundle"]
