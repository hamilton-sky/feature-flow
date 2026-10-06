import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import view  # the package under test, from this checkout

SCRIPTS = str(helpers.ROOT / "scripts")


class Out:
    def __init__(self):
        self.text = ""

    def write(self, text):
        self.text += text


def data_of(page_path):
    for line in Path(page_path).read_text(encoding="utf-8").splitlines():
        if line.startswith('<script id="flow-data"'):
            body = line[len('<script id="flow-data" type="application/json">'):-len("</script>")]
            return json.loads(body)
    raise AssertionError("no flow-data line")


class ExtrasTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "01-a.md")

    def tearDown(self):
        self.tmp.cleanup()

    def extras(self, data):
        with open(self.path, "wb") as handle:
            handle.write(data)
        return json.loads(view.extras(self.path) + "}")

    def test_done_when_keeps_eight_bullets_of_240_characters(self):
        bullets = "".join("- b%d\n" % i for i in range(10))
        got = self.extras(("# A\n\n## DONE WHEN\n\n- %s\n%s" % ("x" * 300, bullets)).encode())
        self.assertEqual(len(got["done_when"]), 8)
        self.assertEqual(got["done_when"][0], "x" * 240)
        self.assertEqual(got["done_when"][-1], "b6")

    def test_cuts_count_characters_not_bytes(self):
        # the awks disagree here (mawk counts bytes); the port counts characters, so a cut never splits one
        got = self.extras(("## Done when\n\n- %s\n\n## Answer\n\n%s\n" % ("\u00e9" * 300, "\u00e9" * 800)).encode())
        self.assertEqual(got["done_when"][0], "\u00e9" * 240)
        self.assertEqual(got["answer"], "\u00e9" * 700)

    def test_answer_joins_lines_and_skips_blank_and_tag_lines(self):
        got = self.extras(b"## Answer\n\nBuilt: x\n<!-- note -->\n \t\nProof: \"y\" \\ z\tw\x02\n")
        self.assertEqual(got["answer"], 'Built: x\nProof: "y" \\ z\tw')

    def test_a_line_of_carriage_returns_is_blank_like_mawk(self):
        # gawk and BSD awk count "\r" as a field; mawk does not. pinned to mawk, the Ubuntu default
        got = self.extras(b"## Answer\n\r\nBuilt\r\n\v\f\r\nProof\r\n")
        self.assertEqual(got["answer"], "Built\nProof")

    def test_answer_stops_growing_at_700_and_is_cut_there(self):
        got = self.extras(("## Answer\n\n%s\n%s\nlast\n" % ("a" * 699, "b" * 50)).encode())
        self.assertEqual(got["answer"], "a" * 699 + "\n")

    def test_the_template_placeholder_answer_is_empty(self):
        got = self.extras(b"## Answer\n\nleft empty until the ticket is done\n")
        self.assertEqual(got["answer"], "")

    def test_review_rounds(self):
        got = self.extras(b"## Review findings (round 3, gate)\n\nx\n## Review findings\n"
                          b"## review findings (round 12)\n## Review Findings (round 4, a, b) (c)\n")
        self.assertEqual(got["rounds"], [{"n": 3, "source": "gate"}, {"n": 0, "source": ""},
                                         {"n": 12, "source": ""}, {"n": 4, "source": "a, b"}])

    def test_an_empty_file(self):
        self.assertEqual(self.extras(b""), {"done_when": [], "answer": "", "rounds": []})


class ShowStatusTests(unittest.TestCase):
    def test_words(self):
        self.assertEqual(view.show_status(b"# A\nStatus: Done (by hand)\n"), b"resolved")
        self.assertEqual(view.show_status(b"Status:\twontfix\n"), b"parked")
        self.assertEqual(view.show_status(b"Status: claimed\n"), b"open")
        self.assertEqual(view.show_status(b"x\n" * 20 + b"Status: resolved\n"), b"")

    def test_a_carriage_return_makes_it_open_like_in_bash(self):
        self.assertEqual(view.show_status(b"Status: resolved\r\n"), b"open")


class PageTests(unittest.TestCase):
    def test_refresh_and_data_go_in_and_every_line_ends_in_a_newline(self):
        template = b"<head><!--__REFRESH__--></head>\n<s>__FLOW_DATA__</s> __FLOW_DATA__\nend"
        self.assertEqual(view.page(template, b"{1}\n", view.REFRESH),
                         b'<head><meta http-equiv="refresh" content="3"></head>\n<s>{1}</s> __FLOW_DATA__\nend\n')
        self.assertEqual(view.page(template, b"{1}", b""), b"<head></head>\n<s>{1}</s> __FLOW_DATA__\nend\n")
        self.assertEqual(view.page(b"", b"x", b""), b"")


class PauseTests(unittest.TestCase):
    def test_suffixes(self):
        with mock.patch.object(view.time, "sleep") as sleep:
            view.pause("1.5m", Out())
            view.pause(".2", Out())
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [90.0, 0.2])

    def test_a_bad_value_stops_like_sleep(self):
        err = Out()
        with self.assertRaises(view.Stop) as stop:
            view.pause("soon", err)
        self.assertEqual(stop.exception.code, 1)
        self.assertEqual(err.text, "sleep: invalid time interval 'soon'\nTry 'sleep --help' for more information.\n")


class RunTests(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.repo = helpers.Repo()
        os.chdir(str(self.repo.dir))
        self.env = mock.patch.dict(os.environ, {"FLOW_NO_OPEN": "1"})
        self.env.start()
        for key in ("FLOW_DIR", "FLOW_TICKETS", "FLOW_WATCH_SECONDS"):
            os.environ.pop(key, None)

    def tearDown(self):
        self.env.stop()
        os.chdir(self.cwd)
        self.repo.close()

    def run_view(self, *args, here=SCRIPTS):
        out, err = Out(), Out()
        with mock.patch.object(view.time, "gmtime", lambda real=time.gmtime: real(0)):
            code = view.run(list(args), out, err, here)
        return code, out.text, err.text

    def test_usage(self):
        usage = view.USAGE + "\n"
        for args in ((), ("",), ("f", "--bogus"), ("f", "--out"), ("f", "--out", "")):
            self.assertEqual(self.run_view(*args), (2, "", usage), args)

    def test_missing_folder_and_template(self):
        self.assertEqual(self.run_view("nope"), (2, "", "no ticket folder: plans/nope/tasks\n"))
        self.assertEqual(self.run_view("f", here="/nowhere"), (2, "", "missing /nowhere/flow-view.html\n"))

    def test_writes_the_page_into_git_with_history(self):
        self.repo.resolve("plans/f/tasks/01-a.md")
        code, out, err = self.run_view("f", "--no-open")
        page = os.path.join(self.repo.git("rev-parse", "--absolute-git-dir"), "flow-f.html")
        self.assertEqual((code, out, err), (0, "wrote %s\n" % page, ""))
        data = data_of(page)
        self.assertEqual(data["generated"], "1970-01-01T00:00:00Z")
        self.assertEqual([h["status"] for h in data["details"]["01"]["history"]], ["open", "resolved"])
        self.assertEqual(data["details"]["02"]["done_when"], ["x"])
        self.assertNotIn("cost", data["details"]["01"])  # the cost log went with the headless loop
        self.assertEqual(data["counts"]["resolved"], 1)
        self.assertNotIn("http-equiv", Path(page).read_text())
        self.assertEqual(self.repo.porcelain(), "")

    def test_angle_brackets_in_the_data_are_escaped(self):
        self.repo.set_status("plans/f/tasks/01-a.md", "open")
        Path("plans/f/tasks/01-a.md").write_text(helpers.ticket_text("</script><b>", "open", "—"))
        self.run_view("f", "--out", "o/p.html")
        text = Path("o/p.html").read_text()
        self.assertIn("\\u003c/script>\\u003cb>", text)
        self.assertNotIn("</script><b>", text)

    def test_status_failure_ends_the_run_with_its_code(self):
        Path("plans/e/tasks").mkdir(parents=True)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"TMPDIR": tmp}):
            tempfile.tempdir = None
            try:
                self.assertEqual(self.run_view("e", "--out", "x.html"), (2, "", "no tickets in plans/e/tasks\n"))
                self.assertEqual(len(os.listdir(tmp)), 1)  # the temp file is left behind, as mktemp's is in bash
            finally:
                tempfile.tempdir = None
        self.assertFalse(Path("x.html").exists())

    def test_outside_git_the_page_goes_to_tmpdir_without_history(self):
        with tempfile.TemporaryDirectory() as plan, tempfile.TemporaryDirectory() as tmp:
            os.chdir(plan)
            Path("plans/f/tasks").mkdir(parents=True)
            Path("plans/f/tasks/01-a.md").write_text(helpers.ticket_text("A", "open", "—"))
            with mock.patch.dict(os.environ, {"TMPDIR": tmp, "GIT_CEILING_DIRECTORIES": os.path.dirname(plan)}):
                code, out, _ = self.run_view("f", "--no-open")
            self.assertEqual((code, out), (0, "wrote %s/flow-f.html\n" % tmp))
            self.assertEqual(data_of(os.path.join(tmp, "flow-f.html"))["details"]["01"]["history"], [])
            os.chdir(str(self.repo.dir))

    def test_watching_a_finished_feature_ends_at_once(self):
        self.repo.resolve("plans/f/tasks/01-a.md")
        self.repo.resolve("plans/f/tasks/02-b.md")
        code, out, _ = self.run_view("f", "--watch", "--out", "w.html")
        self.assertEqual(code, 0)
        self.assertEqual(out, "wrote w.html\nwatching, press Ctrl-C to stop\nfeature complete, final page written\n")
        self.assertNotIn("http-equiv", Path("w.html").read_text())

    def test_watching_rewrites_with_a_refresh_until_complete(self):
        seen = []

        def sleep(seconds):
            seen.append((seconds, "http-equiv" in Path("w.html").read_text()))
            self.repo.resolve("plans/f/tasks/0%d-%s.md" % (len(seen), "ab"[len(seen) - 1]))

        os.environ["FLOW_WATCH_SECONDS"] = "0.5"
        with mock.patch.object(view.time, "sleep", sleep):
            code, out, _ = self.run_view("f", "--watch", "--out", "w.html")
        self.assertEqual(code, 0)
        self.assertEqual(seen, [(0.5, True), (0.5, True)])
        self.assertTrue(out.endswith("feature complete, final page written\n"))
        self.assertNotIn("http-equiv", Path("w.html").read_text())

    def test_an_existing_directory_as_out_gets_the_page_inside_like_mv(self):
        Path("d").mkdir()
        self.assertEqual(self.run_view("f", "--out", "d")[:2], (0, "wrote d\n"))
        self.assertTrue(Path("d/d.tmp").is_file())


class ScriptDirTests(unittest.TestCase):
    def test_relative_and_absolute(self):
        self.assertEqual(view.script_dir("/a/b/../c/x.py"), "/a/c")
        with mock.patch.dict(os.environ, {"PWD": os.getcwd()}):
            self.assertEqual(view.script_dir("x.py"), os.getcwd())


if __name__ == "__main__":
    unittest.main()
