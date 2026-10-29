"""feature-flow brainstorm-page <feature>: the brainstorm as a review page, for the user to read before they pick.

usage: feature-flow brainstorm-page <feature> [--style NAME] [--fragment] [--out FILE]
       feature-flow brainstorm-page <feature> --live DIR | --asks STATE | --answer STATE <n> <text> | --apply STATE <figure> <version>
Reads plans/<feature>/brainstorm.md, or .feature-flow/state/brainstorm-<feature>.md before the plan exists, turns
it into a review document and has Forkboard (packages/forkboard/, found by feature_flow/studio.py) make the page.
The page goes beside the brainstorm (same name, .html). The look is a Forkboard theme: --style, else the brainstorm's
`Style:` line, else FLOW_STYLE, else route. --fragment leaves out the doctype, html, head and body tags, for a host
that adds its own (an Artifact). --live writes DIR/index.html and DIR/state.json to publish as an artifact that
saves itself; --asks, --answer and --apply are the session's side of it, and --apply is the one part that writes
the brainstorm: Forkboard never touches it.
"""

import os
import re
import sys
from pathlib import Path

from feature_flow import git, studio

USAGE = ("usage: feature-flow brainstorm-page <feature> [--style NAME] [--fragment] [--out FILE]\n"
         "       feature-flow brainstorm-page <feature> --live DIR | --asks STATE | --answer STATE <n> <text> | --apply STATE <figure> <version>")
DEFAULT_STYLE = "route"
FENCE = re.compile(r"^```mermaid[ \t]*\n(.*?)^```[ \t]*$", re.S | re.M)
KINDS = {"chosen": "chosen", "rejected": "rejected", "open": "open", "risks for the planner": "callout"}


def source(top, feature):
    """The brainstorm to show: the committed one once the plan exists, else the one in the state folder."""
    for path in (Path(top) / os.environ.get("FLOW_DIR", "plans") / feature / "brainstorm.md",
                 Path(top) / ".feature-flow" / "state" / ("brainstorm-%s.md" % feature)):
        if path.is_file():
            return path
    return None


def parse(text):
    """(title, meta {key: value}, intro lines, [(heading, lines, [(subheading, lines)])])."""
    title, meta, intro, sections = "", {}, [], []
    for line in text.splitlines():
        if line.startswith("# ") and not title and not sections:
            title = line[2:].strip()
        elif line.startswith("## "):
            sections.append((line[3:].strip(), [], []))
        elif line.startswith("### ") and sections:
            sections[-1][2].append((line[4:].strip(), []))
        elif sections:
            (sections[-1][2][-1][1] if sections[-1][2] else sections[-1][1]).append(line)
        else:
            m = re.match(r"^([A-Z][A-Za-z ]{1,20}):\s*(.+)$", line)
            if m and not any(l.strip() for l in intro):
                meta[m.group(1).strip().lower()] = m.group(2).strip()
            else:
                intro.append(line)
    return title, meta, intro, sections


def document(text, feature):
    """The brainstorm as a Forkboard review document: which section is Chosen, Rejected or Open, and which option
    the Chosen line picks, are the brainstorm's own conventions (guides/brainstorm.md), so they are read here."""
    title, meta, intro, sections = parse(text)
    chosen = ""
    for heading, lines, subs in sections:
        if heading.lower() == "chosen":
            chosen = " ".join(l.strip() for l in lines if l.strip())[:200]
    out = []
    for heading, lines, subs in sections:
        items = []
        for sub, sub_lines in subs:
            letter = re.match(r"^([A-Z])[.)]\s", sub)
            items.append({"title": sub, "label": letter.group(1) if letter else "",
                          "chosen": bool(letter and re.match(r"^\W*%s\b" % letter.group(1), chosen)),
                          "markdown": "\n".join(sub_lines)})
        out.append({"title": heading, "kind": KINDS.get(heading.lower(), "text"), "markdown": "\n".join(lines),
                    "items": items})
    return {"schema": studio.MAJOR, "id": feature, "kind": "Brainstorm", "title": title, "meta": meta,
            "intro": "\n".join(intro), "sections": out}


def apply(text, fb, st, figure, version):
    """The brainstorm text with figure `figure` replaced by that version of it, and what the rewrite dropped."""
    graph, source_print = fb.live.version(st, figure, version)
    blocks = list(FENCE.finditer(text))
    if not str(figure).isdigit() or not 1 <= int(figure) <= len(blocks):
        raise ValueError("the brainstorm file has %d diagrams, so no figure %s: build the page again" % (len(blocks), figure))
    block = blocks[int(figure) - 1]
    if source_print and fb.graph.fingerprint(block.group(1)) != source_print:
        raise ValueError("figure %s in the brainstorm changed since the page was built: build the page again (--live), "
                         "publish it, and apply after the next save" % figure)
    return text[:block.start(1)] + fb.graph.mermaid(graph) + "\n" + text[block.end(1):], fb.graph.lost(block.group(1))


def main(argv, out=None, err=None):
    out = out or sys.stdout
    err = err or sys.stderr
    args, style, fragment, target, live, tool, extra = [], None, False, None, None, None, []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--fragment":
            fragment = True
        elif a in ("--live", "--asks") and i + 1 < len(argv) and tool is None and live is None:
            live, tool = argv[i + 1], a[2:]
            i += 1
        elif a == "--answer" and i + 3 < len(argv) and tool is None:
            live, tool, extra = argv[i + 1], "answer", argv[i + 2:i + 4]
            i += 3
        elif a == "--apply" and i + 3 < len(argv) and tool is None:
            live, tool, extra = argv[i + 1], "apply", argv[i + 2:i + 4]
            i += 3
        elif a in ("--style", "--out") and i + 1 < len(argv):
            if a == "--style":
                style = argv[i + 1]
            else:
                target = argv[i + 1]
            i += 1
        elif a.startswith("-"):
            err.write(USAGE + "\n")
            return 2
        else:
            args.append(a)
        i += 1
    if len(args) != 1 or any(c in args[0] for c in "/\\:"):
        err.write(USAGE + "\n")
        return 2
    feature = args[0]
    top = git.toplevel() or os.getcwd()
    path = source(top, feature)
    if path is None:
        err.write("no brainstorm for %s: write .feature-flow/state/brainstorm-%s.md first (brainstorm guide)\n"
                  % (feature, feature))
        return 1
    fb = studio.load()
    if fb is None:
        err.write(studio.MISSING)
        return 1
    text = path.read_text(encoding="utf-8", errors="replace")
    if tool in ("asks", "answer", "apply"):
        return live_tool(fb, tool, path, text, Path(live), extra, out, err)
    names = fb.page.themes()
    _, meta, _, _ = parse(text)
    name = (style or meta.get("style") or os.environ.get("FLOW_STYLE") or DEFAULT_STYLE).strip().lower()
    if name not in names:
        err.write("no style %s: pick one of %s (Forkboard's themes)\n" % (name, ", ".join(names) or "none installed"))
        return 1
    css = fb.page.theme_css(name)
    doc = document(text, feature)
    if tool == "live":  # the page and its state, to publish together as an artifact that saves itself
        folder = Path(live)
        folder.mkdir(parents=True, exist_ok=True)
        st = fb.live.state(doc, fb.live.load(folder / "state.json"))
        (folder / "index.html").write_text(fb.page.render(doc, css, name, True, True), encoding="utf-8")
        (folder / "state.json").write_text(fb.live.dump(st), encoding="utf-8")
        out.write("wrote %s and %s (round %d, %d figures, %d open asks)\n" % (
            (folder / "index.html").as_posix(), (folder / "state.json").as_posix(), st["round"], len(st["figures"]),
            sum(1 for a in st["asks"] if not a.get("answer"))))
        return 0
    dest = Path(target) if target else path.with_suffix(".html")
    dest.write_text(fb.page.render(doc, css, name, fragment), encoding="utf-8")
    out.write("wrote %s\n" % dest.as_posix())
    return 0


def live_tool(fb, tool, path, text, state_path, extra, out, err):
    if state_path.is_dir():
        state_path = state_path / "state.json"
    st = fb.live.load(state_path)
    if st is None:
        err.write("no page state at %s: read the published page's state.json into it first (brainstorm guide)\n"
                  % state_path.as_posix())
        return 1
    try:
        if tool == "asks":
            out.write(fb.live.asks(st) + "\n")
        elif tool == "answer":
            if not extra[0].isdigit():
                raise ValueError("the ask number must be a number, not %s" % extra[0])
            state_path.write_text(fb.live.dump(fb.live.answer(st, int(extra[0]), extra[1])), encoding="utf-8")
            out.write("answered ask %s in %s\n" % (extra[0], state_path.as_posix()))
        else:
            new, dropped = apply(text, fb, st, extra[0], extra[1])
            path.write_text(new, encoding="utf-8")
            if dropped:
                err.write("note: figure %s had %s, which the page does not keep; they are gone from the brainstorm now\n"
                          % (extra[0], ", ".join(dropped)))
            out.write("figure %s in %s is now version %s\n" % (extra[0], path.as_posix(), extra[1]))
    except ValueError as e:
        err.write("%s\n" % e)
        return 1
    return 0
