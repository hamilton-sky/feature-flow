// Forkboard's page in a real browser (Chromium through Playwright): the editor, phone width, and the live layer
// with a stand-in for the artifact runtime, including a save that clashes with someone else's.
// usage: node --test page.test.js   (needs python3 on PATH and playwright; see package.json)
const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync, spawn } = require('node:child_process');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const { chromium } = require('playwright');

const PACKAGE = path.resolve(__dirname, '..', '..');
const FIXTURES = path.resolve(__dirname, '..', 'fixtures');
const PYTHON = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
let dir, browser, server, base;

function forkboard(...args) {
  return execFileSync(PYTHON, ['-m', 'forkboard', ...args], { env: { ...process.env, PYTHONPATH: PACKAGE }, encoding: 'utf-8' });
}

before(async () => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), 'forkboard-'));
  forkboard('render', path.join(FIXTURES, 'csv.json'), '--out', path.join(dir, 'page.html'));
  forkboard('live', path.join(FIXTURES, 'sketch.json'), path.join(dir, 'live'));
  forkboard('live', path.join(FIXTURES, 'steps.json'), path.join(dir, 'live', 'steps'));
  server = http.createServer((req, res) => {  // serves the live folder, as the artifact host serves its files
    let file = path.join(dir, 'live', decodeURIComponent(req.url.split('?')[0]).replace(/^\/+/, '') || 'index.html');
    if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
    if (!file.startsWith(path.join(dir, 'live')) || !fs.existsSync(file)) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'content-type': file.endsWith('.json') ? 'application/json' : 'text/html; charset=utf-8' });
    res.end(fs.readFileSync(file));
  });
  await new Promise((done) => server.listen(0, '127.0.0.1', done));
  base = 'http://127.0.0.1:' + server.address().port + '/';
  browser = await chromium.launch();
});

after(async () => {
  if (browser) await browser.close();
  if (server) server.close();
  fs.rmSync(dir, { recursive: true, force: true });
});

async function open(url, options = {}) {
  const context = await browser.newContext({ viewport: options.viewport || { width: 1280, height: 900 } });
  if (options.init) await context.addInitScript(options.init);
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error' && !/fonts\.g|jsdelivr|ERR_/.test(m.text())) errors.push(m.text()); });
  await page.route(/^https:\/\//, (route) => route.abort());  // no fonts or mermaid from the network: the page must cope
  await page.goto(url);
  await page.waitForSelector('figure.graph g.node', { state: 'attached' });  // a figure may sit in a closed tab
  return { page, errors, context };
}

const counts = (fig) => fig.evaluate((f) => [f.querySelectorAll('g.node').length, f.querySelectorAll('g.edge').length]);

test('the editor adds, connects, renames, deletes, undoes and resets', async () => {
  const { page, errors, context } = await open('file://' + path.join(dir, 'page.html'));
  const fig = page.locator('figure.graph').first();
  assert.deepEqual(await counts(fig), [3, 3]);
  await fig.locator('[data-act=add]').click();
  await page.keyboard.type('Audit log');
  await page.keyboard.press('Enter');
  assert.deepEqual(await counts(fig), [4, 3]);
  assert.ok((await fig.locator('g.node text').allTextContents()).includes('Audit log'));
  await fig.locator('g.node').first().click();
  await fig.locator('[data-act=connect]').click();
  await fig.locator('g.node').last().click();
  assert.deepEqual(await counts(fig), [4, 4]);
  await fig.locator('g.node').nth(1).dblclick();
  await page.keyboard.press('ControlOrMeta+a');
  await page.keyboard.type('Renamed');
  await page.keyboard.press('Enter');
  assert.ok((await fig.locator('g.node text').allTextContents()).includes('Renamed'));
  await fig.locator('g.node').nth(1).click();
  await page.keyboard.press('Delete');
  const [nodes] = await counts(fig);
  assert.equal(nodes, 3);
  await page.keyboard.press('Control+z');
  assert.equal((await counts(fig))[0], 4);
  await page.keyboard.press('Control+Shift+z');
  assert.equal((await counts(fig))[0], 3);
  assert.ok(await fig.locator('.edited').isVisible());
  await fig.locator('[data-act=reset]').click();
  assert.deepEqual(await counts(fig), [3, 3]);
  assert.deepEqual(errors, []);
  await context.close();
});

const boxes = (fig) => fig.evaluate((f) => [...f.querySelectorAll('g.node')].map((n) => n.getBoundingClientRect())
  .map((r) => ({ x: r.x, y: r.y, w: r.width, h: r.height })));
const overlap = (a, b) => a.x < b.x + b.w - 1 && b.x < a.x + a.w - 1 && a.y < b.y + b.h - 1 && b.y < a.y + a.h - 1;

test('Arrange lays the boxes out four ways, without overlaps, and undo puts them back', async () => {
  const { page, errors, context } = await open('file://' + path.join(dir, 'page.html'));
  const fig = page.locator('figure.graph').first();
  await fig.locator('[data-act=add]').click();  // five boxes, so radial and grid have something to arrange
  await page.keyboard.type('Audit log'); await page.keyboard.press('Enter');
  await fig.locator('[data-act=add]').click();
  await page.keyboard.type('Mailer'); await page.keyboard.press('Enter');
  const where = () => fig.evaluate((f) => f.editor.get());
  for (const how of ['radial', 'grid', 'TD', 'LR']) {
    const before = await where();
    await fig.locator('[data-act=arrange]').click();
    await fig.locator('[data-arrange=' + how + ']').click();
    const after = await where();
    assert.notDeepEqual(after.pos, before.pos, how);
    assert.deepEqual(await counts(fig), [5, 3], how);
    const b = await boxes(fig);
    for (let i = 0; i < b.length; i++) for (let j = i + 1; j < b.length; j++) assert.ok(!overlap(b[i], b[j]), how + ': boxes ' + i + ' and ' + j + ' overlap');
    if (how === 'TD' || how === 'LR') assert.equal(after.graph.dir, how);
    await page.keyboard.press('Control+z');
    assert.deepEqual((await where()).pos, before.pos, how + ' undone');
    await page.keyboard.press('Control+Shift+z');
  }
  assert.deepEqual(errors, []);
  await context.close();
});

test('every theme draws the page, and a theme shapes the boxes', async () => {
  const names = forkboard('themes').trim().split('\n').map((l) => l.split(/\s+/)[0]);
  assert.ok(names.length >= 6);
  for (const name of names) {
    const file = path.join(dir, name + '.html');
    forkboard('render', path.join(FIXTURES, 'csv.json'), '--theme', name, '--out', file);
    const { page, errors, context } = await open('file://' + file, { viewport: { width: 390, height: 844 } });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), 390, name);
    const look = await page.locator('figure.graph g.node rect.plain').first().evaluate((r) => {
      const s = getComputedStyle(r); return { rx: s.rx, filter: s.filter, stroke: s.strokeWidth };
    });
    if (name === 'sketch') assert.match(look.filter, /url\(.*fb-rough/, name);
    if (name === 'terminal') assert.equal(look.rx, '0px', name);
    if (name === 'route') assert.deepEqual([look.rx, look.filter], ['8px', 'none'], name);
    assert.deepEqual(errors, [], name);
    await context.close();
  }
});

test('at phone width nothing scrolls sideways', async () => {
  const { page, errors, context } = await open('file://' + path.join(dir, 'page.html'), { viewport: { width: 390, height: 844 } });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), 390);
  assert.deepEqual(errors, []);
  await context.close();
});

// a stand-in for the artifact runtime: publish records each state.json saved, and the second call clashes
function runtime() {
  const calls = () => Number(sessionStorage.getItem('calls') || 0);
  window.__saved = () => JSON.parse(sessionStorage.getItem('saved') || '[]');
  const mocks = {
    artifact: {
      publish: async (files) => {
        sessionStorage.setItem('calls', calls() + 1);
        if (calls() === 2) throw { code: 'conflict' };
        sessionStorage.setItem('saved', JSON.stringify(window.__saved().concat([JSON.parse(files['state.json'].content)])));
        return { version: 'v' + calls(), shas: { 'state.json': 'sha' + calls() } };
      },
    },
    user: { id: async () => 'u_me', profiles: async (ids) => Object.fromEntries([].concat(ids).map((id) => [id, { id, name: 'Me' }])) },
    sample: null,
  };
  window.claude = { use: (name) => Promise.resolve(mocks[name] || null) };
}

test('the live page saves a version, and a clash reloads and saves the change again', async () => {
  const { page, errors, context } = await open(base, { init: runtime });
  const fig = page.locator('figure.graph').first();
  assert.equal(await page.locator('.live-bar').count(), 2);
  await fig.locator('g.node').nth(1).dblclick();
  await page.keyboard.press('Control+a');
  await page.keyboard.type('Export API');
  await page.keyboard.press('Enter');
  await fig.locator('.live-bar input[type=checkbox]').check();
  assert.match(await fig.locator('.diff-sum').textContent(), /1 renamed/);
  await fig.locator('.live-bar button.go').click();  // save 1 goes through
  await page.waitForFunction(() => window.__saved().length === 1);
  const first = await page.evaluate(() => window.__saved()[0]);
  assert.deepEqual(Object.keys(first.figures['1'].versions), ['u_me']);
  await page.locator('#talk textarea').fill('Is a cache worth it?');
  await page.locator('#talk button.go').click();  // save 2 clashes: the page reloads, and save 3 carries the ask
  await page.waitForFunction(() => window.__saved().length === 2, null, { timeout: 10000 });
  const last = await page.evaluate(() => window.__saved()[1]);
  assert.deepEqual(last.asks.map((a) => a.text), ['Is a cache worth it?']);
  assert.equal(await page.evaluate(() => sessionStorage.getItem('calls')), '3');
  assert.deepEqual(errors, []);
  await context.close();
});

test('a live page with steps shows them as tabs, saves picks only on Approve, and Change takes an approval back', async () => {
  const { page, errors, context } = await open(base + 'steps/', { init: runtime });
  assert.equal(await page.locator('[role=tabpanel]:not([hidden])').getAttribute('data-step'), 'Team');  // the current step is open
  const approve = page.locator('button.approve[data-approve=Team]');
  await page.waitForFunction(() => !document.querySelector('button.approve').disabled);
  const lens = page.locator('fieldset.choice[data-key=lens]');
  await lens.locator('input[value=security]').check();  // a pick waits for Approve
  assert.ok(await lens.locator('input[value=artistic]').isDisabled());  // up to 2
  assert.equal(await page.evaluate(() => window.__saved().length), 0);
  await approve.click();  // save 1: the step's picks, its approval and an ask, at once
  await page.waitForFunction(() => window.__saved().length === 1);
  const first = await page.evaluate(() => window.__saved()[0]);
  assert.deepEqual(first.picks.lens.value, ['ux', 'security']);
  assert.equal(first.approved.Team.by, 'u_me');
  const ask = first.asks.pop();
  assert.deepEqual([ask.step, ask.approve, ask.text], ['Team', true, 'Approved Team: Lenses: ux, security']);
  await page.waitForFunction(() => document.querySelector('button.approve').textContent === 'Approved');
  assert.ok(await approve.isDisabled());
  assert.ok(await lens.locator('input[value=ux]').isDisabled());  // an approved step waits for Claude
  await page.locator('#tab-2').focus();
  await page.keyboard.press('ArrowLeft');  // the tabs move with the arrow keys
  assert.equal(await page.locator('[role=tabpanel]:not([hidden])').getAttribute('data-step'), 'Style');
  assert.ok(await page.locator('fieldset.choice[data-key=web] button[data-value=light]').isDisabled());  // a done step is changed with Change
  await page.locator('button.change[data-change=Style]').click();  // save 2 clashes, the reload saves it again
  await page.waitForFunction(() => window.__saved().length === 2, null, { timeout: 10000 });
  const second = await page.evaluate(() => window.__saved()[1]);
  assert.deepEqual(second.approved, {});  // Style and every step after it
  assert.deepEqual([second.asks.at(-1).step, second.asks.at(-1).text], ['Style', 'Change the step Style']);
  await page.locator('#tab-3').click();  // Options: ask about one option, and about one of a section's subjects
  await page.locator('article.opt[data-about="B. In the background"] button.ask-open').click();
  await page.locator('article.opt[data-about="B. In the background"] textarea').fill('Is a queue worth it?');
  await page.locator('article.opt[data-about="B. In the background"] .ask-row button.go').click();
  await page.waitForFunction(() => window.__saved().length === 3);
  const third = (await page.evaluate(() => window.__saved()[2])).asks.at(-1);
  assert.deepEqual([third.about, third.text], ['B. In the background', 'Is a queue worth it?']);
  await page.locator('.ask-about button.ask-open').click();
  await page.locator('.ask-about select').selectOption('02 CSV writer');
  await page.locator('.ask-about textarea').fill('Why after 01?');
  await page.locator('.ask-about .ask-row button.go').click();
  await page.waitForFunction(() => window.__saved().length === 4);
  assert.equal((await page.evaluate(() => window.__saved()[3])).asks.at(-1).about, '02 CSV writer');
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth) <= 1280, true);
  assert.deepEqual(errors, []);
  await context.close();
});


async function localServer(fixture = 'sketch', label = 'Codex') {
  const folder = fs.mkdtempSync(path.join(dir, 'local-'));
  forkboard('live', path.join(FIXTURES, fixture + '.json'), folder, '--provider', 'local', '--agent-label', label);
  const proc = spawn(PYTHON, ['-u', '-m', 'forkboard', 'serve', folder], { env: { ...process.env, PYTHONPATH: PACKAGE } });
  const url = await new Promise((resolve, reject) => {
    let output = '';
    proc.stdout.on('data', chunk => { output += chunk; const m = output.match(/http:\/\/127\.0\.0\.1:\d+\//); if (m) resolve(m[0]); });
    proc.on('exit', code => reject(new Error('server exited ' + code)));
  });
  return { folder, url, stop: () => proc.kill() };
}

test('local queue, reply and explicit proposal preserve dirty edits and typed text during polling', async () => {
  const local = await localServer('sketch', '<Codex>');
  try {
    const { page, errors, context } = await open(local.url);
    const fig = page.locator('figure.graph').first();
    await page.locator('#talk textarea').fill('Unsent question');
    await fig.getByRole('button', { name: 'Ask <Codex> to change it', exact: true }).click();
    await fig.locator('.live-bar input[type=text]').fill('Add a cache');
    await fig.getByRole('button', { name: 'Ask', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('#talk').textContent.includes('Waiting for <Codex>'));
    const state = () => JSON.parse(fs.readFileSync(path.join(local.folder, 'state.json')));
    assert.equal(state().asks.length, 1);
    assert.equal(state().asks[0].kind, 'diagram');
    assert.ok(state().asks[0].source);
    await fig.locator('[data-act=add]').click(); await page.keyboard.type('Dirty'); await page.keyboard.press('Enter');
    const dirty = await fig.evaluate(f => f.editor.get());
    const proposal = state().asks[0].graph;
    proposal.nodes[0].label = 'Proposed';
    const file = path.join(local.folder, 'proposal.json'); fs.writeFileSync(file, JSON.stringify(proposal));
    forkboard('answer-graph', local.folder, '1', file);
    await page.getByRole('button', { name: 'Preview proposal', exact: true }).waitFor();
    assert.deepEqual(await fig.evaluate(f => f.editor.get()), dirty);
    assert.equal(await page.locator('#talk textarea').inputValue(), 'Unsent question');
    assert.equal(Object.keys(state().figures['1'].versions).length, 0);
    await page.getByRole('button', { name: 'Preview proposal', exact: true }).click();
    assert.ok((await fig.locator('g.node text').allTextContents()).includes('Proposed'));
    assert.equal(Object.keys(state().figures['1'].versions).length, 0);
    await fig.getByRole('button', { name: 'Save as my version', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('.toast')?.textContent.includes('Saved'));
    assert.equal(Object.keys(state().figures['1'].versions).length, 1);
    assert.deepEqual(errors, []);
    await context.close();
  } finally { local.stop(); }
});

test('local staged list choices approve atomically and survive polling', async () => {
  const local = await localServer('steps');
  try {
    const { page, errors, context } = await open(local.url);
    const lens = page.locator('fieldset[data-key=lens]');
    await page.waitForFunction(() => !document.querySelector('button.approve').disabled);
    await lens.locator('input[value=security]').check();
    await page.waitForTimeout(2400);
    assert.ok(await lens.locator('input[value=security]').isChecked());
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(local.folder, 'state.json'))).picks, {});
    await page.locator('button.approve').click();
    await page.waitForFunction(() => document.querySelector('button.approve').textContent === 'Approved');
    const st = JSON.parse(fs.readFileSync(path.join(local.folder, 'state.json')));
    assert.deepEqual(st.picks.lens.value, ['ux', 'security']);
    assert.equal(st.asks.length, 1);
    assert.equal(st.approved.Team.by, st.identity.id);
    assert.deepEqual(errors, []);
    await context.close();
  } finally { local.stop(); }
});

test('native capability denial becomes accessible read only and native generation remains a deliberate save', async () => {
  function denied() {
    window.claude = {use: async name => name === 'artifact' ? {publish: async () => {throw {code: 'not_granted'};}} : name === 'user' ? {id: async () => 'me', profiles: async () => ({})} : null};
  }
  let opened = await open(base, {init: denied});
  await opened.page.locator('.live-bar button.go').first().click();
  await opened.page.waitForFunction(() => document.querySelector('.live-connection').textContent.includes('Read only'));
  assert.ok(await opened.page.locator('.live-bar button.go').first().isDisabled());
  assert.ok(await opened.page.locator('#talk .live-note').isVisible());
  assert.deepEqual(opened.errors, []);
  await opened.context.close();
  function nativeSample() {
    window.__publications = [];
    window.__prompt = null;
    window.claude = {use: async name => ({
      artifact: {publish: async files => { window.__publications.push(JSON.parse(files['state.json'].content)); return {shas: {'state.json': 'saved'}}; }},
      user: {id: async () => 'me', profiles: async () => ({})},
      sample: {json: async (prompt, options) => {window.__prompt = [prompt, options]; return {graph: {dir: 'TD', nodes: [{id: 'new', label: 'Native proposal', shape: 'bogus'}], edges: []}, reply: 'Proposed.'};}}
    })[name]};
  }
  opened = await open(base, {init: nativeSample});
  const fig = opened.page.locator('figure.graph').first();
  await fig.getByRole('button', {name: 'Ask Claude to change it', exact: true}).click();
  await fig.locator('.live-bar input[type=text]').fill('Simplify');
  await fig.getByRole('button', {name: 'Ask', exact: true}).click();
  await opened.page.waitForFunction(() => document.querySelector('figure.graph').textContent.includes('Native proposal'));
  assert.equal(await opened.page.evaluate(() => window.__publications.length), 0);
  assert.equal(await fig.evaluate(f => f.editor.get().graph.dir), 'LR');
  assert.equal(await fig.evaluate(f => f.editor.get().graph.nodes[0].shape), 'rect');
  assert.deepEqual(await opened.page.evaluate(() => window.__prompt[1]), {modelTier: 'default'});
  await fig.getByRole('button', {name: 'Save as my version', exact: true}).click();
  await opened.page.waitForFunction(() => window.__publications.length === 1);
  assert.deepEqual(await opened.page.evaluate(() => window.__publications[0].figures['1'].versions.me.via), ['claude']);
  assert.deepEqual(opened.errors, []);
  await opened.context.close();
});

test('local repeated conflict retains an idempotent queue through reload and serializes retry', async () => {
  const local = await localServer();
  try {
    const {page, context} = await open(local.url);
    let calls = 0, ids = [];
    await page.route('**/api/change', async route => {
      const envelope = route.request().postDataJSON(); ids.push(envelope.id); calls++;
      if (calls <= 2) await route.fulfill({status: 412, contentType: 'application/json', body: JSON.stringify({error: 'concurrent writer'})});
      else await route.continue();
    });
    await page.locator('#talk textarea').fill('Retain this question');
    await page.locator('#talk button.go').click();
    await page.getByRole('button', {name: 'Retry save', exact: true}).waitFor();
    assert.equal(calls, 2);
    assert.equal(ids[0], ids[1]);
    assert.equal(await page.locator('#talk textarea').inputValue(), 'Retain this question');
    await page.reload();
    await page.waitForFunction(() => document.querySelector('#talk')?.textContent.includes('Retain this question'));
    const st = JSON.parse(fs.readFileSync(path.join(local.folder, 'state.json')));
    assert.equal(st.asks.length, 1);
    assert.equal(st.asks[0].id, ids[0]);
    assert.ok(ids.every(id => id === ids[0]));
    await context.close();
  } finally {local.stop();}
});

test('local dirty edits, forms and staged picks survive disconnect and unsafe regeneration', async () => {
  const local = await localServer('steps');
  try {
    const {page, context} = await open(local.url);
    const lens = page.locator('fieldset[data-key=lens]');
    await page.waitForFunction(() => !document.querySelector('button.approve').disabled);
    await lens.locator('input[value=security]').check();
    await page.locator('#talk textarea').fill('Still typing');
    await page.locator('#tab-3').click();
    const fig = page.locator('figure.graph').first();
    await fig.locator('[data-act=add]').click(); await page.keyboard.type('Unsaved'); await page.keyboard.press('Enter');
    const dirty = await fig.evaluate(f => f.editor.get());
    await page.context().setOffline(true);
    // An aborted fetch reports an expected transport console error; state and form retention are the assertions.
    await page.waitForFunction(() => document.querySelector('.live-connection').textContent.includes('Connection lost'));
    assert.deepEqual(await fig.evaluate(f => f.editor.get()), dirty);
    assert.equal(await page.locator('#talk textarea').inputValue(), 'Still typing');
    await page.context().setOffline(false);
    const updated = JSON.parse(fs.readFileSync(path.join(FIXTURES, 'steps.json'))); updated.title = 'Updated review';
    const docFile = path.join(local.folder, 'updated.json'); fs.writeFileSync(docFile, JSON.stringify(updated));
    forkboard('live', docFile, local.folder, '--provider', 'local');
    await page.getByRole('button', {name: 'Review update', exact: true}).waitFor({timeout: 15000});
    assert.deepEqual(await fig.evaluate(f => f.editor.get()), dirty);
    assert.equal(await page.locator('#talk textarea').inputValue(), 'Still typing');
    await page.locator('#tab-2').click();
    assert.ok(await lens.locator('input[value=security]').isChecked());
    await page.locator('button.approve').click();
    await page.waitForFunction(() => document.querySelector('button.approve').textContent === 'Approved');
    await page.locator('#tab-1').click();
    await page.locator('button.change[data-change=Style]').click();
    await page.waitForFunction(() => document.querySelector('#talk').textContent.includes('Change the step Style'));
    const st = JSON.parse(fs.readFileSync(path.join(local.folder, 'state.json')));
    assert.deepEqual(st.approved, {});
    assert.equal(st.asks.length, 2);
    await context.close();
  } finally {local.stop();}
});

test('local figure source change blocks blind conflict replay without discarding the editor', async () => {
  const local = await localServer();
  try {
    const {page, context} = await open(local.url);
    const fig = page.locator('figure.graph').first();
    await fig.locator('[data-act=add]').click(); await page.keyboard.type('Old edit'); await page.keyboard.press('Enter');
    const dirty = await fig.evaluate(f => f.editor.get());
    const doc = JSON.parse(fs.readFileSync(path.join(FIXTURES, 'sketch.json')));
    doc.sections[0].markdown = doc.sections[0].markdown.replace('Tasks table', 'Different source');
    const docFile = path.join(local.folder, 'changed.json'); fs.writeFileSync(docFile, JSON.stringify(doc));
    forkboard('live', docFile, local.folder, '--provider', 'local');
    await fig.getByRole('button', {name: 'Save as my version', exact: true}).click();
    await page.waitForFunction(() => document.querySelector('.live-connection').textContent.includes('Figure source changed'));
    assert.deepEqual(await fig.evaluate(f => f.editor.get()), dirty);
    assert.equal(Object.keys(JSON.parse(fs.readFileSync(path.join(local.folder, 'state.json'))).figures['1'].versions).length, 0);
    assert.ok(await page.getByRole('button', {name: 'Retry save', exact: true}).isVisible());
    await page.locator('#talk textarea').fill('Unrelated question');
    await page.locator('#talk button.go').click();
    await page.getByRole('button', {name: 'Keep edit and unblock saves', exact: true}).click();
    await page.waitForFunction(() => document.querySelector('#talk').textContent.includes('Unrelated question'));
    assert.deepEqual(await fig.evaluate(f => f.editor.get()), dirty);
    await page.reload();
    await page.getByRole('button', {name: 'Restore preserved edit', exact: true}).click();
    assert.deepEqual(await fig.evaluate(f => f.editor.get()), dirty);
    const saved = JSON.parse(fs.readFileSync(path.join(local.folder, 'state.json')));
    assert.deepEqual(saved.asks.map(a => a.text), ['Unrelated question']);
    assert.equal(Object.keys(saved.figures['1'].versions).length, 0);
    await context.close();
  } finally {local.stop();}
});

for (const host of ['local', 'native']) {
  for (const field of ['talk', 'diagram', 'option', 'ticket']) {
    test(`${host} delayed ${field} acknowledgement preserves a newer draft`, async () => {
      const local = host === 'local' ? await localServer('steps') : null;
      function delayedRuntime() {
        window.__saved = [];
        const wait = () => new Promise(resolve => { window.__release = resolve; });
        window.claude = {use: async name => ({
          artifact: {publish: async files => {await wait(); window.__saved.push(JSON.parse(files['state.json'].content)); return {shas: {'state.json': 'saved'}};}},
          user: {id: async () => 'me', profiles: async () => ({})},
          sample: {json: async () => {await wait(); return {graph: {nodes: [{id: 'a', label: 'Proposal'}], edges: []}, reply: 'Done'};}}
        })[name]};
      }
      let context;
      try {
        const opened = await open(local ? local.url : base + 'steps/', local ? {} : {init: delayedRuntime});
        const {page, errors} = opened; context = opened.context;
        let started, release;
        const waiting = new Promise(resolve => {started = resolve;});
        if (local) await page.route('**/api/change', async route => {
          await new Promise(resolve => {release = resolve; started();});
          await route.continue();
        });
        let input, send;
        if (field === 'talk') {
          input = page.locator('#talk textarea'); send = page.locator('#talk button.go');
        } else {
          await page.locator('#tab-3').click();
          if (field === 'diagram') {
            const fig = page.locator('figure.graph').first();
            await fig.getByRole('button', {name: /Ask .* to change it/}).click();
            input = fig.locator('.live-bar input[type=text]'); send = fig.getByRole('button', {name: 'Ask', exact: true});
          } else {
            const box = field === 'option' ? page.locator('article.opt[data-about="B. In the background"]') : page.locator('.ask-about');
            await box.locator('button.ask-open').click();
            input = box.locator('textarea'); send = box.locator('.ask-row button.go');
          }
        }
        await input.fill('  first request  ');
        await send.click();
        if (local) await waiting;
        else await page.waitForFunction(() => !!window.__release);
        await input.fill('second unsent request');
        if (local) release(); else await page.evaluate(() => window.__release());
        await page.waitForFunction(selector => !document.querySelector(selector).disabled,
          field === 'talk' ? '#talk button.go' : field === 'diagram' ? 'figure.graph .live-bar input[type=text] + button' : field === 'option' ? 'article.opt[data-about="B. In the background"] .ask-row button.go' : '.ask-about button.go');
        assert.equal(await input.inputValue(), 'second unsent request');
        if (field !== 'diagram' || local) {
          const saved = local ? JSON.parse(fs.readFileSync(path.join(local.folder, 'state.json'))) : await page.evaluate(() => window.__saved.at(-1));
          assert.deepEqual(saved.asks.map(ask => ask.text), ['first request']);
        }
        // Unchanged drafts, including surrounding whitespace, still clear after success.
        if (local) await page.unroute('**/api/change');
        else await page.evaluate(() => { window.__release = null; });
        await input.fill('  unchanged draft  ');
        await send.click();
        if (!local) {
          await page.waitForFunction(() => !!window.__release);
          await page.evaluate(() => window.__release());
        }
        await page.waitForFunction(element => element.value === '', await input.elementHandle());
        assert.deepEqual(errors, []);
      } finally {
        if (context) await context.close();
        if (local) local.stop();
      }
    });
  }
}

test('delayed approval preserves newer staged list choices', async () => {
  function delayedApproval() {
    window.__saved = [];
    window.claude = {use: async name => ({
      artifact: {publish: async files => {
        await new Promise(resolve => { window.__release = resolve; });
        window.__saved.push(JSON.parse(files['state.json'].content));
        return {shas: {'state.json': 'saved'}};
      }},
      user: {id: async () => 'me', profiles: async () => ({})},
    })[name]};
  }
  const {page, errors, context} = await open(base + 'steps/', {init: delayedApproval});
  try {
    const lens = page.locator('fieldset.choice[data-key=lens]');
    await page.waitForFunction(() => !document.querySelector('button.approve').disabled);
    await lens.locator('input[value=security]').check();
    await page.locator('button.approve[data-approve=Team]').click();
    await page.waitForFunction(() => !!window.__release);
    await lens.locator('input[value=security]').uncheck();
    await lens.locator('input[value=artistic]').check();
    await page.evaluate(() => window.__release());
    await page.waitForFunction(() => document.querySelector('button.approve').textContent === 'Approved');
    assert.deepEqual(await page.evaluate(() => window.__saved[0].picks.lens.value), ['ux', 'security']);
    await page.waitForFunction(() => {
      const key = 'brainstorm-live:' + document.querySelector('.wrap').dataset.page + ':choices';
      return JSON.parse(sessionStorage.getItem(key) || '{}').lens?.includes('artistic');
    }, null, {timeout: 2000});
    await page.reload();
    await page.waitForSelector('.live-bar');
    assert.equal(await lens.locator('input[value=artistic]').isChecked(), true);
    assert.equal(await lens.locator('input[value=security]').isChecked(), false);
    assert.deepEqual(errors, []);
  } finally { await context.close(); }
});
