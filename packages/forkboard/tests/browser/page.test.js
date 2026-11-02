// Forkboard's page in a real browser (Chromium through Playwright): the editor, phone width, and the live layer
// with a stand-in for the artifact runtime, including a save that clashes with someone else's.
// usage: node --test page.test.js   (needs python3 on PATH and playwright; see package.json)
const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
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
  await page.keyboard.press('Control+a');
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
