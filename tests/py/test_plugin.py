import json
import re
import sys
import unittest

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import __version__  # the package under test, from this checkout

PLUGIN = helpers.ROOT / ".claude-plugin"


class PluginTests(unittest.TestCase):
    def load(self, name):
        return json.loads((PLUGIN / name).read_text(encoding="utf-8"))

    def test_the_plugin_manifest_names_the_package_version(self):
        manifest = self.load("plugin.json")
        self.assertEqual(manifest["name"], "feature-flow")
        self.assertEqual(manifest["version"], __version__)
        self.assertTrue(re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", manifest["name"]))

    def test_the_marketplace_lists_this_repo_as_the_plugin(self):
        market = self.load("marketplace.json")
        self.assertEqual(market["owner"]["name"], "hamilton-sky")
        self.assertEqual([(p["name"], p["source"]) for p in market["plugins"]], [("feature-flow", "./")])

    def test_the_default_folders_hold_what_the_skill_needs(self):
        root = helpers.ROOT
        for rel in ("skills/feature-flow/SKILL.md", "agents/ticket-builder.md", "agents/ticket-reviewer.md",
                    "scripts/flow.py", "scripts/flow-trust.py", "feature_flow/__init__.py", "guides/build.md"):
            self.assertTrue((root / rel).is_file(), rel)

    def test_the_skill_knows_the_plugin_folder_and_role_names(self):
        text = (helpers.ROOT / "skills" / "feature-flow" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/scripts/flow.py", text)
        self.assertIn("feature-flow:ticket-builder", text)


if __name__ == "__main__":
    unittest.main()
