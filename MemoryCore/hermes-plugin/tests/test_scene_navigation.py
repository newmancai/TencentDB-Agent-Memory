"""Check progressive scene lookup through the real Hermes provider surface."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


def load_provider():
    # Only the host base class is stubbed. Load the actual provider/client code.
    agent = types.ModuleType("agent")
    base = types.ModuleType("agent.memory_provider")
    base.MemoryProvider = object
    source = Path(__file__).resolve().parents[1] / "memory/memory_tencentdb/__init__.py"
    spec = importlib.util.spec_from_file_location(
        "tdai_scene_navigation_test_provider", source,
        submodule_search_locations=[str(source.parent)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with patch.dict(sys.modules, {"agent": agent, "agent.memory_provider": base}):
        spec.loader.exec_module(module)
    return module.MemoryTencentdbProvider


Provider = load_provider()


class SceneNavigationTests(unittest.TestCase):
    def provider(self, entries):
        provider = Provider()
        provider._ensure_alive_for_request = lambda: True
        provider._team_id = "test-team"
        provider._agent_id = "test-agent"
        provider._user_id = "test-user"
        client = Mock()
        client._timeout = 1
        client.atomic_search.return_value = {"data": {"items": []}}
        client.core_read.return_value = {"data": {"content": ""}}
        client.scenario_ls.return_value = {"data": {"entries": entries}}
        provider._client = client
        return provider, client

    def test_summary_points_to_exact_on_demand_read(self):
        provider, client = self.provider([
            {"path": "部署-规则.md", "summary": "Release scope\n and rollback rules"},
        ])
        context = provider.prefetch("Review the release")
        self.assertIn('scene_id: "部署-规则.md"', context)
        self.assertIn("Summary: Release scope and rollback rules", context)
        self.assertIn("memory_tencentdb_read_scene", context)
        client.scenario_read.assert_not_called()
        client.scenario_read.return_value = {"data": {"content": "Full source policy"}}
        result = provider.handle_tool_call(
            "memory_tencentdb_read_scene", {"scene_id": "部署-规则.md"},
        )
        self.assertEqual(result, "Full source policy")
        client.scenario_read.assert_called_once_with(
            path="部署-规则.md", team_id="test-team", agent_id="test-agent", user_id="test-user",
        )

    def test_legacy_entry_needs_no_summary(self):
        provider, _ = self.provider([{"path": "legacy.md"}])
        context = provider.prefetch("legacy policy")
        self.assertIn('scene_id: "legacy.md"', context)
        self.assertNotIn("Summary:", context)

    def test_directory_is_not_advertised_as_readable_scene(self):
        provider, _ = self.provider([
            {"path": "nested/", "summary": "directory"}, {"path": "policy.md"},
        ])
        context = provider.prefetch("policy")
        self.assertNotIn('scene_id: "nested/"', context)
        self.assertIn('scene_id: "policy.md"', context)


if __name__ == "__main__":
    unittest.main()
