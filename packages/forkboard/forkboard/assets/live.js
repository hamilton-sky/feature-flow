
(function () {
  var wrap = document.querySelector('.wrap');
  if (!wrap || !wrap.dataset.live) return;
  var STASH = 'brainstorm-live:' + wrap.dataset.page;
  var main = document.querySelector('main'), panel = document.createElement('section');
  panel.className = 'live-panel'; panel.id = 'talk'; panel.hidden = true;
  main.insertBefore(panel, main.children[1] || null);
  function toast(text) {
    var t = document.createElement('div'); t.className = 'toast'; t.setAttribute('role', 'status'); t.textContent = agentText(text);
    document.body.appendChild(t); setTimeout(function () { t.remove(); }, 2400);
  }
  function make(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  var label = wrap.dataset.agentLabel || 'Claude';
  function agentText(text) { return String(text).replace(/Claude/g, function () { return label; }); }
  var boot = make('div', {class: 'live-connection', role: 'status', 'aria-live': 'polite'}, 'Connecting…');
  main.insertBefore(boot, panel);
  var bootTimer, bootStopped = false, bootDelay = 2000;
  window.addEventListener('pagehide', function () { bootStopped = true; clearTimeout(bootTimer); });
  window.ForkboardProviders(wrap).then(function (provider) {
    if (!provider) { boot.textContent = 'Live storage unavailable • Read only'; return; }
    function connect() {
      provider.readState().then(function (got) {
        return provider.identity(got.state).then(function (me) { boot.remove(); start(got.state, got.revision, provider, me); });
      }).catch(function () {
        boot.textContent = 'Connection lost • Retrying; pending work is kept';
        if (!bootStopped) bootTimer = setTimeout(connect, bootDelay);
        bootDelay = Math.min(bootDelay * 2, 30000);
      });
    }
    connect();
  }).catch(function () { boot.textContent = 'Live storage unavailable • Read only'; });

  function start(st, sha, provider, me) {
    var writable = !!me, figs = [], saving = false, queue = [], stopped = false, timer, delay = 2000, pageRevision, epoch = 0;
    var connection = make('div', {class: 'live-connection', role: 'status', 'aria-live': 'polite'});
    var status = make('span', {}, label + (writable ? ' • Connected' : ' • Read only'));
    var retry = make('button', {type: 'button'}, 'Retry save'); retry.hidden = true;
    var unblock = make('button', {type: 'button'}, 'Keep edit and unblock saves'); unblock.hidden = true;
    var preserved = make('div', {}), savedEdits = [];
    try { savedEdits = JSON.parse(sessionStorage.getItem(STASH + ':preserved') || '[]'); } catch (e) { toast('Could not restore preserved edits.'); }
    var update = make('button', {type: 'button'}, 'Review update'); update.hidden = true;
    connection.appendChild(status); connection.appendChild(retry); connection.appendChild(unblock); connection.appendChild(update); connection.appendChild(preserved);
    main.insertBefore(connection, panel);
    var updatePage = null;
    update.addEventListener('click', function () {
      if (!updatePage) return;
      var previous = connection.querySelector('.update-preview'); if (previous) previous.remove();
      var before = make('details', {class: 'update-preview'}), title = make('summary', {}, 'New page available; your edits stay here');
      var frame = make('iframe', {title: 'Updated review page', sandbox: 'allow-scripts'});
      frame.srcdoc = updatePage;
      before.appendChild(title); before.appendChild(frame); connection.appendChild(before); before.open = true;
      update.hidden = true;
    });
    function names(ids) {
      return provider.profiles(ids).then(function (ps) { var o = {}; ids.forEach(function (id) { o[id] = id === me ? 'You' : (ps[id] && ps[id].name) || 'Someone'; }); return o; });
    }
    function remember() {
      try { sessionStorage.setItem(STASH, JSON.stringify(queue.map(function (x) { return x.envelope; }))); } catch (e) { toast('Browser storage unavailable. Keep this page open to retain pending work.'); }
    }
    function accept(got) {
      st = got.state; sha = got.revision; epoch++;
      figs.forEach(function (x) { if (st.figures[x.key]) { x.f = st.figures[x.key]; x.refresh(x.f); } });
    }
    function sourceMatches(change) {
      var payload = change.version || (change.ask && change.ask.figure ? change.ask : null);
      return !payload || !payload.source || (st.figures[payload.figure] && st.figures[payload.figure].source === payload.source);
    }
    function flush() {
      if (saving || !queue.length || !writable) return;
      saving = true; retry.hidden = true; unblock.hidden = true;
      var item = queue[0];
      function send(replayed) {
        if (!sourceMatches(item.envelope.change)) return Promise.reject({code: 'stale_source', message: 'Figure source changed. Keep your edits; review the update before saving.'});
        return provider.saveChange(item.envelope, sha, st, merge).catch(function (e) {
          if (e.code !== 'conflict' || replayed) throw e;
          return provider.readState().then(function (got) { accept(got); return send(true); });
        });
      }
      send(false).then(function (got) {
        accept(got); queue.shift(); remember(); saving = false;
        status.textContent = label + ' • Connected';
        return render().then(function () { if (item.done) item.done(); flush(); });
      }).catch(function (e) {
        saving = false; retry.hidden = false;
        var code = e && e.code;
        unblock.hidden = code !== 'stale_source';
        if (['not_writer', 'not_granted', 'capability_disabled', 'consent_required'].indexOf(code) >= 0) {
          writable = false; status.textContent = label + ' • Read only'; render();
        } else status.textContent = 'Pending changes kept • ' + (e.message || (code === 'conflict' ? 'Save conflicted again. Retry save.' : 'Connection lost. Retry save.'));
      });
    }
    retry.addEventListener('click', flush);
    unblock.addEventListener('click', function () {
      if (saving || !queue.length) return;
      var item = queue[0], next = savedEdits.concat([item.envelope]);
      try { sessionStorage.setItem(STASH + ':preserved', JSON.stringify(next)); }
      catch (e) { status.textContent = 'Could not preserve edit in browser storage. Keep this page open.'; return; }
      savedEdits = next; queue.shift(); remember();
      if (item.cancel) item.cancel();
      unblock.hidden = true; retry.hidden = true; status.textContent = 'Edit preserved • Continuing pending saves';
      showPreserved(); flush();
    });
    function showPreserved() {
      preserved.replaceChildren();
      savedEdits.forEach(function (envelope) {
        var change = envelope.change, payload = change.version || change.ask;
        var button = make('button', {type: 'button'}, 'Restore preserved edit');
        button.addEventListener('click', function () {
          var fig = figs.filter(function (x) { return x.key === payload.figure; })[0];
          if (!fig) { status.textContent = 'Preserved edit belongs to a figure unavailable on this page.'; return; }
          fig.restore(payload);
        });
        preserved.appendChild(button);
      });
    }
    function save(change, done, cancel) {
      var payload = change.version || (change.ask && change.ask.figure ? change.ask : null);
      if (payload && !payload.source && st.figures[payload.figure]) payload.source = st.figures[payload.figure].source;
      queue.push({envelope: {id: crypto.randomUUID(), change: change}, done: done, cancel: cancel}); remember(); flush();
    }
    function merge(s, change) {
      if (change.version) {
        var f = s.figures[change.version.figure]; if (!f) return;
        f.versions = f.versions || {}; f.versions[change.version.by] = change.version.entry;
      }
      if (change.ask) s.asks.push(change.ask);
      if (change.pick) { s.picks = s.picks || {}; s.picks[change.pick.key] = change.pick.entry; }
      (change.picks || []).forEach(function (p) { s.picks = s.picks || {}; s.picks[p.key] = p.entry; });
      if (change.approve) { s.approved = s.approved || {}; s.approved[change.approve.step] = { by: change.approve.by, at: change.approve.at }; }
      (change.unapprove || []).forEach(function (name) { if (s.approved) delete s.approved[name]; });
    }
    try { queue = JSON.parse(sessionStorage.getItem(STASH) || '[]').map(function (envelope) { return {envelope: envelope}; }); }
    catch (e) { toast('Could not restore pending work. Keep this page open.'); }

    document.querySelectorAll('figure.graph').forEach(function (fig) {
      var key = fig.dataset.fig, f = st.figures[key], ed = fig.editor, source = f && f.source;
      if (!f || !ed) return;
      var bar = make('div', { class: 'live-bar' }), pick = make('select', { 'aria-label': 'Version' });
      var cmp = make('input', { type: 'checkbox' }), saveBtn = make('button', { type: 'button', class: 'go' }, 'Save as my version');
      var askBtn = make('button', { type: 'button' }, 'Ask ' + label + ' to change it'), sum = make('span', { class: 'diff-sum' }), said = make('span', { class: 'said' });
      var cmpLabel = make('label'); cmpLabel.appendChild(cmp); cmpLabel.appendChild(document.createTextNode('Compare with original'));
      bar.appendChild(make('span', {}, 'Version')); bar.appendChild(pick); bar.appendChild(cmpLabel); bar.appendChild(saveBtn);
      if (provider.local || provider.propose) bar.appendChild(askBtn);
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
        if (v) { ed.load(v.graph, v.pos); source = v.source || f.source; via = []; diff(); }
      });
      saveBtn.addEventListener('click', function () {
        if (!writable) return;
        var now = ed.get();
        save({ version: { figure: key, by: me, source: source, entry: { graph: now.graph, pos: now.pos, at: new Date().toISOString(), via: via.length ? via.slice() : ['hand'] } } },
             function () { toast('Saved as your version'); pick.value = me; });
      });
      askBtn.addEventListener('click', function () {
        var box = bar.querySelector('input[type=text]');
        if (box) { box.focus(); return; }
        box = make('input', { type: 'text', placeholder: 'What should change? For example: add a cache before the database', 'aria-label': 'Ask ' + label + ' to change this diagram' });
        var go = make('button', { type: 'button', class: 'go' }, 'Ask');
        bar.insertBefore(box, said); bar.insertBefore(go, said);
        box.focus();
        function ask() {
          var draft = box.value, want = draft.trim(); if (!want) return;
          go.disabled = true; go.textContent = 'Thinking...';
          var now = ed.get().graph;
          if (provider.local) {
            save({ask: {by: me, text: want, kind: 'diagram', figure: key, source: source, graph: now}}, function () {
              said.hidden = false; said.textContent = 'Waiting for ' + label; if (box.value === draft) box.value = ''; go.disabled = false; go.textContent = 'Ask';
            }, function () { go.disabled = false; go.textContent = 'Ask'; });
            return;
          }
          provider.propose('You edit one flowchart in a design review. The flowchart as JSON:\n' + JSON.stringify(now) +
            '\n\nThe change the reviewer wants: ' + want +
            '\n\nReply with only JSON: {"graph": the whole changed flowchart in the same shape, "reply": one or two sentences on what you changed and why}. ' +
            'Keep the ids of boxes you keep; new ids are short letters and digits. shape is one of rect, round, stadium, diamond, hexagon, circle, cylinder. ' +
            'colour is "" or one of ' + Object.keys(PALETTE).join(', ') + '. style is one of arrow, open, dotted, thick. dir stays "' + now.dir + '".'
            ).then(function (out) {
            var g = out && out.graph;
            if (!g || !Array.isArray(g.nodes) || !Array.isArray(g.edges)) throw { code: 'invalid_json' };
            var ident = function (x) { return String(x).replace(/[^\w-]/g, ''); }, ids = {};
            var boxes = g.nodes.filter(function (n) { return n && ident(n.id) && !ids[ident(n.id)] && (ids[ident(n.id)] = true); }).map(function (n) { return { id: ident(n.id), label: String(n.label || n.id), shape: n.shape in { rect: 1, round: 1, stadium: 1, diamond: 1, hexagon: 1, circle: 1, cylinder: 1 } ? n.shape : 'rect', colour: PALETTE[n.colour] ? n.colour : '' }; });
            var arrows = g.edges.filter(function (e) { return e && ids[ident(e.from)] && ids[ident(e.to)]; }).map(function (e) { return { from: ident(e.from), to: ident(e.to), label: String(e.label || ''), style: { arrow: 1, open: 1, dotted: 1, thick: 1 }[e.style] ? e.style : 'arrow' }; });
            if (!boxes.length) throw { code: 'invalid_json' };
            ed.load({ dir: now.dir, nodes: boxes, edges: arrows }, null, 'claude');
            said.hidden = false; said.textContent = label + ': ' + String(out.reply || 'Done.') + ' Undo takes it back; Save as my version keeps it.';
            if (box.value === draft) box.value = '';
          }).catch(function (e) {
            said.hidden = false;
            said.textContent = e && e.code === 'rate_limited' ? label + ' is busy: try again in a minute.' : e && e.code === 'not_granted' ? 'Asking ' + label + ' is not allowed in this view.' : label + ' could not change it this time. Try saying it another way.';
          }).then(function () { go.disabled = false; go.textContent = 'Ask'; });
        }
        go.addEventListener('click', ask);
        box.addEventListener('keydown', function (ev) { if (ev.key === 'Enter') { ask(); ev.preventDefault(); } ev.stopPropagation(); });
      });
      figs.push({ key: key, f: f, pick: pick, save: saveBtn, editor: ed, ask: askBtn, refresh: function (next) { f = next; }, preview: function (graph, fingerprint) { source = fingerprint; ed.load(graph, null, 'claude'); }, restore: function (payload) { source = payload.source; ed.load(payload.entry ? payload.entry.graph : payload.graph, payload.entry ? payload.entry.pos : null); if (payload.text) { askBtn.click(); bar.querySelector('input[type=text]').value = payload.text; } } });
    });

    showPreserved();

    // the document's choices. In a step, a pick waits on the page until the step's Approve saves them all at once,
    // and that save wakes the session; a choice outside any step is saved as it is picked.
    var sets = [], pending = {};
    try { pending = JSON.parse(sessionStorage.getItem(STASH + ':choices') || '{}'); } catch (e) { toast('Could not restore staged choices.'); }
    function stashChoices() { try { sessionStorage.setItem(STASH + ':choices', JSON.stringify(pending)); } catch (e) { toast('Keep this page open to retain staged choices.'); } }
    var order = [].slice.call(document.querySelectorAll('[role=tabpanel][data-step]')).map(function (p) { return p.dataset.step; });
    function stepOf(el) { var p = el.closest && el.closest('[role=tabpanel][data-step]'); return p ? p : null; }
    document.querySelectorAll('fieldset.choice').forEach(function (set) {
      var key = set.dataset.key, kind = set.dataset.kind, top = set.dataset.max ? Number(set.dataset.max) : null;
      var panel = stepOf(set), open = !panel || panel.classList.contains('current');
      var buttons = [].slice.call(set.querySelectorAll('button[data-value]')), boxes = [].slice.call(set.querySelectorAll('input[type=checkbox]'));
      function value() {
        if (kind === 'some') return boxes.filter(function (x) { return x.checked; }).map(function (x) { return x.value; });
        var on = buttons.filter(function (b) { return b.getAttribute('aria-pressed') === 'true'; })[0];
        return on ? on.dataset.value : null;
      }
      function show(v) {
        if (kind === 'some') boxes.forEach(function (b) { b.checked = Array.isArray(v) && v.indexOf(b.value) >= 0; });
        else buttons.forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.value === v)); });
      }
      function limit() {
        var can = writable && !(st._document && st._document.frozen) && open && !(panel && st.approved && st.approved[panel.dataset.step]);
        var n = boxes.filter(function (b) { return b.checked; }).length;
        boxes.forEach(function (b) { b.disabled = !can || (top !== null && !b.checked && n >= top); });
        buttons.forEach(function (b) { b.disabled = !can; });
      }
      function pick(v, label) {
        if (panel) { pending[key] = v; stashChoices(); set.classList.add('changed'); return; }
        save({ pick: { key: key, entry: { by: me, at: new Date().toISOString(), value: v } } },
             function () { toast('Saved: ' + label + '. Claude reads it when its session picks it up.'); });
      }
      buttons.forEach(function (b) {
        b.addEventListener('click', function () { if (writable) { show(b.dataset.value); pick(b.dataset.value, b.textContent); } });
      });
      boxes.forEach(function (b) {
        b.addEventListener('change', function () {
          if (!writable) return;
          limit();
          pick(value(), (set.querySelector('legend') || {}).textContent || key);
        });
      });
      sets.push({ key: key, show: show, limit: limit, value: value, panel: panel, set: set,
                  label: function () { var l = set.querySelector('legend'); return (l ? l.firstChild.textContent : key).trim(); } });
    });
    // "Ask Claude about this": on each option, and on a section that names its subjects (a plan's tickets)
    var askers = [];
    function asker(where, subjects, title) {
      var row = make('div', { class: 'ask-row' }), open = make('button', { type: 'button', class: 'ask-open' }, title);
      row.appendChild(open); where.appendChild(row);
      open.addEventListener('click', function () {
        if (row.querySelector('textarea')) { row.querySelector('textarea').focus(); return; }
        var pick = null;
        if (subjects.length > 1) {
          pick = make('select', { 'aria-label': 'About' });
          subjects.forEach(function (x) { pick.appendChild(make('option', { value: x }, x)); });
          row.appendChild(pick);
        }
        var area = make('textarea', { 'aria-label': 'Your question', placeholder: 'For example: why this order? What would you cut?' });
        var go = make('button', { type: 'button', class: 'go' }, 'Send to ' + label);
        row.appendChild(area); row.appendChild(go); area.focus();
        go.addEventListener('click', function () {
          var draft = area.value, text = draft.trim(); if (!text) { area.focus(); return; }
          go.disabled = true;
          save({ ask: { by: me, at: new Date().toISOString(), figure: null, version: null, about: pick ? pick.value : subjects[0], text: text } },
               function () { if (area.value === draft) area.value = ''; go.disabled = false; toast('Sent. Claude answers in Talk to Claude when its session picks it up.'); });
        });
      });
      askers.push(open);
    }
    document.querySelectorAll('article.opt[data-about]').forEach(function (a) { asker(a, [a.dataset.about], 'Ask ' + label + ' about this option'); });
    document.querySelectorAll('.ask-about').forEach(function (box) {
      var subjects = []; try { subjects = JSON.parse(box.querySelector('script').textContent); } catch (e) {}
      if (!subjects.length) return;
      box.hidden = false; asker(box, subjects, 'Ask ' + label + ' about a ticket');
    });

    var approves = [].slice.call(document.querySelectorAll('button.approve[data-approve]'));
    approves.forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (!writable) return;
        var name = btn.dataset.approve, at = new Date().toISOString();
        var mine = sets.filter(function (x) { return x.panel && x.panel.dataset.step === name; });
        var picks = mine.map(function (x) { return { key: x.key, entry: { by: me, at: at, value: x.value() } }; });
        var said = mine.map(function (x) { var v = x.value(); return x.label() + ': ' + (Array.isArray(v) ? (v.length ? v.join(', ') : 'none') : (v === null ? 'none' : v)); });
        btn.disabled = true;
        save({ picks: picks, approve: { step: name, by: me, at: at },
               ask: { by: me, at: at, figure: null, version: null, step: name, approve: true, text: 'Approved ' + name + (said.length ? ': ' + said.join('; ') : '') } },
             function () {
               mine.forEach(function (x, i) { if (JSON.stringify(pending[x.key]) === JSON.stringify(picks[i].entry.value)) { delete pending[x.key]; x.set.classList.remove('changed'); } }); stashChoices();
               toast('Approved ' + name + '. Claude takes it from here when its session picks it up.');
             });
      });
    });
    var changes = [].slice.call(document.querySelectorAll('button.change[data-change]'));
    changes.forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (!writable) return;
        btn.disabled = true;
        var name = btn.dataset.change, from = order.indexOf(name);
        save({ unapprove: from < 0 ? [name] : order.slice(from),
               ask: { by: me, at: new Date().toISOString(), figure: null, version: null, step: name, text: 'Change the step ' + name } },
             function () { toast('Sent. Claude reopens ' + name + ' when its session picks it up.'); btn.disabled = false; });
      });
    });

    function render() {
      sets.forEach(function (x) {
        var p = st.picks && st.picks[x.key];
        if (x.key in pending) x.show(pending[x.key]); else if (p) x.show(p.value);
        x.limit();
      });
      changes.forEach(function (btn) { btn.hidden = !writable || !!(st._document && st._document.frozen); });
      askers.forEach(function (btn) { btn.hidden = !writable; });
      approves.forEach(function (btn) {
        var done = st.approved && st.approved[btn.dataset.approve], hint = btn.parentNode.querySelector('.approve-hint');
        btn.hidden = !writable;
        btn.disabled = !writable || !!done || !!(st._document && st._document.frozen);
        btn.textContent = done ? 'Approved' : 'Approve ' + btn.dataset.approve;
        if (hint) hint.textContent = !writable ? 'Reply ok in the chat to take these, or say what to change.'
          : done ? 'Waiting for ' + label + ': it writes these into its files and opens the next step.'
          : 'Pick here, then Approve: that saves your picks and queues a request for ' + label + '.';
      });
      document.querySelectorAll('.choice-hint').forEach(function (h) {
        h.textContent = writable ? 'What you pick here is saved to this page, and ' + label + ' reads it. You can also answer in the chat.' : 'Reply ok in the chat to take these, or say what to change.';
      });
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
            x.pick.appendChild(make('option', { value: id }, (who[id] || 'Someone') + (id === me ? 'r version' : "'s version") + ((v.via || []).indexOf('claude') >= 0 ? ' (with ' + label + ')' : '')));
          });
          x.pick.value = was && (was === 'original' || x.f.versions[was]) ? was : 'original';
          x.save.disabled = !writable; x.ask.disabled = !writable;
          x.save.title = writable ? '' : 'Ask the owner for edit access to save';
        });
        var oldForm = panel.querySelector('form');
        [].slice.call(panel.children).forEach(function (child) { if (child !== oldForm) child.remove(); });
        panel.hidden = false;
        panel.insertBefore(make('h2', {}, 'Talk to ' + label), oldForm);
        panel.insertBefore(make('p', { class: 'who' }, 'Questions and change requests for ' + label + '. It answers here and may update the diagrams; your saved versions stay.'), oldForm);
        var list = make('ol');
        st.asks.forEach(function (a) {
          var li = make('li', { class: a.answer ? 'answered' : '' });
          var fig = a.figure && st.figures[a.figure];
          li.appendChild(make('span', { class: 'who' }, (who[a.by] || 'Someone') + (fig ? ' on "' + (fig.title || 'figure ' + a.figure) + '"' : '') + (a.about ? ' about "' + a.about + '"' : '') + (a.version ? ', with ' + (a.version === me ? 'your' : 'their') + ' version' : '')));
          li.appendChild(make('span', {}, a.text));
          li.appendChild(a.answer ? make('span', { class: 'reply' }, label + ': ' + a.answer) : make('span', { class: 'who' }, 'Waiting for ' + label));
          if (a.result && fig) {
            var preview = make('button', {type: 'button'}, 'Preview proposal');
            preview.addEventListener('click', function () {
              var target = figs.filter(function (x) { return x.key === String(a.figure); })[0];
              if (!target || target.f.source !== a.source) { toast('Figure source changed. This proposal belongs to an older source.'); return; }
              target.preview(a.result, a.source);
              toast('Preview only. Save as my version keeps this proposal.');
            });
            li.appendChild(preview);
          }
          list.appendChild(li);
        });
        if (st.asks.length) panel.insertBefore(list, oldForm);
        if (!writable) { if (oldForm) oldForm.remove(); panel.appendChild(make('p', { class: 'live-note' }, 'You can read this page. To save versions or ask ' + label + ', the owner needs to give you edit access.')); return; }
        if (oldForm) { return; }
        var form = make('form'), area = make('textarea', { 'aria-label': 'Your question or request', placeholder: 'For example: B looks too big for a first version. What would you cut?' });
        var row = make('div', { class: 'row' }), about = make('select', { 'aria-label': 'About' }), send = make('button', { type: 'submit', class: 'go' }, 'Send to ' + label);
        about.appendChild(make('option', { value: '' }, 'About the whole page'));
        figs.forEach(function (x) { about.appendChild(make('option', { value: x.key }, 'About: ' + (x.f.title || 'figure ' + x.key) + (x.f.versions[me] ? ' (with my version)' : ''))); });
        row.appendChild(about); row.appendChild(send);
        form.appendChild(area); form.appendChild(row); panel.appendChild(form);
        form.addEventListener('submit', function (ev) {
          ev.preventDefault();
          var draft = area.value, text = draft.trim(); if (!text) { area.focus(); return; }
          var key = about.value, fig = key && st.figures[key];
          send.disabled = true;
          save({ ask: { by: me, at: new Date().toISOString(), figure: key || null, version: fig && fig.versions[me] ? me : null, text: text } },
               function () { if (area.value === draft) area.value = ''; send.disabled = false; toast('Sent. Claude answers here when its session picks it up.'); });
        });
      });
    }
    render().then(flush);
    function poll() {
      if (stopped) return;
      var observed = epoch;
      (provider.metadata ? provider.metadata() : Promise.resolve(null)).then(function (meta) {
        if (meta && pageRevision && meta.revision !== pageRevision) {
          update.hidden = false;
          status.textContent = label + ' • New page available; your edits are kept';
          fetch('./', {cache: 'no-store'}).then(function (r) { return r.text(); }).then(function (text) { updatePage = text; }).catch(function () { status.textContent = 'Could not fetch the update; your edits are kept.'; });
        }
        if (meta) pageRevision = meta.revision;
        if (saving) return null;
        return provider.readState();
      }).then(function (got) {
        delay = 2000;
        if (got && !saving && observed === epoch) { accept(got); render(); }
        if (update.hidden && !queue.length) status.textContent = label + (writable ? ' • Connected' : ' • Read only');
      }).catch(function () {
        status.textContent = 'Connection lost • Retrying; your edits are kept'; delay = Math.min(delay * 2, 30000);
      }).then(function () { if (!stopped) timer = setTimeout(poll, delay); });
    }
    window.addEventListener('pagehide', function () { stopped = true; clearTimeout(timer); });
    if (provider.local) poll(); else timer = setTimeout(poll, 2000);
  }
})();
