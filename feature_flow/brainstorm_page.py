"""feature-flow brainstorm-page <feature>: the brainstorm as a review page, for the user to read before they pick.

usage: feature-flow brainstorm-page <feature> [--style NAME] [--fragment] [--out FILE]
Reads plans/<feature>/brainstorm.md, or .feature-flow/state/brainstorm-<feature>.md before the plan exists, and
writes a self contained HTML page beside it (same name, .html): a sidebar that routes between the sections, a
light, dark or system theme switch, flowchart diagrams whose boxes can be dragged (and copied back as mermaid),
and an animation of the arrows, off until the reader turns it on. The look comes from a style, a file of colour
and font tokens in guides/styles/: --style, else the brainstorm's `Style:` line, else FLOW_STYLE, else route.
--fragment leaves out the doctype, html, head and body tags, for a host that adds its own (an Artifact).
Nothing is sent anywhere; the page loads its fonts from Google Fonts, and mermaid from jsDelivr only for a
diagram that is not a flowchart.
"""

import html
import json
import os
import re
import sys
from pathlib import Path

from feature_flow import git

USAGE = "usage: feature-flow brainstorm-page <feature> [--style NAME] [--fragment] [--out FILE]"
DEFAULT_STYLE = "route"
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"
FONT_LINE = re.compile(r"/\*\s*fonts:\s*(https://fonts\.googleapis\.com/\S+)\s*\*/")
SHAPES = (("([", "])", "stadium"), ("[(", ")]", "cylinder"), ("((", "))", "circle"), ("{{", "}}", "hexagon"),
          ("[/", "/]", "rect"), ("[\\", "\\]", "rect"), ("[", "]", "rect"), ("(", ")", "round"), ("{", "}", "diamond"),
          (">", "]", "rect"))
NODE = re.compile(r'\s*([A-Za-z0-9_][\w-]*)\s*(\(\[.*?\]\)|\[\(.*?\)\]|\(\(.*?\)\)|\{\{.*?\}\}|\[/.*?/\]|\[\\.*?\\\]'
                  r'|\[.*?\]|\(.*?\)|\{.*?\}|>.*?\])?\s*')
LINK = re.compile(r'\s*(-->|---|-\.->|-\.-|==>|===|--o|--x|<-->)\s*(?:\|([^|]*)\|)?\s*')
BOXES = (  # what the Add box menu offers: shape, name, what it usually means, icon
    ("rect", "Box", "a step, a part or a service", '<rect x="2" y="3" width="20" height="12" rx="2"/>'),
    ("round", "Rounded box", "a screen or a softer step", '<rect x="2" y="3" width="20" height="12" rx="5"/>'),
    ("stadium", "Pill", "a person, or where it starts or ends", '<rect x="2" y="3" width="20" height="12" rx="6"/>'),
    ("diamond", "Decision", "a yes or no question", '<path d="M12 1L22 9L12 17L2 9Z"/>'),
    ("cylinder", "Database", "data that is stored", '<path d="M3 4v10c0 2 18 2 18 0V4"/><ellipse cx="12" cy="4" rx="9" ry="2"/>'),
    ("hexagon", "Hexagon", "a job or a preparation step", '<path d="M6 3h12l4 6l-4 6H6L2 9Z"/>'),
    ("circle", "Circle", "an event or a signal", '<circle cx="12" cy="9" r="7"/>'),
)
COLOURS = (  # the colours a box can take: name, hue (outline, and the tint of the fill), light fill for mermaid
    ("teal", "#0e7268", "#dcefec"), ("green", "#2f8a3e", "#e1f1e3"), ("olive", "#7a8a1c", "#eef1d9"),
    ("sky", "#0f86b8", "#ddf0f8"), ("blue", "#2f6fdb", "#e0eafb"), ("indigo", "#4a52c9", "#e4e5f8"),
    ("purple", "#7c4fe0", "#ece5fb"), ("pink", "#c23d72", "#f8e1ea"), ("red", "#c8402f", "#f9e2df"),
    ("orange", "#d0661a", "#fbe8da"), ("amber", "#b58100", "#f7eed6"), ("grey", "#6b7785", "#eceef1"),
)


def dots(attr, checked):
    """The colour picker: one round button per colour, then None."""
    swatch = '<button type="button" role="menuitemradio" aria-checked="%s" data-%s="%s" title="%s" aria-label="%s">%s</button>'
    return '<span class="dots">%s</span>' % "".join(
        swatch % (str(name == checked).lower(), attr, name, name.capitalize(), name.capitalize(),
                  '<i style="--c:%s"></i>' % hue if hue else '<i class="none"></i>')
        for name, hue, _ in COLOURS + (("", "", ""),)).replace('title=""', 'title="None"').replace('aria-label=""', 'aria-label="None"')


TOOLS = ('<span class="split"><button type="button" data-act="add">Add box</button>'
         '<button type="button" data-act="shapes" aria-haspopup="menu" aria-expanded="false" '
         'aria-label="Pick the kind and colour of box">&#9662;</button><span class="menu" role="menu" hidden>%s'
         '<span class="menu-head">Colour of new boxes</span>%s</span></span>'
         % ("".join('<button type="button" role="menuitem" data-shape="%s" data-name="%s"><svg viewBox="0 0 24 18" '
                    'aria-hidden="true">%s</svg><span><b>%s</b><small>%s</small></span></button>'
                    % (shape, name.lower(), icon, name, means) for shape, name, means, icon in BOXES), dots("next", ""))
         + '<span class="split"><button type="button" data-act="colour" aria-haspopup="menu" aria-expanded="false">'
           'Colour &#9662;</button><span class="menu" role="menu" hidden><span class="menu-head">Colour of the selected '
           'box</span>%s</span></span>' % dots("colour", "")
         + "".join('<button type="button" data-act="%s">%s</button>' % pair for pair in (
             ("rename", "Rename"), ("connect", "Connect"), ("delete", "Delete"), ("undo", "Undo"), ("redo", "Redo"),
             ("reset", "Reset"), ("copy", "Copy as mermaid"))))
TEXT_LINK = re.compile(r'\s*(?:--|==)\s+([^-=][^>]*?)\s+(-->|---|==>|===)\s*')


# ---- finding the files --------------------------------------------------------------------------------------

def guides_root():
    """Where guides/ is: beside the package (a checkout, or .feature-flow/ in a repo install), else its bundle."""
    here = Path(__file__).resolve().parent
    for root in (here.parent, here / "_bundle"):
        if (root / "guides" / "styles").is_dir():
            return root
    return None


def styles(root):
    folder = root / "guides" / "styles" if root else None
    return sorted(p.stem for p in folder.glob("*.css")) if folder and folder.is_dir() else []


def source(top, feature):
    """The brainstorm to show: the committed one once the plan exists, else the one in the state folder."""
    for path in (Path(top) / os.environ.get("FLOW_DIR", "plans") / feature / "brainstorm.md",
                 Path(top) / ".feature-flow" / "state" / ("brainstorm-%s.md" % feature)):
        if path.is_file():
            return path
    return None


# ---- markdown, the small part a brainstorm uses --------------------------------------------------------------

def inline(text):
    """Escaped text with `code`, **bold**, *em* and [links](https://...) turned into tags."""
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append("<code>%s</code>" % html.escape(part[1:-1]))
            continue
        piece = html.escape(part, quote=False)
        piece = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
                       lambda m: '<a href="%s">%s</a>' % (html.escape(html.unescape(m.group(2))), m.group(1)), piece)
        piece = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", piece)
        piece = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?![\w*])", r"<em>\1</em>", piece)
        out.append(piece)
    return "".join(out)


def blocks(lines, figures):
    """HTML for a run of markdown lines: paragraphs, lists, tables, fenced code and diagrams."""
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("```"):
            lang = stripped[3:].strip().lower()
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            out.append(figure("\n".join(body), figures) if lang == "mermaid"
                       else "<pre><code>%s</code></pre>" % html.escape("\n".join(body)))
            continue
        if stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            body = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c or "-") for c in r)]
            head, rest = (body[0], body[1:]) if len(rows) > 1 and body is not rows else (None, body)
            table = "".join("<th>%s</th>" % inline(c) for c in head) if head else ""
            out.append('<div class="tbl"><table>%s<tbody>%s</tbody></table></div>' % (
                "<thead><tr>%s</tr></thead>" % table if table else "",
                "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r) for r in rest)))
            continue
        bullet = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if bullet:
            tag = "ol" if bullet.group(2)[0].isdigit() else "ul"
            items = []
            while i < len(lines):
                m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if m:
                    items.append(m.group(3))
                elif lines[i].strip() and items and lines[i].startswith((" ", "\t")):
                    items[-1] += " " + lines[i].strip()
                else:
                    break
                i += 1
            out.append("<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % inline(t) for t in items), tag))
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith(("```", "|")) \
                and not re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
            para.append(lines[i].strip())
            i += 1
        out.append("<p>%s</p>" % inline(" ".join(para)))
    return "\n".join(out)


# ---- diagrams ---------------------------------------------------------------------------------------------------

def label_of(token, ident):
    for opener, closer, shape in SHAPES:
        if token.startswith(opener) and token.endswith(closer):
            text = token[len(opener):len(token) - len(closer)].strip()
            if len(text) > 1 and text[0] == text[-1] == '"':
                text = text[1:-1]
            return text.replace("<br>", " ").replace("<br/>", " "), shape
    return ident, "rect"


def flowchart(text):
    """{"dir", "nodes", "edges"} for a mermaid flowchart the page can lay out and let people drag, else None."""
    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("%%")]
    if not lines:
        return None
    head = re.match(r"^(flowchart|graph)(?:\s+(LR|RL|TD|TB|BT))?\s*;?$", lines[0], re.I)
    if not head:
        return None
    nodes, edges = {}, []

    def node(match):
        ident, token = match.group(1), match.group(2)
        if token:
            label, shape = label_of(token, ident)
            nodes[ident] = {"id": ident, "label": label, "shape": shape}
        elif ident not in nodes:
            nodes[ident] = {"id": ident, "label": ident, "shape": "rect"}
        return ident

    colours, known = {}, {c[0] for c in COLOURS}
    for line in lines[1:]:
        line = line.rstrip(";")
        painted = re.match(r"^class\s+([\w,\s-]+?)\s+([\w-]+)$", line)
        if painted and painted.group(2) in known:
            colours.update((ident.strip(), painted.group(2)) for ident in painted.group(1).split(","))
        if re.match(r"^(classDef|class|style|linkStyle|click|subgraph|end|direction)\b", line):
            continue
        line = TEXT_LINK.sub(lambda m: " %s|%s| " % (m.group(2), m.group(1)), line)
        pos, prev = 0, None
        while pos < len(line):
            m = NODE.match(line, pos)
            if not m or m.end() == pos:
                return None
            ident = node(m)
            if prev is not None:
                edges.append({"from": prev[0], "to": ident, "label": prev[1], "style": prev[2]})
            pos = m.end()
            if pos >= len(line):
                break
            l = LINK.match(line, pos)
            if not l:
                return None
            op = l.group(1)
            prev = (ident, (l.group(2) or "").strip(), "dotted" if "." in op else "thick" if "=" in op else
                    "open" if op in ("---", "===") else "arrow")
            pos = l.end()
        else:
            if prev is not None and pos >= len(line) and line.endswith(("-->", "---", "==>")):
                return None
    if not nodes:
        return None
    for ident, colour in colours.items():
        if ident in nodes:
            nodes[ident]["colour"] = colour
    direction = (head.group(2) or "TD").upper()
    return {"dir": "LR" if direction in ("LR", "RL") else "TD", "nodes": list(nodes.values()), "edges": edges}


def figure(text, figures):
    figures.append(text)
    k = len(figures)
    graph = flowchart(text)
    source_block = ('<details class="src"><summary>Mermaid source</summary><pre><code>%s</code></pre></details>'
                    % html.escape(text))
    if graph is None:
        return ('<figure class="dg" id="fig-%d"><div class="scroll"><pre class="mermaid">%s</pre></div>%s</figure>'
                % (k, html.escape(text), source_block))
    data = json.dumps(graph, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return ('<figure class="dg graph" id="fig-%d" data-fig="%d">'
            '<div class="tools">%s<input class="rename" type="text" hidden maxlength="80">'
            '<span class="edited" hidden>Edited</span></div>'
            '<p class="hint" aria-live="polite">Drag to move. Double-click to rename, Delete to remove, Connect to add an '
            'arrow, Ctrl+Z to undo. Edits stay in this browser; copy the mermaid to keep them.</p>'
            '<div class="scroll"><svg role="img" aria-label="Diagram %d"></svg></div>'
            '<script type="application/json" class="graph-data">%s</script>'
            '<script type="text/plain" class="graph-src">%s</script>%s</figure>'
            % (k, k, TOOLS, k, data, html.escape(text), source_block))


# ---- the page ----------------------------------------------------------------------------------------------------

def slug(text, used):
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"
    name, n = base, 2
    while name in used:
        name, n = "%s-%d" % (base, n), n + 1
    used.add(name)
    return name


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


def render(text, feature, style_css, style_name, fragment=False):
    title, meta, intro, sections = parse(text)
    figures, used = [], set()
    nav, body = [], []
    chosen = ""
    for heading, lines, subs in sections:
        if heading.lower() == "chosen":
            chosen = " ".join(l.strip() for l in lines if l.strip())[:200]
    for heading, lines, subs in sections:
        sid = slug(heading, used)
        kind = heading.lower()
        children = []
        sub_html = []
        for sub, sub_lines in subs:
            cid = slug(sub, used)
            letter = re.match(r"^([A-Z])[.)]\s", sub)
            picked = bool(letter and re.match(r"^\W*%s\b" % letter.group(1), chosen))
            children.append('<li><a href="#%s"><span class="n">%s</span>%s</a></li>'
                            % (cid, html.escape(letter.group(1)) if letter else "&middot;", inline(sub)))
            sub_html.append('<article class="opt%s" id="%s"><h3>%s%s</h3>%s</article>' % (
                " chosen" if picked else "", cid, inline(sub),
                ' <span class="badge">chosen</span>' if picked else "", blocks(sub_lines, figures)))
        cls = {"chosen": "callout good", "rejected": "muted", "open": "callout", "risks for the planner": "callout"}
        inner = blocks(lines, figures)
        if kind in cls and cls[kind].startswith("callout"):
            inner = '<div class="%s">%s</div>' % (cls[kind], inner)
        body.append('<section class="block%s" id="%s"><div class="lvl-head"><div class="eyebrow">%s</div><h2>%s</h2>'
                    '</div>%s%s</section>' % (" muted" if kind == "rejected" else "", sid,
                                              html.escape(feature), inline(heading), inner,
                                              '<div class="opts">%s</div>' % "".join(sub_html) if sub_html else ""))
        nav.append('<li><a href="#%s"><span class="n">%d</span>%s</a>%s</li>' % (
            sid, len(nav) + 1, inline(heading), '<ol class="sub">%s</ol>' % "".join(children) if children else ""))
    fonts = FONT_LINE.search(style_css)
    meta_html = "".join('<span><b>%s:</b> %s</span>' % (html.escape(k.capitalize()), inline(v))
                        for k, v in meta.items())
    needs_mermaid = any(flowchart(f) is None for f in figures)
    page_title = "Brainstorm: %s" % feature
    head = ("<title>%s</title>\n<meta name=\"claude:viewport-fit-sides\" content=\"cover\">\n%s<style>\n%s\n%s\n</style>\n"
            % (html.escape(page_title),
               ('<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" '
                'href="https://fonts.gstatic.com" crossorigin>\n<link rel="stylesheet" href="%s">\n'
                % html.escape(fonts.group(1)) if fonts else ""), BASE_CSS + PALETTE_CSS, style_css))
    content = (
        '<div class="wrap" data-page="%s">\n<nav class="route" aria-label="Sections">'
        '<div class="progress"><div class="bar"><i></i></div><div class="count">0 of %d sections read</div></div>'
        '<div class="stage">Brainstorm</div><ol>%s</ol>'
        '<div class="stage">View</div><div class="controls">'
        '<div class="seg" role="group" aria-label="Theme"><button type="button" data-theme-set="system">System</button>'
        '<button type="button" data-theme-set="light">Light</button><button type="button" data-theme-set="dark">Dark'
        '</button></div><label class="motion"><input type="checkbox" id="motion"> Animate the arrows</label></div>'
        '</nav>\n<main>\n<header class="hero"><div class="eyebrow">Brainstorm review &middot; style %s</div>'
        '<h1>%s</h1>%s<div class="meta">%s</div></header>\n%s\n</main>\n</div>\n%s<script>\n%s\n</script>\n'
        % (html.escape(feature), len(nav), "".join(nav), html.escape(style_name), inline(title or page_title),
           blocks(intro, figures), meta_html, "\n".join(body),
           '<script src="%s"></script>\n' % MERMAID if needs_mermaid else "", PALETTE_JS + BASE_JS))
    if fragment:
        return head + content
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" '
            'content="width=device-width, initial-scale=1, viewport-fit=cover">\n%s</head>\n<body>\n%s</body>\n</html>\n'
            % (head, content))


def main(argv, out=None, err=None, root=None):
    out = out or sys.stdout
    err = err or sys.stderr
    args, style, fragment, target = [], None, False, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--fragment":
            fragment = True
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
    text = path.read_text(encoding="utf-8", errors="replace")
    root = Path(root) if root else guides_root()
    names = styles(root)
    _, meta, _, _ = parse(text)
    name = (style or meta.get("style") or os.environ.get("FLOW_STYLE") or DEFAULT_STYLE).strip().lower()
    if name not in names:
        err.write("no style %s: pick one of %s (guides/styles/)\n" % (name, ", ".join(names) or "none installed"))
        return 1
    css = (root / "guides" / "styles" / (name + ".css")).read_text(encoding="utf-8")
    page = render(text, feature, css, name, fragment)
    dest = Path(target) if target else path.with_suffix(".html")
    dest.write_text(page, encoding="utf-8")
    out.write("wrote %s\n" % dest.as_posix())
    return 0


# ---- the page's own CSS and script, shared by every style ----------------------------------------------------

BASE_CSS = r"""
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font-family:var(--f-body);font-size:16.5px;line-height:1.65;margin:0}
.wrap{max-width:1180px;margin:0 auto;padding-left:max(16px, env(safe-area-inset-left, 0px));padding-right:max(16px, env(safe-area-inset-right, 0px));padding-block:40px 80px;display:grid;grid-template-columns:230px minmax(0,1fr);gap:48px}
h1,h2,h3,h4{font-family:var(--f-display);text-wrap:balance;line-height:1.15;margin:0}
h1{font-size:clamp(2rem,5vw,3.2rem);font-weight:700}
h2{font-size:1.8rem;font-weight:700}
h3{font-size:1.2rem;font-weight:700;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
p{margin:0;max-width:46rem}
a{color:var(--acc);text-underline-offset:3px}
a:focus-visible,button:focus-visible,input:focus-visible,summary:focus-visible,g.node:focus-visible{outline:2px solid var(--acc);outline-offset:2px;border-radius:4px}
code{font-family:var(--f-mono);font-size:.86em;background:var(--code-bg);padding:1px 5px;border-radius:4px}
pre{margin:0;font-family:var(--f-mono);font-size:.82rem;line-height:1.55;background:var(--code-bg);padding:12px 14px;border-radius:8px;overflow-x:auto;white-space:pre}
pre code{background:none;padding:0}
ul,ol{margin:0;padding-left:1.2em;display:grid;gap:6px;max-width:46rem}
.eyebrow{font-family:var(--f-display);font-size:.78rem;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-weight:500}
nav.route{position:sticky;top:calc(env(safe-area-inset-top, 0px) + 24px);align-self:start;font-family:var(--f-display);font-size:.92rem;max-height:calc(100vh - 48px);overflow-y:auto;padding-right:4px}
.route .progress{display:grid;gap:6px;margin-bottom:18px}
.route .bar{height:6px;background:var(--line);border-radius:3px;overflow:hidden}
.route .bar i{display:block;height:100%;width:0;background:var(--acc);transition:width .3s}
.route .count{color:var(--muted);font-size:.82rem}
.route .stage{margin:16px 0 6px;font-size:.72rem;text-transform:uppercase;letter-spacing:.12em;color:var(--muted)}
.route ol{list-style:none;margin:0;padding:0;border-left:2px solid var(--line);display:block}
.route ol.sub{border-left:none;margin-left:22px}
.route li a{display:grid;grid-template-columns:22px 1fr;gap:8px;align-items:baseline;padding:4px 0 4px 12px;margin-left:-2px;border-left:2px solid transparent;color:var(--fg);text-decoration:none}
.route ol.sub li a{padding-left:4px;font-size:.86rem;color:var(--muted)}
.route li a:hover{border-left-color:var(--line-strong)}
.route li a.here{border-left-color:var(--acc);color:var(--acc)}
.route li a .n{font-family:var(--f-mono);font-size:.78rem;color:var(--muted)}
.controls{display:grid;gap:10px}
.seg{display:inline-grid;grid-template-columns:repeat(3,auto);border:1px solid var(--line);border-radius:8px;overflow:hidden;width:max-content}
.seg button{font:inherit;font-size:.82rem;background:var(--box);color:var(--fg);border:0;padding:5px 10px;cursor:pointer}
.seg button+button{border-left:1px solid var(--line)}
.seg button[aria-pressed="true"]{background:var(--acc);color:var(--box)}
.motion{font-size:.85rem;color:var(--muted);display:flex;gap:8px;align-items:center;cursor:pointer}
main{min-width:0;display:grid;gap:64px}
.hero{display:grid;gap:16px;max-width:46rem}
.meta{display:flex;flex-wrap:wrap;gap:8px 20px;font-family:var(--f-display);font-size:.9rem;color:var(--muted)}
.meta b{color:var(--fg);font-weight:500}
section.block{display:grid;gap:20px;scroll-margin-top:24px}
section.block.muted{opacity:.82}
.lvl-head{display:grid;gap:8px;padding-bottom:14px;border-bottom:1px solid var(--line)}
.opts{display:grid;gap:22px}
.opt{background:var(--card);border:1px solid var(--line);border-radius:var(--radius,12px);padding:18px 20px;display:grid;gap:14px;align-content:start;min-width:0;scroll-margin-top:24px}
.opt.chosen{border-color:var(--acc);box-shadow:0 0 0 1px var(--acc)}
.badge{font-family:var(--f-mono);font-size:.72rem;font-weight:500;text-transform:uppercase;letter-spacing:.08em;background:var(--acc-soft);color:var(--acc);padding:2px 8px;border-radius:99px}
.callout{border-left:3px solid var(--warn);background:var(--warn-soft);padding:12px 16px;border-radius:0 8px 8px 0;max-width:46rem;display:grid;gap:8px}
.callout.good{border-left-color:var(--acc);background:var(--acc-soft)}
figure.dg{margin:0;background:var(--card);border:1px solid var(--line);border-radius:var(--radius,12px);padding:14px;display:grid;gap:10px;min-width:0}
.opt figure.dg{background:var(--box);--fig-bg:var(--box)}
.dg .scroll{overflow-x:auto}
.dg .scroll svg{display:block;width:100%;height:auto;max-height:520px;min-width:560px;touch-action:none;user-select:none}
.dg .tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-family:var(--f-display);font-size:.82rem}
.dg .tools button{font:inherit;background:var(--box);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:3px 10px;cursor:pointer}
.dg .tools button:hover{border-color:var(--line-strong)}
.dg .split{position:relative;display:inline-flex}
.dg .split>button[data-act="add"]{border-radius:6px 0 0 6px}
.dg .split>button[data-act="shapes"]{border-radius:0 6px 6px 0;margin-left:-1px;padding:3px 7px}
.dg .split>button:hover,.dg .split>button:focus-visible{position:relative;z-index:1}
.dg .menu{position:absolute;top:calc(100% + 4px);left:0;z-index:5;display:grid;min-width:16rem;padding:4px;background:var(--box);border:1px solid var(--line-strong);border-radius:8px;box-shadow:0 8px 24px rgb(0 0 0 / .14)}
.dg .menu[hidden]{display:none}
.dg .tools .menu button{display:grid;grid-template-columns:28px 1fr;gap:10px;align-items:center;text-align:left;border:0;border-radius:6px;padding:6px 8px}
.dg .tools .menu button:hover,.dg .tools .menu button:focus-visible{background:var(--acc-soft);outline:none}
.dg .menu svg{width:28px;height:21px;fill:none;stroke:var(--acc);stroke-width:1.6}
.dg .menu b{display:block;font-weight:500}
.dg .menu small{display:block;color:var(--muted);font-size:.78rem}
.dg .menu-head{display:block;padding:8px 8px 4px;font-family:var(--f-mono);font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.dg .menu i{display:inline-block;width:18px;height:18px;border-radius:50%;border:2px solid var(--c,var(--line-strong));background:color-mix(in srgb,var(--c,var(--box)) 22%,var(--box));justify-self:center}
.dg .tools .menu .dots{display:grid;grid-template-columns:repeat(7,auto);justify-content:start;gap:2px;padding:0 4px 4px}
.dg .tools .menu .dots button{display:block;padding:5px}
.dg .tools .menu [aria-checked="true"]{background:var(--acc-soft)}
.dg .tools .menu [aria-checked="true"] i{box-shadow:0 0 0 2px var(--box),0 0 0 4px var(--acc)}
.dg .menu i.none{border-style:dashed;border-color:var(--line-strong);background:var(--box)}
.dg .tools button:disabled{opacity:.45;cursor:default}
.dg .tools button[aria-pressed="true"]{background:var(--acc);color:var(--box);border-color:var(--acc)}
.dg .tools input.rename{font:inherit;background:var(--box);color:var(--fg);border:1px solid var(--acc);border-radius:6px;padding:3px 8px;min-width:0;width:16rem;max-width:100%}
.dg .edited{font-family:var(--f-mono);font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:var(--acc);background:var(--acc-soft);padding:2px 8px;border-radius:99px}
.dg .hint{color:var(--muted);font-family:var(--f-display);font-size:.82rem;margin:0}
.dg svg:focus{outline:none}
.dg details.src summary{font-family:var(--f-display);font-size:.82rem;color:var(--muted);cursor:pointer}
.dg details.src pre{margin-top:8px}
.dg pre.mermaid{background:none;text-align:center}
g.node{cursor:grab}
g.node.dragging{cursor:grabbing}
g.node .shape{fill:var(--box);stroke:var(--line-strong);stroke-width:1.3}
.dg g.node:hover .shape,.dg g.node.dragging .shape{stroke:var(--acc);stroke-width:2}
g.node text{fill:var(--fg);font-family:var(--f-display);font-size:13px;font-weight:500;pointer-events:none}
g.edge path{fill:none;stroke:var(--line-strong);stroke-width:1.4}
g.edge.dotted path{stroke-dasharray:4 4}
g.edge.thick path{stroke-width:2.6}
g.edge text{fill:var(--muted);font-family:var(--f-mono);font-size:11px}
g.edge rect{fill:var(--fig-bg,var(--card))}
.motion-on g.edge path{stroke-dasharray:6 6;animation:flow 1.2s linear infinite}
@keyframes flow{to{stroke-dashoffset:-12}}
g.edge{cursor:pointer}
.dg g.edge path.hit{stroke:transparent;stroke-width:14;stroke-dasharray:none;animation:none;pointer-events:stroke}
.dg g.node.sel .shape{stroke:var(--acc);stroke-width:2.6}
.dg g.node.from .shape{stroke:var(--acc);stroke-width:2.6;stroke-dasharray:5 3}
g.node:focus{outline:none}
.dg g.node:focus-visible .shape{stroke:var(--acc);stroke-width:2.6}
.dg g.edge.sel path:not(.hit){stroke:var(--acc);stroke-width:2.4}
.dg g.edge.sel text{fill:var(--acc)}
@media (prefers-reduced-motion: reduce){.motion-on g.edge path{animation:none}.route .bar i{transition:none}}
.tbl{overflow-x:auto;max-width:52rem}
table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-family:var(--f-display);font-size:.82rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:500}
.toast{position:fixed;bottom:calc(16px + env(safe-area-inset-bottom, 0px));right:max(16px, env(safe-area-inset-right, 0px));background:var(--fg);color:var(--bg);padding:8px 14px;border-radius:8px;font-family:var(--f-display);font-size:.88rem}
@media (max-width: 900px){
  .wrap{grid-template-columns:minmax(0,1fr);gap:32px;padding-block:24px 64px}
  nav.route{position:static;max-height:none;border:1px solid var(--line);border-radius:12px;padding:14px 16px;background:var(--card)}
  .route ol{border-left:none}
  .route li a{border-left:none;padding-left:0}
}
"""

PALETTE_CSS = "".join(
    "g.node.c-%s .shape{fill:color-mix(in srgb,%s 16%%,var(--box));stroke:%s}\n" % (name, hue, hue)
    for name, hue, _ in COLOURS)
PALETTE_JS = "\nvar PALETTE = %s;" % json.dumps({name: [hue, fill] for name, hue, fill in COLOURS})

BASE_JS = r"""
(function () {
  var root = document.documentElement, page = (document.querySelector('.wrap') || {}).dataset || {};
  var key = 'brainstorm:' + (page.page || 'page') + ':';
  function load(k) { try { return localStorage.getItem(key + k); } catch (e) { return null; } }
  function save(k, v) { try { if (v === null) localStorage.removeItem(key + k); else localStorage.setItem(key + k, v); } catch (e) {} }
  function toast(text) {
    var t = document.createElement('div'); t.className = 'toast'; t.setAttribute('role', 'status'); t.textContent = text;
    document.body.appendChild(t); setTimeout(function () { t.remove(); }, 1800);
  }

  // theme: system, light or dark
  function theme(value) {
    if (value === 'light' || value === 'dark') root.setAttribute('data-theme', value); else root.removeAttribute('data-theme');
    document.querySelectorAll('[data-theme-set]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.themeSet === (value || 'system'))); });
  }
  theme(load('theme') || 'system');
  document.querySelectorAll('[data-theme-set]').forEach(function (b) {
    b.addEventListener('click', function () { theme(b.dataset.themeSet); save('theme', b.dataset.themeSet); });
  });

  // motion: off until the reader turns it on
  var motion = document.getElementById('motion');
  if (motion) {
    motion.checked = load('motion') === 'on';
    root.classList.toggle('motion-on', motion.checked);
    motion.addEventListener('change', function () { root.classList.toggle('motion-on', motion.checked); save('motion', motion.checked ? 'on' : null); });
  }

  // the route: which section is in view, and how far the reader got
  var links = Array.prototype.slice.call(document.querySelectorAll('nav.route > ol > li > a'));
  var sections = links.map(function (a) { return document.getElementById(a.getAttribute('href').slice(1)); });
  var seen = {}, bar = document.querySelector('.route .bar i'), count = document.querySelector('.route .count');
  function mark() {
    var current = 0;
    sections.forEach(function (s, i) { if (s && s.getBoundingClientRect().top < window.innerHeight * 0.35) { current = i; seen[i] = true; } });
    links.forEach(function (a, i) { a.classList.toggle('here', i === current); });
    var n = Object.keys(seen).length;
    if (bar) bar.style.width = (sections.length ? 100 * n / sections.length : 0) + '%';
    if (count) count.textContent = n + ' of ' + sections.length + ' sections read';
  }
  window.addEventListener('scroll', mark, { passive: true });
  mark();

  // diagrams: lay out, draw, drag
  var NS = 'http://www.w3.org/2000/svg';
  function el(name, attrs, parent) {
    var e = document.createElementNS(NS, name);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function wrap(text) {
    var words = text.split(/\s+/), lines = [], line = '';
    words.forEach(function (w) { if ((line + ' ' + w).trim().length > 22 && line) { lines.push(line); line = w; } else line = (line + ' ' + w).trim(); });
    if (line) lines.push(line);
    return lines.slice(0, 4);
  }
  function measure(n) {
    n.lines = wrap(n.label);
    var longest = Math.max.apply(null, n.lines.map(function (l) { return l.length; }).concat(1));
    n.w = Math.max(96, Math.min(230, longest * 7.4 + 32));
    n.h = Math.max(44, n.lines.length * 17 + 24);
    if (n.shape === 'diamond') { n.w += 40; n.h += 24; }
    if (n.shape === 'circle') { n.w = n.h = Math.max(n.w, n.h); }
  }
  function loops(g) {  // depth first, in the order the source names them: an edge back to an open node is a loop
    var ids = g.nodes.map(function (n) { return n.id; }), state = {}, forward = [], out = {};
    g.edges.forEach(function (e) { (out[e.from] = out[e.from] || []).push(e); });
    function visit(id) {
      state[id] = 1;
      (out[id] || []).forEach(function (e) {
        if (state[e.to] === 1 || e.to === e.from) return;
        forward.push(e);
        if (!state[e.to]) visit(e.to);
      });
      state[id] = 2;
    }
    ids.forEach(function (id) { if (!state[id]) visit(id); });
    g.edges.forEach(function (e) { e.back = forward.indexOf(e) < 0; });
    return forward;
  }
  function layout(g) {
    var lr0 = g.dir === 'LR', rank = {}, ids = g.nodes.map(function (n) { return n.id; }), forward = loops(g);
    ids.forEach(function (id) { rank[id] = 0; });
    for (var pass = 0; pass < ids.length; pass++) {
      var moved = false;
      forward.forEach(function (e) { if (rank[e.to] < rank[e.from] + 1) { rank[e.to] = rank[e.from] + 1; moved = true; } });
      if (!moved) break;
    }
    var rows = {}, pos = {};
    g.nodes.forEach(function (n) {
      measure(n);
      (rows[rank[n.id]] = rows[rank[n.id]] || []).push(n);
    });
    var longest = g.edges.reduce(function (m, e) { return Math.max(m, e.label.length); }, 0);
    var step = Math.max(lr0 ? 72 : 64, longest * 6.6 + 36);
    var along = 0, lr = lr0, gap = lr ? 28 : 36, spans = {}, widest = 0;
    Object.keys(rows).forEach(function (r) {
      spans[r] = rows[r].reduce(function (s, n) { return s + (lr ? n.h : n.w) + gap; }, -gap);
      widest = Math.max(widest, spans[r]);
    });
    Object.keys(rows).sort(function (a, b) { return a - b; }).forEach(function (r) {
      var row = rows[r], depth = Math.max.apply(null, row.map(function (n) { return lr ? n.w : n.h; }));
      var across = (widest - spans[r]) / 2;
      row.forEach(function (n) {
        var size = lr ? n.h : n.w;
        pos[n.id] = lr ? { x: along + depth / 2, y: across + size / 2 } : { x: across + size / 2, y: along + depth / 2 };
        across += size + gap;
      });
      along += depth + step;
    });
    return pos;
  }
  function border(n, p, toward) {
    var dx = toward.x - p.x, dy = toward.y - p.y;
    if (!dx && !dy) return { x: p.x, y: p.y };
    var sx = (n.w / 2) / Math.abs(dx || 1e-9), sy = (n.h / 2) / Math.abs(dy || 1e-9);
    var s = Math.min(sx, sy);
    if (n.shape === 'diamond' || n.shape === 'circle') s = Math.min(s, 1 / (Math.abs(dx) / (n.w / 2) + Math.abs(dy) / (n.h / 2)) * (n.shape === 'circle' ? 1.2 : 1));
    return { x: p.x + dx * s, y: p.y + dy * s };
  }
  function shape(n, g) {
    var w = n.w, h = n.h, x = -w / 2, y = -h / 2;
    if (n.shape === 'diamond') return el('polygon', { points: [0, y, w / 2, 0, 0, h / 2, x, 0].join(' '), class: 'shape' }, g);
    if (n.shape === 'hexagon') return el('polygon', { points: [x + 14, y, w / 2 - 14, y, w / 2, 0, w / 2 - 14, h / 2, x + 14, h / 2, x, 0].join(' '), class: 'shape' }, g);
    if (n.shape === 'circle') return el('ellipse', { cx: 0, cy: 0, rx: w / 2, ry: h / 2, class: 'shape' }, g);
    if (n.shape === 'cylinder') {
      el('rect', { x: x, y: y + 6, width: w, height: h - 6, class: 'shape' }, g);
      return el('ellipse', { cx: 0, cy: y + 6, rx: w / 2, ry: 6, class: 'shape' }, g);
    }
    return el('rect', { x: x, y: y, width: w, height: h, rx: n.shape === 'stadium' ? h / 2 : n.shape === 'round' ? 14 : 8, class: 'shape' }, g);
  }
  var BRACKETS = { rect: ['[', ']'], round: ['(', ')'], stadium: ['([', '])'], diamond: ['{', '}'], hexagon: ['{{', '}}'], circle: ['((', '))'], cylinder: ['[(', ')]'] };
  var OPS = { arrow: '-->', open: '---', dotted: '-.->', thick: '==>' };
  function clean(g) {  // the graph without what drawing adds, for saving, undo and comparing
    return { dir: g.dir, nodes: g.nodes.map(function (n) { return { id: n.id, label: n.label, shape: n.shape, colour: n.colour || '' }; }),
      edges: g.edges.map(function (e) { return { from: e.from, to: e.to, label: e.label, style: e.style }; }) };
  }
  function mermaid(g) {
    var text = function (s) { return '"' + s.replace(/"/g, '#quot;') + '"'; };
    return ['flowchart ' + g.dir].concat(
      g.nodes.map(function (n) { var b = BRACKETS[n.shape] || BRACKETS.rect; return '  ' + n.id + b[0] + text(n.label) + b[1]; }),
      g.edges.map(function (e) { return '  ' + e.from + ' ' + (OPS[e.style] || OPS.arrow) + (e.label ? '|' + text(e.label) + '|' : '') + ' ' + e.to; }),
      Object.keys(PALETTE).map(function (c) {
        var ids = g.nodes.filter(function (n) { return n.colour === c; }).map(function (n) { return n.id; });
        return ids.length ? '  classDef ' + c + ' fill:' + PALETTE[c][1] + ',stroke:' + PALETTE[c][0] + '\n  class ' + ids.join(',') + ' ' + c : '';
      }).filter(Boolean)
    ).join('\n');
  }
  document.querySelectorAll('figure.graph').forEach(function (fig) {
    var g = JSON.parse(fig.querySelector('.graph-data').textContent), svg = fig.querySelector('.scroll svg');
    var src = fig.querySelector('.graph-src').textContent, store = 'fig' + fig.dataset.fig;
    var start = layout(g), first = JSON.stringify(clean(g)), pos = JSON.parse(JSON.stringify(start));
    try {
      var kept = JSON.parse(load(store) || 'null');
      if (kept && kept.graph) { g = kept.graph; pos = kept.pos || {}; }
      else if (kept) Object.keys(kept).forEach(function (id) { if (pos[id]) pos[id] = kept[id]; });  // a page from before editing kept only places
    } catch (e) {}
    var tool = function (act) { return fig.querySelector('[data-act="' + act + '"]'); };
    var next = '';
    var hint = fig.querySelector('.hint'), help = hint.textContent, edited = fig.querySelector('.edited'), input = fig.querySelector('input.rename');
    var mid = 'arrow-' + fig.dataset.fig, byId = {}, nodes = {}, edges = [];
    var sel = null, linking = null, renaming = null, press = null, last = { at: 0 }, undo = [], redo = [];
    svg.setAttribute('tabindex', '-1');

    function snap() { return JSON.stringify({ g: clean(g), pos: pos }); }
    function persist() {
      var same = JSON.stringify(clean(g)) === first && JSON.stringify(pos) === JSON.stringify(start);
      save(store, same ? null : JSON.stringify({ graph: clean(g), pos: pos }));
    }
    function change(fn) {  // every edit goes through here, so it can be undone
      var before = snap();
      fn();
      undo.push(before); if (undo.length > 100) undo.shift(); redo = [];
      build(); persist();
    }
    function restore(from, to) {
      if (!from.length) return;
      to.push(snap());
      var s = JSON.parse(from.pop()); g = s.g; pos = s.pos;
      build(); persist();
    }
    function exists(s) { return s && (s.node ? byId[s.node] : g.edges[s.edge]); }
    function select(s) {
      sel = exists(s) ? s : null;
      Object.keys(nodes).forEach(function (id) { nodes[id].classList.toggle('sel', !!sel && sel.node === id); nodes[id].classList.toggle('from', linking === id); });
      edges.forEach(function (d, i) { d.grp.classList.toggle('sel', !!sel && sel.edge === i); });
      tool('rename').disabled = tool('delete').disabled = !sel;
      tool('connect').disabled = tool('colour').disabled = !(sel && sel.node);
      tool('connect').setAttribute('aria-pressed', String(!!linking));
      tool('undo').disabled = !undo.length; tool('redo').disabled = !redo.length;
      edited.hidden = JSON.stringify(clean(g)) === first;
      hint.textContent = linking ? 'Click the box the new arrow goes to. Esc cancels.' : help;
    }
    function build() {
      var had = fig.contains(document.activeElement);  // undo can remove the focused box: keep the keys in this figure
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      byId = {}; nodes = {}; edges = [];
      g.nodes.forEach(function (n) { measure(n); byId[n.id] = n; if (!pos[n.id]) pos[n.id] = spot(); });
      g.edges = g.edges.filter(function (e) { return byId[e.from] && byId[e.to]; });
      loops(g);
      var defs = el('defs', {}, svg);
      el('path', { d: 'M0 0L10 5L0 10z', fill: 'var(--line-strong)' }, el('marker', { id: mid, viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse' }, defs));
      var edgeLayer = el('g', {}, svg), nodeLayer = el('g', {}, svg);
      g.edges.forEach(function (e, i) {
        var grp = el('g', { class: 'edge ' + e.style, 'data-i': i }, edgeLayer), hit = el('path', { class: 'hit' }, grp), path = el('path', {}, grp);
        if (e.style !== 'open') path.setAttribute('marker-end', 'url(#' + mid + ')');
        var box = null, text = null;
        if (e.label) { box = el('rect', { rx: 4 }, grp); text = el('text', { 'text-anchor': 'middle' }, grp); text.textContent = e.label; }
        edges.push({ e: e, grp: grp, hit: hit, path: path, box: box, text: text,
          twin: g.edges.some(function (o) { return o.from === e.to && o.to === e.from && o !== e; }) });
      });
      g.nodes.forEach(function (n) {
        var grp = el('g', { class: 'node' + (PALETTE[n.colour] ? ' c-' + n.colour : ''), tabindex: 0, role: 'button', 'data-id': n.id, 'aria-label': n.label + ' (drag to move, Enter to rename)' }, nodeLayer);
        shape(n, grp);
        n.lines.forEach(function (line, i) {
          var t = el('text', { 'text-anchor': 'middle', y: (i - (n.lines.length - 1) / 2) * 17 + 4.5 }, grp);
          t.textContent = line;
        });
        nodes[n.id] = grp;
      });
      place();
      select(sel);
      if (sel && sel.node && had) nodes[sel.node].focus({ preventScroll: true });
      else if (had && !fig.contains(document.activeElement)) svg.focus({ preventScroll: true });
    }
    function spot() {  // a free place for a new box: beside the one selected, else below the rest
      var near = sel && sel.node && pos[sel.node], lr = g.dir === 'LR', p;
      if (near) p = lr ? { x: near.x + 200, y: near.y } : { x: near.x, y: near.y + 110 };
      else {
        var ys = Object.keys(pos).map(function (id) { return pos[id]; });
        p = ys.length ? { x: ys.reduce(function (s, q) { return s + q.x; }, 0) / ys.length, y: Math.max.apply(null, ys.map(function (q) { return q.y; })) + 110 } : { x: 0, y: 0 };
      }
      var taken = function (q) { return Object.keys(pos).some(function (id) { return Math.abs(pos[id].x - q.x) < 110 && Math.abs(pos[id].y - q.y) < 56; }); };
      for (var k = 0; k < 20 && taken(p); k++) p = lr ? { x: p.x, y: p.y + 70 } : { x: p.x + 140, y: p.y };
      return p;
    }
    function place(keepBox) {
      var extra = [];
      g.nodes.forEach(function (n) { nodes[n.id].setAttribute('transform', 'translate(' + pos[n.id].x + ' ' + pos[n.id].y + ')'); });
      edges.forEach(function (d) {
        var a = byId[d.e.from], b = byId[d.e.to], pa = pos[a.id], pb = pos[b.id], line;
        if (a === b) line = 'M' + (pa.x + a.w / 2) + ' ' + pa.y + 'c40 -40 40 40 0 12';
        else {
          var s = border(a, pa, pb), t = border(b, pb, pa), mx = (s.x + t.x) / 2, my = (s.y + t.y) / 2;
          var len = Math.hypot(t.x - s.x, t.y - s.y) || 1;
          var bend = d.twin ? 22 : d.e.back && len > 260 ? Math.min(140, 40 + len * 0.12) : 0;
          if (bend) {  // arrows both ways bend to their own sides; a long arrow back goes round, not through, the boxes
            var nx = -(t.y - s.y) / len * bend, ny = (t.x - s.x) / len * bend;
            line = 'M' + s.x + ' ' + s.y + 'Q' + (mx + 2 * nx) + ' ' + (my + 2 * ny) + ' ' + t.x + ' ' + t.y;
            mx += nx; my += ny; extra.push({ x: mx, y: my });
          } else line = 'M' + s.x + ' ' + s.y + 'L' + t.x + ' ' + t.y;
          if (d.text) {
            d.text.setAttribute('x', mx); d.text.setAttribute('y', my + 4);
            var w = d.e.label.length * 6.6 + 10;
            d.box.setAttribute('x', mx - w / 2); d.box.setAttribute('y', my - 9); d.box.setAttribute('width', w); d.box.setAttribute('height', 18);
          }
        }
        d.path.setAttribute('d', line); d.hit.setAttribute('d', line);
      });
      if (keepBox) return;
      var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      extra.forEach(function (p) { minX = Math.min(minX, p.x - 40); minY = Math.min(minY, p.y - 14); maxX = Math.max(maxX, p.x + 40); maxY = Math.max(maxY, p.y + 14); });
      g.nodes.forEach(function (n) { var p = pos[n.id]; minX = Math.min(minX, p.x - n.w / 2); minY = Math.min(minY, p.y - n.h / 2); maxX = Math.max(maxX, p.x + n.w / 2); maxY = Math.max(maxY, p.y + n.h / 2); });
      if (minX === Infinity) { minX = minY = 0; maxX = 200; maxY = 80; }
      svg.setAttribute('viewBox', [minX - 24, minY - 24, maxX - minX + 48, maxY - minY + 48].join(' '));
    }

    // editing: add, rename, connect, delete, undo, redo
    function add(shape, name, colour) {
      var k = g.nodes.length + 1;
      while (g.nodes.some(function (n) { return n.id === 'N' + k; })) k++;
      var id = 'N' + k;
      change(function () { pos[id] = spot(); g.nodes.push({ id: id, label: 'New ' + (name || 'box'), shape: shape || 'rect', colour: colour || '' }); sel = { node: id }; });
      rename();
    }
    function rename() {
      if (!exists(sel)) return;
      renaming = sel;
      input.hidden = false;
      input.value = sel.node ? byId[sel.node].label : g.edges[sel.edge].label;
      input.setAttribute('aria-label', sel.node ? 'Box name' : 'Arrow label');
      input.focus(); input.select();
    }
    function named(keep) {
      var target = renaming, value = input.value.replace(/\s+/g, ' ').trim();
      renaming = null; input.hidden = true;
      if (!keep || !exists(target)) return;
      if (target.node && value && value !== byId[target.node].label) change(function () { g.nodes.forEach(function (n) { if (n.id === target.node) n.label = value; }); });
      if (!target.node && value !== g.edges[target.edge].label) change(function () { g.edges[target.edge].label = value; });
      if (target.node && nodes[target.node]) nodes[target.node].focus({ preventScroll: true });
    }
    function remove() {
      if (!exists(sel)) return;
      var s = sel; sel = null;
      change(function () {
        if (s.node) { g.nodes = g.nodes.filter(function (n) { return n.id !== s.node; }); g.edges = g.edges.filter(function (e) { return e.from !== s.node && e.to !== s.node; }); delete pos[s.node]; }
        else g.edges.splice(s.edge, 1);
      });
      svg.focus({ preventScroll: true });
    }
    function connect(to) {
      var from = linking; linking = null;
      if (from === to) { select(sel); return; }
      if (g.edges.some(function (e) { return e.from === from && e.to === to; })) { toast('Those boxes are already joined'); select(sel); return; }
      change(function () { g.edges.push({ from: from, to: to, label: '', style: 'arrow' }); sel = { node: to }; });
    }
    function clicked(s) {
      var name = s.node ? 'n' + s.node : 'e' + s.edge, now = Date.now(), twice = last.name === name && now - last.at < 450;
      last = twice ? { at: 0 } : { name: name, at: now };
      if (linking && s.node) { connect(s.node); return; }
      linking = null; select(s);
      if (twice) rename();
    }

    var point = function (ev) { var m = svg.getScreenCTM(); return m ? new DOMPoint(ev.clientX, ev.clientY).matrixTransform(m.inverse()) : { x: 0, y: 0 }; };
    svg.addEventListener('pointerdown', function (ev) {
      if (renaming) named(true);
      var hit = ev.target.closest && ev.target.closest('g.node, g.edge');
      ev.preventDefault();
      if (!hit) { linking = null; select(null); svg.focus({ preventScroll: true }); return; }
      if (hit.classList.contains('edge')) { clicked({ edge: +hit.dataset.i }); svg.focus({ preventScroll: true }); return; }
      var id = hit.dataset.id, p = point(ev);
      press = { id: id, dx: p.x - pos[id].x, dy: p.y - pos[id].y, x: ev.clientX, y: ev.clientY, moved: false, before: snap() };
      svg.setPointerCapture(ev.pointerId); hit.focus({ preventScroll: true });
    });
    svg.addEventListener('pointermove', function (ev) {
      if (!press || (!press.moved && Math.hypot(ev.clientX - press.x, ev.clientY - press.y) < 4)) return;
      press.moved = true; nodes[press.id].classList.add('dragging');
      var p = point(ev); pos[press.id] = { x: p.x - press.dx, y: p.y - press.dy }; place(true);
    });
    function drop() {
      if (!press) return;
      var done = press; press = null;
      if (!done.moved) { clicked({ node: done.id }); return; }
      nodes[done.id].classList.remove('dragging');
      undo.push(done.before); if (undo.length > 100) undo.shift(); redo = [];
      place(); persist(); select(sel);
    }
    svg.addEventListener('pointerup', drop);
    svg.addEventListener('pointercancel', drop);
    svg.addEventListener('focusin', function (ev) { var id = ev.target.dataset && ev.target.dataset.id; if (id && !press && !(sel && sel.node === id)) select({ node: id }); });
    input.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter') { named(true); ev.preventDefault(); }
      else if (ev.key === 'Escape') { named(false); ev.preventDefault(); }
      ev.stopPropagation();
    });
    input.addEventListener('blur', function () { if (renaming) named(true); });
    fig.addEventListener('keydown', function (ev) {
      var mod = ev.ctrlKey || ev.metaKey, key = ev.key.toLowerCase();
      if (mod && key === 'z') { restore(ev.shiftKey ? redo : undo, ev.shiftKey ? undo : redo); ev.preventDefault(); return; }
      if (mod && key === 'y') { restore(redo, undo); ev.preventDefault(); return; }
      if (ev.target.tagName === 'BUTTON' && (ev.key === 'Enter' || ev.key === ' ')) return;
      if (ev.key === 'Escape') { linking = null; select(null); return; }
      if (ev.key === 'Delete' || ev.key === 'Backspace') { remove(); ev.preventDefault(); return; }
      if (ev.key === 'Enter' || ev.key === 'F2') { rename(); ev.preventDefault(); return; }
      var step = ev.shiftKey ? 32 : 8, d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[ev.key];
      if (!d || !(sel && sel.node)) return;
      var id = sel.node;
      change(function () { pos[id] = { x: pos[id].x + d[0], y: pos[id].y + d[1] }; });
      ev.preventDefault();
    });
    tool('add').addEventListener('click', function () { add(); });
    function dropdown(button, pick) {  // a menu under a toolbar button: arrow keys move, Esc closes
      var menu = button.parentNode.querySelector('.menu'), items = Array.prototype.slice.call(menu.querySelectorAll('button'));
      function open(on) {
        menu.hidden = !on; button.setAttribute('aria-expanded', String(on));
        if (on) (menu.querySelector('[data-colour][aria-checked="true"]') || items[0]).focus();
      }
      button.addEventListener('click', function () { if (menu.hidden) pick(null); open(menu.hidden); });
      items.forEach(function (item, i) {
        item.addEventListener('click', function () { if (pick(item) !== 'stay') { open(false); } });
        item.addEventListener('keydown', function (ev) {
          var to = { ArrowDown: i + 1, ArrowUp: i - 1, ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: items.length - 1 }[ev.key];
          if (to !== undefined) { items[(to + items.length) % items.length].focus(); ev.preventDefault(); }
          if (ev.key === 'Escape') { open(false); button.focus(); }
          if (ev.key !== 'Enter' && ev.key !== ' ') ev.stopPropagation();
        });
      });
      document.addEventListener('pointerdown', function (ev) { if (!menu.hidden && !button.parentNode.contains(ev.target)) open(false); });
      return items;
    }
    var nexts = dropdown(tool('shapes'), function (item) {
      if (!item) return;
      if (item.dataset.next === undefined) { add(item.dataset.shape, item.dataset.name, next); return; }
      next = item.dataset.next;
      nexts.forEach(function (b) { if (b.dataset.next !== undefined) b.setAttribute('aria-checked', String(b.dataset.next === next)); });
      return 'stay';
    });
    var paints = dropdown(tool('colour'), function (item) {
      var id = sel && sel.node, now = id && byId[id] ? byId[id].colour || '' : '';
      if (!item) { paints.forEach(function (b) { b.setAttribute('aria-checked', String(b.dataset.colour === now)); }); return; }
      if (id && item.dataset.colour !== now) change(function () { g.nodes.forEach(function (n) { if (n.id === id) n.colour = item.dataset.colour; }); });
      if (id && nodes[id]) nodes[id].focus({ preventScroll: true });
    });
    tool('rename').addEventListener('click', rename);
    tool('delete').addEventListener('click', remove);
    tool('connect').addEventListener('click', function () { linking = linking ? null : sel && sel.node; select(sel); });
    tool('undo').addEventListener('click', function () { restore(undo, redo); });
    tool('redo').addEventListener('click', function () { restore(redo, undo); });
    tool('reset').addEventListener('click', function () {
      change(function () { g = JSON.parse(first); pos = JSON.parse(JSON.stringify(start)); sel = null; linking = null; });
      toast('Back to the original. Undo brings your edits back.');
    });
    tool('copy').addEventListener('click', function () {
      var changed = JSON.stringify(clean(g)) !== first;
      var text = (changed ? mermaid(g) : src.replace(/\s+$/, '')) + '\n%% layout (feature-flow brainstorm page): ' +
        g.nodes.map(function (n) { return n.id + ' ' + Math.round(pos[n.id].x) + ',' + Math.round(pos[n.id].y); }).join('; ') + '\n';
      var done = function () { toast(changed ? 'Copied the edited diagram as mermaid' : 'Copied as mermaid'); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, function () { fallback(text); });
      else fallback(text);
    });
    function fallback(text) {
      var area = document.createElement('textarea'); area.value = text; area.setAttribute('aria-label', 'Mermaid source');
      area.style.position = 'fixed'; area.style.opacity = '0'; document.body.appendChild(area); area.select();
      try { document.execCommand('copy'); toast('Copied as mermaid'); } catch (e) { toast('Select the source below to copy it'); }
      area.remove();
    }
    build();
  });
  if (window.mermaid) { try { window.mermaid.initialize({ startOnLoad: true, theme: 'neutral' }); } catch (e) {} }
})();
"""
