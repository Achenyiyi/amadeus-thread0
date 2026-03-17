from __future__ import annotations

import importlib
import unittest


class GraphFacadeTests(unittest.TestCase):
    def test_core_graph_entrypoints_remain_available(self) -> None:
        graph = importlib.import_module("amadeus_thread0.graph")

        self.assertTrue(callable(graph.build_graph))
        self.assertTrue(callable(graph.build_implicit_idle_state_update))
        self.assertTrue(callable(graph.reset_runtime_caches))
        self.assertTrue(callable(graph._default_persona_core))

    def test_legacy_helper_exports_resolve_via_compat_facade(self) -> None:
        graph = importlib.reload(importlib.import_module("amadeus_thread0.graph"))
        sample_targets = {
            "_generation_profile": "amadeus_thread0.graph_parts.generation_profile",
            "_memory_guard_check": "amadeus_thread0.graph_parts.tool_runtime",
            "_parse_set_profile_args": "amadeus_thread0.graph_parts.tooling",
            "_normalize_event_override": "amadeus_thread0.graph_parts.turn_events",
            "_compact_semantic_narrative_hint": "amadeus_thread0.graph_parts.semantic_narrative",
        }

        for name in sample_targets:
            graph.__dict__.pop(name, None)

        for name, module_name in sample_targets.items():
            with self.subTest(name=name):
                self.assertNotIn(name, graph.__dict__)
                value = getattr(graph, name)
                module = importlib.import_module(module_name)
                self.assertIs(value, getattr(module, name))
                self.assertIs(graph.__dict__[name], value)


if __name__ == "__main__":
    unittest.main()
