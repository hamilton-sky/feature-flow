"""feature-flow brainstorm-page <feature>: the brainstorm as a review page, for the user to read before they pick.

usage: feature-flow brainstorm-page <feature> [--style NAME] [--fragment] [--out FILE]
       feature-flow brainstorm-page <feature> --live DIR | --asks STATE | --answer STATE <n> <text> | --apply STATE <figure> <version> | --picks STATE
       feature-flow brainstorm-page <feature> --serve DIR [--port N] [--agent-label NAME] | --answer-graph STATE <n> <graph.json>
Reads plans/<feature>/brainstorm.md, or .feature-flow/state/brainstorm-<feature>.md before the plan exists, turns
it into a review document and has Forkboard (packages/forkboard/, found by feature_flow/pages/studio.py) make the page.
The page goes beside the brainstorm (same name, .html). The look is a Forkboard theme: --style, else the brainstorm's
`Style:` line, else FLOW_STYLE, else route. --fragment leaves out the doctype, html, head and body tags, for a host
that adds its own (an Artifact). --live writes DIR/index.html and DIR/state.json to publish as an artifact that
saves itself; --asks, --answer, --apply and --picks are the session's side of it, and --apply and --picks are the
only parts that write the brainstorm (--picks only its Type:, Scouts: and Helpers: lines): Forkboard never touches it.
The page is the guided flow's one page (feature_flow/pages/flow_page.py): Style, Team, Options, Plan and Build, as tabs.
"""

import os
import json
import importlib
import secrets
import re
import sys
from pathlib import Path

from feature_flow.pages import flow_page, studio
from feature_flow.plan import brainstorm_mode
from feature_flow.infra import git, plan_lock

USAGE = ("usage: feature-flow brainstorm-page <feature> [--style NAME] [--fragment] [--out FILE]\n"
         "       feature-flow brainstorm-page <feature> --live DIR | --asks STATE | --answer STATE <n> <text> | --apply STATE <figure> <version> | --picks STATE\n"
         "       feature-flow brainstorm-page <feature> --serve DIR [--port N] [--agent-label NAME] | --answer-graph STATE <n> <graph.json>")
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
    provider, agent_label, port = "claude", None, 0
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--fragment":
            fragment = True
        elif a in ("--live", "--serve", "--asks", "--picks") and i + 1 < len(argv) and tool is None and live is None:
            live, tool = argv[i + 1], a[2:]
            i += 1
        elif a in ("--answer", "--answer-graph") and i + 3 < len(argv) and tool is None:
            live, tool, extra = argv[i + 1], a[2:], argv[i + 2:i + 4]
            i += 3
        elif a == "--apply" and i + 3 < len(argv) and tool is None:
            live, tool, extra = argv[i + 1], "apply", argv[i + 2:i + 4]
            i += 3
        elif a in ("--provider", "--agent-label", "--port") and i + 1 < len(argv):
            if a == "--provider":
                provider = argv[i + 1]
            elif a == "--agent-label":
                agent_label = argv[i + 1]
            else:
                try:
                    port = int(argv[i + 1])
                except ValueError:
                    err.write("invalid port\n")
                    return 2
            i += 1
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
    plans = flow_page.folders(top, feature)
    if path is None and not any(plans) and tool not in ("asks", "answer", "answer-graph"):
        err.write("no brainstorm for %s and no plan found\n" % feature)
        return 1
    fb = studio.load()
    if fb is None:
        err.write(studio.MISSING)
        return 1
    importlib.import_module("forkboard.storage")
    importlib.import_module("forkboard.server")
    text = path.read_text(encoding="utf-8", errors="replace") if path else ""
    if tool in ("asks", "answer", "answer-graph", "apply", "picks"):
        if tool == "picks":
            try:
                # The plan lock is always acquired before the state lock in live_tool.
                # Re-evaluate both source and plan after acceptance/import/fix completes.
                with plan_lock.lock(top, feature):
                    current_path = source(top, feature)
                    current_text = current_path.read_text(encoding="utf-8", errors="replace") if current_path else ""
                    return live_tool(fb, tool, current_path, current_text, Path(live), extra, out, err,
                                     flow_page.folders(top, feature))
            except (OSError, ValueError) as e:
                err.write("%s\n" % e)
                return 1
        return live_tool(fb, tool, path, text, Path(live), extra, out, err, plans)
    if provider not in ("claude", "local"):
        err.write("provider must be claude or local\n")
        return 2
    if tool == "serve":
        provider = "local"
    names = fb.page.themes()
    _, meta, _, _ = parse(text)
    name = (style or meta.get("style") or os.environ.get("FLOW_STYLE") or DEFAULT_STYLE).strip().lower()
    if name not in names:
        err.write("no style %s: pick one of %s (Forkboard's themes)\n" % (name, ", ".join(names) or "none installed"))
        return 1
    css = fb.page.theme_css(name)

    def compose(old):
        current_path = source(top, feature)
        current_text = current_path.read_text(encoding="utf-8", errors="replace") if current_path else ""
        base = document(current_text, feature) if current_path else {
            "schema": studio.MAJOR, "id": feature, "kind": "Plan", "title": feature,
            "meta": {}, "intro": "", "sections": []}
        approved = set(fb.live.approved(old or {})) if tool in ("live", "serve") else None
        doc = flow_page.document(base, current_text, top=top, feature=feature, approved=approved)
        draft, plan = flow_page.folders(top, feature)
        if not current_path:
            for step in doc["steps"][:3]:
                step.update(state="done", summary="not used")
            doc["sections"] = [section for section in doc["sections"] if section.get("step") not in ("Style", "Team", "Options")]
            doc["sections"][:0] = [{"title": step, "kind": "text", "markdown": "Not used", "items": [], "step": step} for step in ("Style", "Team", "Options")]
        if plan:
            doc["frozen"] = True
            doc["phase"] = "complete" if doc["steps"][4]["state"] == "done" else "build"
        elif draft:
            doc["phase"] = "draft"
        else:
            doc["phase"] = "brainstorm"
        return doc

    def prepare_locked(old, force=False):
        folder = Path(live)
        folder.mkdir(parents=True, exist_ok=True)
        state_path = folder / "state.json"
        doc = compose(old)
        html = fb.page.render(doc, css, name, provider != "local", True, provider=provider, agent_label=agent_label)
        page_path = folder / "index.html"
        if not force and page_path.is_file() and not page_path.is_symlink() and page_path.read_text(encoding="utf-8") == html:
            return old, None
        st = fb.storage._validate(fb.live.state(doc, old))
        st["phase"] = doc["phase"]
        st.setdefault("identity", {"id": "local_" + secrets.token_hex(12), "label": "You"})
        data = fb.live.dump(st)
        if len(data.encode("utf-8")) > fb.storage.MAX_STATE:
            raise ValueError("page state exceeds the 8 MiB limit")
        return st, html

    def regenerate_locked(force=False):
        state_path = Path(live) / "state.json"
        old = fb.storage._read(state_path, missing=True)
        st, html = prepare_locked(old, force)
        if html is not None:
            fb.storage.publish(state_path, fb.live.dump(st), html)
        return st

    def regenerate(force=False):
        folder = Path(live)
        folder.mkdir(parents=True, exist_ok=True)
        with fb.storage.lock(folder / "state.json"):
            return regenerate_locked(force)

    try:
        if tool in ("live", "serve"):
            st = regenerate(force=True)
            out.write("wrote %s and %s (round %d, %d figures, %d open asks)\n" % (
                (Path(live) / "index.html").as_posix(), (Path(live) / "state.json").as_posix(), st["round"],
                len(st["figures"]), sum(1 for a in st["asks"] if not a.get("answer"))))
            if tool == "serve":
                fb.server.serve(live, port, out, refresh=regenerate, prepare=prepare_locked,
                                guard=lambda: plan_lock.lock(top, feature))
            return 0
        doc = compose(None)
        dest = Path(target) if target else path.with_suffix(".html") if path else (plans[1] or plans[0]) / "index.html"
        dest.write_text(fb.page.render(doc, css, name, fragment), encoding="utf-8")
        out.write("wrote %s\n" % dest.as_posix())
        return 0
    except (OSError, ValueError, brainstorm_mode.BadMode) as e:
        err.write("%s\n" % e)
        return 1


def live_tool(fb, tool, path, text, state_path, extra, out, err, plans=(None, None)):
    if state_path.is_dir():
        state_path = state_path / "state.json"
    try:
        st = fb.storage.read(state_path)
    except (OSError, ValueError) as e:
        err.write("%s\n" % e)
        return 1
    if st is None:
        err.write("no page state at %s: read the published page's state.json into it first (brainstorm guide)\n"
                  % state_path.as_posix())
        return 1
    try:
        if tool == "asks":
            out.write(fb.live.asks(st) + "\n")
        elif tool in ("answer", "answer-graph"):
            if not extra[0].isdigit():
                raise ValueError("the ask number must be a number, not %s" % extra[0])
            if tool == "answer-graph":
                with Path(extra[1]).open("rb") as stream:
                    raw = stream.read(fb.storage.MAX_BODY + 1)
                if len(raw) > fb.storage.MAX_BODY:
                    raise ValueError("graph proposal exceeds the 1 MiB limit")
                proposal = json.loads(raw, parse_constant=fb.storage._constant)
                fb.storage.transaction(state_path, lambda old: fb.live.answer_graph(old, int(extra[0]), proposal))
            else:
                fb.storage._text(extra[1], "answer text")
                fb.storage.transaction(state_path, lambda old: fb.live.answer(old, int(extra[0]), extra[1]))
            out.write("answered ask %s in %s\n" % (extra[0], state_path.as_posix()))
        elif tool == "picks":
            if not hasattr(fb.live, "picks"):
                raise ValueError("this Forkboard has no picks: reinstall feature-flow")
            picks = fb.live.picks(st)
            draft, plan = plans
            plan_picks = {k: v for k, v in picks.items() if flow_page.is_plan_key(k)}
            option = picks.get(flow_page.OPTION_KEY)
            setup_picks = {k: v for k, v in picks.items() if not flow_page.is_plan_key(k) and k != flow_page.OPTION_KEY}
            if not picks:
                out.write("no picks on the page: %s is as it was\n" % (path.as_posix() if path else "plan"))
                return 0
            if setup_picks and not (draft or plan):  # once the plan is drafted, Style and Team are done
                try:
                    new, lines = flow_page.apply_picks(text, setup_picks)
                except brainstorm_mode.BadMode as e:
                    raise ValueError(str(e))
                path.write_text(new, encoding="utf-8")
                out.write("wrote %s into %s\n" % (", ".join("%s: %s" % kv for kv in lines.items()), path.as_posix()))
            if option and not (draft or plan):
                out.write("the page picked option %s: write it as Chosen (brainstorm guide, Step 4)\n" % option)
            if plan_picks:
                if plan:
                    out.write("the plan is accepted, so the Plan step's picks are kept as approved: change its build "
                              "flow with a re-plan\n")
                    return 0
                if not draft:
                    raise ValueError("there is no draft plan yet for the Plan step's picks")
                from feature_flow.pages import flow_plan
                said = flow_plan.apply_picks(draft, plan_picks)
                out.write("wrote %s into the draft %s\n" % ("; ".join(said), draft.as_posix()))
        else:
            if path is None:
                raise ValueError("diagram apply unavailable: no brainstorm source")
            new, dropped = apply(text, fb, st, extra[0], extra[1])
            path.write_text(new, encoding="utf-8")
            if dropped:
                err.write("note: figure %s had %s, which the page does not keep; they are gone from the brainstorm now\n"
                          % (extra[0], ", ".join(dropped)))
            out.write("figure %s in %s is now version %s\n" % (extra[0], path.as_posix(), extra[1]))
    except (OSError, ValueError, TypeError, RecursionError) as e:
        err.write("%s\n" % e)
        return 1
    return 0
