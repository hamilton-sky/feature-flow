"""Where code lives in feature_flow/, and which way imports may point (CONTRIBUTING.md, "Where code lives").

The layers, top to bottom: entry (command, cli, __main__) > commands > pages > conductor > verify > plan > infra.
A module may import its own layer or any layer below it, never one above; infra imports only infra. A module's
layer is its folder (feature_flow/plan/x.py is plan); a module still at the top of the package has its layer in
FLAT, the folder it is going to. UPWARD lists the upward imports that are allowed today, and the test fails when
one of them is gone, so the list only shrinks. Every import counts, including one inside a function.

It also checks that there is no import cycle between modules at module level, that every package folder is listed
in pyproject.toml, that every module parses as Python 3.9, that no module grows past its line limit, and that the
scripts in scripts/ start the package with the same bootstrap lines.
"""

import ast
import re
import unittest

from helpers import ROOT

PACKAGE = ROOT / "feature_flow"
ORDER = ("infra", "plan", "verify", "conductor", "pages", "commands", "entry")
RANK = {name: rank for rank, name in enumerate(ORDER)}
ENTRY = {"__init__", "__main__", "command", "cli"}

# modules still at the top of feature_flow/, by the folder they move to
FLAT = {
    "lanes": "conductor", "scouts": "conductor", "prompts": "conductor", "codeintel": "conductor",
    "codehash": "conductor",
    "view": "pages", "flow_page": "pages", "flow_plan": "pages", "brainstorm_page": "pages", "studio": "pages",
    "doctor": "commands", "report": "commands", "evaluate": "commands", "importer": "commands",
    "fixer": "commands", "clean": "commands", "install": "commands", "uninstall": "commands",
    "released": "commands", "config": "commands",
}

# the upward imports allowed today, (importer, imported); each move empties some of them
UPWARD = {
    ("feature_flow.plan.status", "feature_flow.lanes"),  # --width, lazily
}

# modules allowed to import each other at module level: the build, review and ask phases hand a ticket to
# one another
CYCLES = {
    frozenset({"feature_flow.conductor.phases.ask", "feature_flow.conductor.phases.build",
               "feature_flow.conductor.phases.review"}),
}

LIMIT = 700  # lines, for a module outside the conductor (the conductor keeps its own, tighter limits)


def modules():
    """{dotted name: path} for every module under feature_flow/."""
    out = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        parts = list(path.relative_to(ROOT).with_suffix("").parts)
        if parts[-1] == "__init__" and len(parts) > 2:
            parts.pop()
        out[".".join(parts)] = path
    return out


def layer(name):
    parts = name.split(".")[1:]
    if not parts or parts == ["__init__"]:
        return "entry"
    if len(parts) > 1 or parts[0] in RANK:
        return parts[0]
    if parts[0] in ENTRY:
        return "entry"
    return FLAT.get(parts[0])


def imports(name, path, known, top_only=False):
    """The feature_flow modules that name imports; top_only keeps only the imports run when it is loaded."""
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    nodes = tree.body if top_only else list(ast.walk(tree))
    if top_only:  # also imports under a module-level if/try
        nodes = [n for top in tree.body if not isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                                ast.ClassDef))
                 for n in ast.walk(top)]
    out = set()
    for node in nodes:
        if isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[:len(base) - node.level + 1]
                base = ".".join(base + ([node.module] if node.module else []))
            else:
                base = node.module or ""
            subs = ["%s.%s" % (base, alias.name) for alias in node.names]
            targets = [t for t in subs if t in known] or [base]  # `from pkg import mod` imports mod, not pkg
        else:
            continue
        for target in targets:
            while target and target not in known:
                target = target.rpartition(".")[0]
            if target and target != name and target != "feature_flow":
                out.add(target)
    return out


def listed_packages():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"(?ms)^packages = \[(.*?)\]", text)
    return set(re.findall(r'"([^"]+)"', block.group(1))) if block else set()


class Layout(unittest.TestCase):
    def setUp(self):
        self.modules = modules()

    def test_every_module_has_a_layer(self):
        missing = sorted(name for name in self.modules if layer(name) not in RANK)
        self.assertEqual(missing, [], "add these to FLAT in tests/py/test_layout.py, or move them into a layer "
                                      "folder: %s" % missing)

    def test_no_import_points_up_a_layer(self):
        up = set()
        for name, path in self.modules.items():
            for target in imports(name, path, self.modules):
                if RANK.get(layer(target), -1) > RANK.get(layer(name), -1):
                    up.add((name, target))
        self.assertEqual(sorted(up - UPWARD), [], "these imports point up a layer (see the docstring)")
        self.assertEqual(sorted(UPWARD - up), [], "these are gone: take them out of UPWARD")

    def test_no_import_cycle_at_module_level(self):
        graph = {name: imports(name, path, self.modules, top_only=True) for name, path in self.modules.items()}
        index, low, stack, on, found = {}, {}, [], set(), set()

        def strong(node):  # Tarjan's strongly connected components
            index[node] = low[node] = len(index)
            stack.append(node)
            on.add(node)
            for nxt in sorted(graph.get(node, ())):
                if nxt not in index:
                    strong(nxt)
                    low[node] = min(low[node], low[nxt])
                elif nxt in on:
                    low[node] = min(low[node], index[nxt])
            if low[node] == index[node]:
                group = []
                while True:
                    top = stack.pop()
                    on.discard(top)
                    group.append(top)
                    if top == node:
                        break
                if len(group) > 1:
                    found.add(frozenset(group))

        for node in sorted(graph):
            if node not in index:
                strong(node)
        self.assertEqual(sorted(map(sorted, found - CYCLES)), [], "modules that import each other at module level")
        self.assertEqual(sorted(map(sorted, CYCLES - found)), [], "these cycles are gone: take them out of CYCLES")

    def test_every_package_folder_is_listed_in_pyproject(self):
        names = {".".join(p.parent.relative_to(ROOT).parts) for p in PACKAGE.rglob("__init__.py")
                 if "__pycache__" not in p.parts}
        self.assertEqual(sorted(names - listed_packages()), [], "pyproject.toml's packages misses these")

    def test_every_module_parses_as_python_3_9(self):
        for name, path in self.modules.items():
            with self.subTest(module=name):
                ast.parse(path.read_text(encoding="utf-8"), str(path), feature_version=(3, 9))

    def test_no_module_outside_the_conductor_grows_past_the_limit(self):
        for name, path in self.modules.items():
            if layer(name) == "conductor" and name.startswith("feature_flow.conductor"):
                continue  # test_conductor_package.py keeps the conductor's own limits
            with self.subTest(module=name):
                lines = len(path.read_text(encoding="utf-8").splitlines())
                self.assertLess(lines, LIMIT, "%s has %d lines, the limit is under %d" % (name, lines, LIMIT))

    def test_the_scripts_share_one_bootstrap(self):
        def bootstrap(path):
            lines = path.read_text(encoding="utf-8").splitlines()
            start = lines.index("import sys")
            end = next(i for i, line in enumerate(lines) if "exec_module" in line)
            return lines[start:end + 1]

        scripts = sorted(p for p in (ROOT / "scripts").glob("*.py") if p.name != "flow-trust.py")
        self.assertGreaterEqual(len(scripts), 5)
        first = bootstrap(scripts[0])
        for path in scripts[1:]:
            with self.subTest(script=path.name):
                self.assertEqual(bootstrap(path), first, "%s's bootstrap differs from %s's"
                                 % (path.name, scripts[0].name))


if __name__ == "__main__":
    unittest.main()
