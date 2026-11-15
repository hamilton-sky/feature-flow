(function () {
  function hash(text) {
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)).then(function (b) {
      return Array.from(new Uint8Array(b), function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
    });
  }
  function request(path, options) {
    var controller = new AbortController(), timer = setTimeout(function () { controller.abort(); }, 4000);
    return fetch(path, Object.assign({cache: 'no-store', signal: controller.signal}, options)).then(function (r) {
      return r.json().then(function (body) {
        if (!r.ok) throw {code: r.status === 412 ? 'conflict' : 'unavailable', message: body.error};
        return {state: body, revision: r.headers.get('ETag')};
      });
    }).finally(function () { clearTimeout(timer); });
  }
  window.ForkboardProviders = function (wrap) {
    var local = wrap.dataset.provider === 'local';
    var label = wrap.dataset.agentLabel || (local ? 'Codex' : 'Claude');
    if (local) {
      return Promise.resolve({local: true, label: label,
        readState: function () { return request('state.json'); },
        identity: function (st) { return Promise.resolve(st.identity && st.identity.id); },
        profiles: function (ids) { return Promise.resolve(ids.reduce(function (o, id) { o[id] = {name: 'Reviewer'}; return o; }, {})); },
        saveChange: function (envelope, revision) {
          return request('api/change', {method: 'POST', headers: {'Content-Type': 'application/json', 'If-Match': revision}, body: JSON.stringify(envelope)});
        },
        metadata: function () { return request('api/page').then(function (r) { return r.state; }); }
      });
    }
    if (!window.claude || !window.claude.use) return Promise.resolve(null);
    function use(name) { return window.claude.use(name).catch(function () { return null; }); }
    return Promise.all([use('artifact'), use('user'), use('sample')]).then(function (caps) {
      var artifact = caps[0], user = caps[1], sample = caps[2];
      if (!artifact) return null;
      return {local: false, label: label,
        readState: function () { return fetch('state.json', {cache: 'no-store'}).then(function (r) {
          if (!r.ok) throw {code: 'unavailable'};
          return r.text();
        }).then(function (text) { return hash(text).then(function (sha) { return {state: JSON.parse(text), revision: sha}; }); }); },
        identity: function () { return user ? user.id().catch(function () { return null; }) : Promise.resolve(null); },
        profiles: function (ids) { return user ? user.profiles(ids).catch(function () { return {}; }) : Promise.resolve({}); },
        propose: sample ? function (prompt) { return sample.json(prompt, {modelTier: 'default'}); } : null,
        saveChange: function (envelope, revision, state, merge) {
          if (state._nativeOperations && state._nativeOperations[envelope.id]) return Promise.resolve({state: state, revision: revision});
          var next = JSON.parse(JSON.stringify(state)); merge(next, envelope.change);
          next._nativeOperations = next._nativeOperations || {}; next._nativeOperations[envelope.id] = true;
          if (envelope.change.ask) next.asks[next.asks.length - 1].id = envelope.id;
          var body = JSON.stringify(next, null, 1) + '\n';
          return artifact.publish({'state.json': {content: body, contentType: 'application/json', ifMatch: revision}}).then(function (res) {
            var sha = res && res.shas && res.shas['state.json'];
            return (sha ? Promise.resolve(sha) : hash(body)).then(function (rev) { return {state: next, revision: rev}; });
          });
        }
      };
    });
  };
})();
