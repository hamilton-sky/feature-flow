"""The live brainstorm: a review page published as an artifact that people edit together and talk to Claude through.

The page (index.html) stays fixed; what people do lands in state.json beside it, which the page saves with the
artifact's own publish. Each person saves their own version of a diagram, keyed by their id; the original is the
brainstorm file's diagram; asks are questions for the session, which answers them and publishes again.

    state.json = {"feature", "round",
                  "figures": {"<n>": {"title", "original": graph, "versions": {"<person id>": {"graph", "pos", "at", "via"}}}},
                  "asks": [{"by", "at", "figure", "version", "text", "answer"}]}

The n-th figure is the n-th mermaid block in the brainstorm file, counted from 1, as on the page.
"""

import hashlib
import json
import re

from feature_flow import brainstorm_page as page

FENCE = re.compile(r"^```mermaid[ \t]*\n(.*?)^```[ \t]*$", re.S | re.M)
OPS = {"arrow": "-->", "open": "---", "dotted": "-.->", "thick": "==>"}
BRACKETS = {"rect": ("[", "]"), "round": ("(", ")"), "stadium": ("([", "])"), "diamond": ("{", "}"),
            "hexagon": ("{{", "}}"), "circle": ("((", "))"), "cylinder": ("[(", ")]")}
LIVE_USAGE = ("usage: feature-flow brainstorm-page <feature> --live DIR [--style NAME]\n"
              "       feature-flow brainstorm-page <feature> --asks STATE\n"
              "       feature-flow brainstorm-page <feature> --answer STATE <ask number> <text>\n"
              "       feature-flow brainstorm-page <feature> --apply STATE <figure> <version: original, claude or a person id>")


def diagrams(text):
    """[(figure number, mermaid source, graph or None)] in the file's order."""
    return [(n, m.group(1).rstrip("\n"), page.flowchart(m.group(1))) for n, m in enumerate(FENCE.finditer(text), 1)]


def titles(text):
    """{figure number: the heading it sits under}, counting figures exactly as diagrams() does."""
    headings = [(m.start(), m.group(1).strip()) for m in re.finditer(r"^#{2,3} (.+)$", text, re.M)]
    out = {}
    for n, m in enumerate(FENCE.finditer(text), 1):
        above = [h for at, h in headings if at < m.start()]
        out[n] = above[-1] if above else ""
    return out


def fingerprint(source):
    return hashlib.sha256(source.strip().encode("utf-8")).hexdigest()[:16]


def lost(source):
    """What a rewrite of this mermaid block drops: the page keeps boxes, arrows, shapes and palette colours only."""
    keep = {c[0] for c in page.COLOURS}
    found = []
    for line in source.splitlines():
        word = line.strip().split(" ", 1)[0]
        if word in ("subgraph", "style", "linkStyle", "click") and word not in found:
            found.append(word)
        elif word == "classDef" and line.split()[1:2] and line.split()[1] not in keep and "classDef" not in found:
            found.append("classDef")
        elif line.strip().startswith("%%") and "comments" not in found:
            found.append("comments")
    return found


def mermaid(graph):
    """Mermaid flowchart text for a graph, with its colours as classDef and class lines (the page's Copy as mermaid)."""
    quote = lambda s: '"%s"' % s.replace('"', "#quot;")
    lines = ["flowchart %s" % graph.get("dir", "TD")]
    for n in graph["nodes"]:
        left, right = BRACKETS.get(n.get("shape"), BRACKETS["rect"])
        lines.append("  %s%s%s%s" % (n["id"], left, quote(n["label"]), right))
    for e in graph["edges"]:
        lines.append("  %s %s%s %s" % (e["from"], OPS.get(e.get("style"), OPS["arrow"]),
                                       "|%s|" % quote(e["label"]) if e.get("label") else "", e["to"]))
    fills = {name: (hue, fill) for name, hue, fill in page.COLOURS}
    for name in fills:
        ids = [n["id"] for n in graph["nodes"] if n.get("colour") == name]
        if ids:
            lines.append("  classDef %s fill:%s,stroke:%s" % (name, fills[name][1], fills[name][0]))
            lines.append("  class %s %s" % (",".join(ids), name))
    return "\n".join(lines)


def state(text, feature, old=None):
    """The state for the brainstorm as it is now, keeping the versions and asks people saved in the old one."""
    old = old if isinstance(old, dict) else {}
    named = titles(text)
    figures = {}
    for n, source, graph in diagrams(text):
        if graph is None:
            continue
        kept = (old.get("figures") or {}).get(str(n)) or {}
        figures[str(n)] = {"title": named.get(n, ""), "source": fingerprint(source), "original": graph,
                           "versions": kept.get("versions") or {}}
    return {"feature": feature, "round": int(old.get("round") or 0) + 1, "figures": figures,
            "asks": old.get("asks") if isinstance(old.get("asks"), list) else []}


def asks(st):
    """What the people on the page asked and nobody answered yet, as text for the session."""
    lines = []
    for i, ask in enumerate(st.get("asks") or [], 1):
        if ask.get("answer"):
            continue
        fig = str(ask.get("figure") or "")
        where = fig and (st.get("figures") or {}).get(fig)
        lines.append("ask %d from %s at %s%s:" % (i, ask.get("by") or "someone", ask.get("at") or "?",
                                                    " about figure %s (%s)" % (fig, where.get("title", "")) if where else ""))
        lines.append("  " + str(ask.get("text") or "").replace("\n", "\n  "))
        version = where and ask.get("version") and where["versions"].get(ask["version"])
        if version:
            lines.append("  their version of the figure (%s):" % ", ".join(version.get("via") or ["by hand"]))
            lines.append("    " + mermaid(version["graph"]).replace("\n", "\n    "))
    return "\n".join(lines) if lines else "no open asks"


def answer(st, number, text):
    items = st.get("asks") or []
    if not 1 <= number <= len(items):
        raise ValueError("no ask %d: there are %d" % (number, len(items)))
    items[number - 1]["answer"] = text
    return st


def apply(text, st, figure, version):
    """The brainstorm text with figure `figure` replaced by that version of it."""
    fig = (st.get("figures") or {}).get(str(figure))
    if not fig:
        raise ValueError("no figure %s in the page's state: figures %s" % (figure, ", ".join(sorted(st.get("figures") or {})) or "none"))
    graph = fig["original"] if version == "original" else (fig["versions"].get(version) or {}).get("graph")
    if graph is None:
        raise ValueError("figure %s has no version %s: it has original%s" % (
            figure, version, "".join(", " + v for v in sorted(fig["versions"]))))
    blocks = list(FENCE.finditer(text))
    if not str(figure).isdigit() or not 1 <= int(figure) <= len(blocks):
        raise ValueError("the brainstorm file has %d diagrams, so no figure %s: build the page again" % (len(blocks), figure))
    block = blocks[int(figure) - 1]
    if fig.get("source") and fingerprint(block.group(1)) != fig["source"]:
        raise ValueError("figure %s in the brainstorm changed since the page was built: build the page again (--live), "
                         "publish it, and apply after the next save" % figure)
    return text[:block.start(1)] + mermaid(graph) + "\n" + text[block.end(1):]


def load(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def dump(st):
    return json.dumps(st, ensure_ascii=False, indent=1) + "\n"


# ---- the page's live layer: shown only on a page published as an artifact that can save itself ----------------

LIVE_CSS = r"""
.live-panel{display:grid;gap:14px;background:var(--card);border:1px solid var(--line);border-radius:var(--radius,12px);padding:18px 20px;max-width:52rem}
.live-panel[hidden],.live-bar[hidden]{display:none}
.live-panel h2{font-size:1.2rem}
.live-panel .who{font-family:var(--f-display);font-size:.82rem;color:var(--muted)}
.live-panel ol{list-style:none;padding:0;display:grid;gap:12px}
.live-panel li{display:grid;gap:4px;border-left:3px solid var(--line);padding-left:12px}
.live-panel li.answered{border-left-color:var(--acc)}
.live-panel .reply{background:var(--acc-soft);border-radius:8px;padding:8px 12px}
.live-panel form{display:grid;gap:8px}
.live-panel textarea,.live-bar input[type=text]{font:inherit;font-size:.92rem;background:var(--box);color:var(--fg);border:1px solid var(--line-strong);border-radius:8px;padding:8px 10px;width:100%;min-height:4.5em;resize:vertical}
.live-bar input[type=text]{min-height:0}
.live-panel .row,.live-bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-family:var(--f-display);font-size:.82rem}
.live-bar{padding:8px 10px;border:1px dashed var(--line-strong);border-radius:8px}
.live-panel select,.live-bar select,.live-panel button,.live-bar button{font:inherit;background:var(--box);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:3px 10px;cursor:pointer}
.live-panel button.go,.live-bar button.go{background:var(--acc);color:var(--box);border-color:var(--acc)}
.live-panel button:disabled,.live-bar button:disabled{opacity:.45;cursor:default}
.live-bar label{display:inline-flex;gap:6px;align-items:center;color:var(--muted)}
.live-bar .said{flex-basis:100%;color:var(--muted)}
.live-note{font-family:var(--f-display);font-size:.85rem;color:var(--muted)}
g.node.diff-add .shape{stroke:#2f8a3e;stroke-width:2.6}
g.node.diff-ren .shape{stroke:#b58100;stroke-width:2.6}
g.node.diff-ren text.was{fill:var(--muted);text-decoration:line-through;font-size:11px;font-weight:400}
g.ghost .shape{fill:none;stroke:#c8402f;stroke-width:1.6;stroke-dasharray:5 4;opacity:.75}
g.ghost text{fill:#c8402f;opacity:.75;text-decoration:line-through;font-family:var(--f-display);font-size:13px}
.dg g.edge.diff-add path:not(.hit){stroke:#2f8a3e;stroke-width:2.4}
g.edge.ghost path{fill:none;stroke:#c8402f;stroke-width:1.6;stroke-dasharray:5 4;opacity:.75}
.diff-sum{font-family:var(--f-mono);font-size:.78rem;color:var(--muted)}
"""

LIVE_JS = r"""
(function () {
  var wrap = document.querySelector('.wrap');
  if (!wrap || !wrap.dataset.live || !window.claude || !window.claude.use) return;
  var STASH = 'brainstorm-live:' + wrap.dataset.page;
  var main = document.querySelector('main'), panel = document.createElement('section');
  panel.className = 'live-panel'; panel.id = 'talk'; panel.hidden = true;
  main.insertBefore(panel, main.children[1] || null);
  function toast(text) {
    var t = document.createElement('div'); t.className = 'toast'; t.setAttribute('role', 'status'); t.textContent = text;
    document.body.appendChild(t); setTimeout(function () { t.remove(); }, 2400);
  }
  function make(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function hash(text) {
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)).then(function (b) {
      return Array.prototype.map.call(new Uint8Array(b), function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
    });
  }
  var use = function (name) { return window.claude.use(name).catch(function () { return null; }); };
  Promise.all([fetch('state.json', { cache: 'no-store' }).then(function (r) { return r.ok ? r.text() : null; }).catch(function () { return null; }),
               use('artifact'), use('user'), use('sample')]).then(function (got) {
    if (!got[0] || !got[1]) return;
    var text = got[0], artifact = got[1], user = got[2], sample = got[3], st;
    try { st = JSON.parse(text); } catch (e) { return; }
    st.figures = st.figures || {}; st.asks = st.asks || [];
    hash(text).then(function (sha) { (user ? user.id() : Promise.resolve(null)).then(function (me) { start(st, sha, artifact, user, sample, me); }); });
  });

  function start(st, sha, artifact, user, sample, me) {
    var writable = !!me, figs = [];
    function names(ids) {
      return user ? user.profiles(ids).then(function (ps) { var o = {}; ids.forEach(function (id) { o[id] = id === me ? 'You' : (ps[id] && ps[id].name) || 'Someone'; }); return o; })
                  : Promise.resolve(ids.reduce(function (o, id) { o[id] = id === me ? 'You' : 'Someone'; return o; }, {}));
    }
    function save(change, done) {  // change the state and publish it; a clash with someone else's save reloads and tries once more
      try {  // kept across the reload a clash causes; a private window may refuse it, and then a clash loses the change
        var pending = JSON.parse(sessionStorage.getItem(STASH) || '[]'); pending.push(change);
        sessionStorage.setItem(STASH, JSON.stringify(pending));
      } catch (e) {}
      var next = JSON.parse(JSON.stringify(st));  // the page's state changes only once the save lands
      merge(next, change);
      var body = JSON.stringify(next, null, 1) + '\n';
      artifact.publish({ 'state.json': { content: body, contentType: 'application/json', ifMatch: sha } }).then(function (res) {
        try { sessionStorage.removeItem(STASH); } catch (e) {}
        merge(st, change);
        sha = res && res.shas && res.shas['state.json'];
        if (!sha) hash(body).then(function (h) { sha = h; });
        render().then(function () { if (done) done(); });
      }, function (e) {
        var code = e && e.code;
        if (code === 'conflict') {  // this view still holds the old state.json: load the new one, then the stash saves the change again
          toast('Someone saved at the same moment. Reloading, then your change is saved again.');
          setTimeout(function () { location.reload(); }, 1200);
          return;
        }
        try { sessionStorage.removeItem(STASH); } catch (x) {}
        if (code === 'not_writer' || code === 'not_granted' || code === 'capability_disabled' || code === 'consent_required') { writable = false; toast('This view is read only: ask the owner for edit access to save.'); render(); }
        else toast('Could not save (' + (code || 'error') + '). Try again in a moment.');
      });
    }
    function merge(s, change) {
      if (change.version) {
        var f = s.figures[change.version.figure]; if (!f) return;
        f.versions = f.versions || {}; f.versions[change.version.by] = change.version.entry;
      }
      if (change.ask) s.asks.push(change.ask);
    }
    // a change saved just before a reload (a clash) is saved again now
    try {
      var left = JSON.parse(sessionStorage.getItem(STASH) || '[]');
      sessionStorage.removeItem(STASH);
      if (left.length && writable) left.forEach(function (c, i) { if (i === left.length - 1) save(c); else merge(st, c); });
    } catch (e) {}

    document.querySelectorAll('figure.graph').forEach(function (fig) {
      var key = fig.dataset.fig, f = st.figures[key], ed = fig.editor;
      if (!f || !ed) return;
      var bar = make('div', { class: 'live-bar' }), pick = make('select', { 'aria-label': 'Version' });
      var cmp = make('input', { type: 'checkbox' }), saveBtn = make('button', { type: 'button', class: 'go' }, 'Save as my version');
      var askBtn = make('button', { type: 'button' }, 'Ask Claude to change it'), sum = make('span', { class: 'diff-sum' }), said = make('span', { class: 'said' });
      var cmpLabel = make('label'); cmpLabel.appendChild(cmp); cmpLabel.appendChild(document.createTextNode('Compare with original'));
      bar.appendChild(make('span', {}, 'Version')); bar.appendChild(pick); bar.appendChild(cmpLabel); bar.appendChild(saveBtn);
      if (sample) bar.appendChild(askBtn);
      bar.appendChild(sum); bar.appendChild(said); said.hidden = true;
      fig.insertBefore(bar, fig.querySelector('.scroll'));
      var hint = fig.querySelector('.hint');
      if (hint) hint.dataset.help = hint.textContent = 'Drag to move. Double-click to rename, Delete to remove, Connect to add an arrow, Ctrl+Z to undo. Save as my version shares your diagram with everyone on this page.';
      var via = [];  // how the diagram on screen came about since it was loaded: by hand, by Claude, or both
      ed.onChange = function (how) { if (via.indexOf(how) < 0) via.push(how); diff(); };
      function diff() {
        if (!cmp.checked) { ed.compare(null); sum.textContent = ''; return; }
        var d = ed.compare(f.original);
        sum.textContent = d.added + ' added, ' + d.removed + ' removed, ' + d.renamed + ' renamed';
      }
      cmp.addEventListener('change', diff);
      pick.addEventListener('change', function () {
        var v = pick.value === 'original' ? { graph: f.original, pos: null } : f.versions[pick.value];
        if (v) { ed.load(v.graph, v.pos); via = []; diff(); }
      });
      saveBtn.addEventListener('click', function () {
        if (!writable) return;
        var now = ed.get();
        save({ version: { figure: key, by: me, entry: { graph: now.graph, pos: now.pos, at: new Date().toISOString(), via: via.length ? via.slice() : ['hand'] } } },
             function () { toast('Saved as your version'); pick.value = me; });
      });
      askBtn.addEventListener('click', function () {
        var box = bar.querySelector('input[type=text]');
        if (box) { box.focus(); return; }
        box = make('input', { type: 'text', placeholder: 'What should change? For example: add a cache before the database', 'aria-label': 'Ask Claude to change this diagram' });
        var go = make('button', { type: 'button', class: 'go' }, 'Ask');
        bar.insertBefore(box, said); bar.insertBefore(go, said);
        box.focus();
        function ask() {
          var want = box.value.trim(); if (!want) return;
          go.disabled = true; go.textContent = 'Thinking...';
          var now = ed.get().graph;
          sample.json('You edit one flowchart in a design review. The flowchart as JSON:\n' + JSON.stringify(now) +
            '\n\nThe change the reviewer wants: ' + want +
            '\n\nReply with only JSON: {"graph": the whole changed flowchart in the same shape, "reply": one or two sentences on what you changed and why}. ' +
            'Keep the ids of boxes you keep; new ids are short letters and digits. shape is one of rect, round, stadium, diamond, hexagon, circle, cylinder. ' +
            'colour is "" or one of ' + Object.keys(PALETTE).join(', ') + '. style is one of arrow, open, dotted, thick. dir stays "' + now.dir + '".',
            { modelTier: 'default' }).then(function (out) {
            var g = out && out.graph;
            if (!g || !Array.isArray(g.nodes) || !Array.isArray(g.edges)) throw { code: 'invalid_json' };
            var ident = function (x) { return String(x).replace(/[^\w-]/g, ''); }, ids = {};
            var boxes = g.nodes.filter(function (n) { return n && ident(n.id) && !ids[ident(n.id)] && (ids[ident(n.id)] = true); }).map(function (n) { return { id: ident(n.id), label: String(n.label || n.id), shape: n.shape in { rect: 1, round: 1, stadium: 1, diamond: 1, hexagon: 1, circle: 1, cylinder: 1 } ? n.shape : 'rect', colour: PALETTE[n.colour] ? n.colour : '' }; });
            var arrows = g.edges.filter(function (e) { return e && ids[ident(e.from)] && ids[ident(e.to)]; }).map(function (e) { return { from: ident(e.from), to: ident(e.to), label: String(e.label || ''), style: { arrow: 1, open: 1, dotted: 1, thick: 1 }[e.style] ? e.style : 'arrow' }; });
            if (!boxes.length) throw { code: 'invalid_json' };
            ed.load({ dir: now.dir, nodes: boxes, edges: arrows }, null, 'claude');
            said.hidden = false; said.textContent = 'Claude: ' + String(out.reply || 'Done.') + ' Undo takes it back; Save as my version keeps it.';
            box.value = '';
          }).catch(function (e) {
            said.hidden = false;
            said.textContent = e && e.code === 'rate_limited' ? 'Claude is busy: try again in a minute.' : e && e.code === 'not_granted' ? 'Asking Claude is not allowed in this view.' : 'Claude could not change it this time. Try saying it another way.';
          }).then(function () { go.disabled = false; go.textContent = 'Ask'; });
        }
        go.addEventListener('click', ask);
        box.addEventListener('keydown', function (ev) { if (ev.key === 'Enter') { ask(); ev.preventDefault(); } ev.stopPropagation(); });
      });
      figs.push({ key: key, f: f, pick: pick, save: saveBtn });
    });

    function render() {
      var ids = [];
      figs.forEach(function (x) { Object.keys(x.f.versions || {}).forEach(function (id) { if (ids.indexOf(id) < 0) ids.push(id); }); });
      st.asks.forEach(function (a) { if (a.by && ids.indexOf(a.by) < 0) ids.push(a.by); });
      if (me && ids.indexOf(me) < 0) ids.push(me);
      return names(ids).then(function (who) {
        figs.forEach(function (x) {
          var was = x.pick.value;
          while (x.pick.firstChild) x.pick.removeChild(x.pick.firstChild);
          x.pick.appendChild(make('option', { value: 'original' }, 'Original'));
          Object.keys(x.f.versions || {}).forEach(function (id) {
            var v = x.f.versions[id];
            x.pick.appendChild(make('option', { value: id }, (who[id] || 'Someone') + (id === me ? 'r version' : "'s version") + ((v.via || []).indexOf('claude') >= 0 ? ' (with Claude)' : '')));
          });
          x.pick.value = was && (was === 'original' || x.f.versions[was]) ? was : 'original';
          x.save.disabled = !writable;
          x.save.title = writable ? '' : 'Ask the owner for edit access to save';
        });
        while (panel.firstChild) panel.removeChild(panel.firstChild);
        panel.hidden = false;
        panel.appendChild(make('h2', {}, 'Talk to Claude'));
        panel.appendChild(make('p', { class: 'who' }, 'Questions and change requests for the Claude session that made this page. It answers here and may update the diagrams; your saved versions stay.'));
        var list = make('ol');
        st.asks.forEach(function (a) {
          var li = make('li', { class: a.answer ? 'answered' : '' });
          var fig = a.figure && st.figures[a.figure];
          li.appendChild(make('span', { class: 'who' }, (who[a.by] || 'Someone') + (fig ? ' on "' + (fig.title || 'figure ' + a.figure) + '"' : '') + (a.version ? ', with ' + (a.version === me ? 'your' : 'their') + ' version' : '')));
          li.appendChild(make('span', {}, a.text));
          li.appendChild(a.answer ? make('span', { class: 'reply' }, 'Claude: ' + a.answer) : make('span', { class: 'who' }, 'Waiting for Claude'));
          list.appendChild(li);
        });
        if (st.asks.length) panel.appendChild(list);
        if (!writable) { panel.appendChild(make('p', { class: 'live-note' }, 'You can read this page. To save versions or ask Claude, the owner needs to give you edit access.')); return; }
        var form = make('form'), area = make('textarea', { 'aria-label': 'Your question or request', placeholder: 'For example: B looks too big for a first version. What would you cut?' });
        var row = make('div', { class: 'row' }), about = make('select', { 'aria-label': 'About' }), send = make('button', { type: 'submit', class: 'go' }, 'Send to Claude');
        about.appendChild(make('option', { value: '' }, 'About the whole page'));
        figs.forEach(function (x) { about.appendChild(make('option', { value: x.key }, 'About: ' + (x.f.title || 'figure ' + x.key) + (x.f.versions[me] ? ' (with my version)' : ''))); });
        row.appendChild(about); row.appendChild(send);
        form.appendChild(area); form.appendChild(row); panel.appendChild(form);
        form.addEventListener('submit', function (ev) {
          ev.preventDefault();
          var text = area.value.trim(); if (!text) { area.focus(); return; }
          var key = about.value, fig = key && st.figures[key];
          send.disabled = true;
          save({ ask: { by: me, at: new Date().toISOString(), figure: key || null, version: fig && fig.versions[me] ? me : null, text: text } },
               function () { toast('Sent. Claude answers here when its session picks it up.'); });
        });
      });
    }
    render();
  }
})();
"""
