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
  server = http.createServer((req, res) => {  // serves the live folder, as the artifact host serves its files
    const file = path.join(dir, 'live', decodeURIComponent(req.url.split('?')[0]).replace(/^\/+/, '') || 'index.html');
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
  await page.waitForSelector('figure.graph g.node');
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
