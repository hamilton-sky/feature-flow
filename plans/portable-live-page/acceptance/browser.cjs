// Real Chromium, only public UI/HTTP/CLI interactions. No private application helpers.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const [base, mode, live, root] = process.argv.slice(2);
const {chromium} = require(path.join(root, 'packages/forkboard/tests/browser/node_modules/playwright'));
function cli(...args) { return execFileSync('python3', ['-m','forkboard',...args], {encoding:'utf8'}); }
const state = () => JSON.parse(fs.readFileSync(path.join(live, 'state.json'), 'utf8'));
async function eventually(fn, ms=5000) {
  const end=Date.now()+ms; let last;
  do { try { if (await fn()) return; } catch(e) {last=e;} await new Promise(r=>setTimeout(r,70)); } while(Date.now()<end);
  throw last || new Error('Observable result did not arrive within '+ms+'ms');
}
(async()=>{
  const browser=await chromium.launch();
  try {
    const context=await browser.newContext();
    const page=await context.newPage();
    page.setDefaultTimeout(5000);
    await page.route(/^https:\/\//, r=>r.abort());
    let payload;
    page.on('request', r=>{if(r.method()==='POST' && r.url().endsWith('/api/change')) payload=r.postDataJSON();});
    await page.goto(base);
    const body=()=>page.locator('body').innerText();
    const question=()=>page.getByRole('textbox',{name:'Your question or request'});
    const figure=()=>page.locator('figure.graph').first();
    async function ask(text='Acceptance question') {
      await question().fill(text);
      await page.getByRole('button',{name:/Send to /}).click();
      await eventually(()=>state().asks.some(a=>a.text===text));
    }
    async function addNode() {
      if(!await figure().isVisible()) await figure().locator('xpath=ancestor::details[1]').locator(':scope > summary').click();
      await figure().locator('[data-act=add]').click();
      await page.keyboard.type('Acceptance node'); await page.keyboard.press('Enter');
    }
    if(['draft','building','done','no-brainstorm'].includes(mode)) {
      await eventually(async()=> /Setup/.test(await body()) && /Plan/.test(await body()));
      if(mode==='draft') {
        assert.match(await body(), /Acceptance ticket/);
        assert.match(await body(), /gate|checks/i);
        assert.ok(await page.locator('fieldset.choice[data-key=profile]').count());
      } else if(mode==='no-brainstorm') {
        assert.match(await body(), /Setup[\s\S]*not used/i);
        assert.match(await body(), /Options[\s\S]*not used/i);
        assert.ok(await question().isVisible());
      } else {
        await eventually(async()=>new RegExp(mode==='building'?'claimed|building|in progress|active':'1 of 1|1/1|all.*done|completed','i').test(await body()));
        assert.match(await body(), /approved|frozen|re-plan/i);
      }
      return;
    }
    await question().waitFor();
    assert.equal(await page.evaluate(()=>typeof window.claude),'undefined');
    assert.match(await body(), new RegExp(mode==='label'?'Review agent':'Codex'));
    if(mode==='label') return;
    if(mode==='save') {
      await addNode();
      await figure().getByRole('button',{name:'Save as my version',exact:true}).click();
      await eventually(()=>Object.keys(state().figures['1'].versions).length>0);
      await figure().getByLabel('Compare with original').check();
      assert.match(await figure().innerText(), /1 added/);
    } else if(mode==='saved') {
      const select=figure().getByRole('combobox',{name:'Version',exact:true});
      const options=await select.locator('option').evaluateAll(es=>es.map(e=>e.value).filter(v=>v!=='original'));
      assert.ok(options.length);
      await select.selectOption(options[0]);
      assert.ok((await figure().locator('g.node text').allTextContents()).includes('Acceptance node'));
    } else if(mode==='ask') {
      await ask();
      assert.ok(payload.id); assert.ok(payload.change.ask);
      console.log('PAYLOAD '+JSON.stringify(payload));
    } else if(mode==='answer') {
      await eventually(async()=>/Acceptance answer/.test(await body()));
    } else if(mode==='pick') {
      const field=page.locator('fieldset.choice[data-key=web]');
      if(!await field.isVisible()) await page.locator('details.step-body > summary').first().click();
      await field.locator('button[data-value=off]').click();
      await eventually(()=>state().picks.web?.value==='off');
    } else if(mode==='plan-pick') {
      await page.locator('fieldset.choice[data-key=profile] button[data-value=careful]').click();
      await eventually(()=>state().picks.profile?.value==='careful');
    } else if(mode==='requests') {
      await ask();
      await page.locator('button.change[data-change=Setup]').click();
      await eventually(()=>state().asks.some(a=>a.step==='Setup'));
      await figure().getByRole('button',{name:/Ask .*change|Ask .*diagram/i}).click();
      const diagramText=figure().getByRole('textbox',{name:/change.*diagram|diagram.*change/i});
      await diagramText.fill('Acceptance diagram request');
      await diagramText.press('Enter');
      await eventually(()=>state().asks.some(a=>a.kind==='diagram'));
    } else if(mode==='proposal') {
      await addNode();
      const before=await figure().locator('g.node text').allTextContents();
      await page.getByRole('button',{name:/Preview proposal/i}).first().click();
      // A proposal may be shown alongside the editor, but must not replace dirty work.
      assert.deepEqual(await figure().locator('g.node text').allTextContents(),before);
      assert.ok(await page.getByRole('button',{name:'Save as my version',exact:true}).count());
    } else if(mode==='conflict') {
      let count=0;
      await page.route('**/api/change', async route=>{
        count++;
        if(count<=2) await route.fulfill({status:412,contentType:'application/json',body:JSON.stringify({error:'stale revision'})});
        else await route.continue();
      });
      await question().fill('Conflict question');
      await page.getByRole('button',{name:/Send to /}).click();
      await eventually(()=>count===2);
      await page.waitForTimeout(500);
      assert.equal(count,2,'Only one automatic replay');
      assert.match(await body(),/pending|retry|kept|conflict/i);
      await page.getByRole('button',{name:/Retry/i}).first().click();
      await eventually(()=>state().asks.some(a=>a.text==='Conflict question'));
      assert.equal(state().asks.filter(a=>a.text==='Conflict question').length,1);
    } else if(mode==='polling') {
      await ask();
      cli('answer',live,'1','Polled acceptance answer');
      await eventually(async()=>/Polled acceptance answer/.test(await body()));
      await addNode(); await question().fill('Unsent through disconnect');
      await page.route('**/api/change',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Storage unavailable'})}));
      await figure().getByRole('button',{name:'Save as my version',exact:true}).click();
      await eventually(async()=>/pending|kept|retry/i.test(await body()));
      await context.setOffline(true);
      await eventually(async()=>/disconnect|connection lost|retrying|offline/i.test(await body()));
      assert.equal(await question().inputValue(),'Unsent through disconnect');
      await page.unroute('**/api/change');
      await context.setOffline(false);
      await eventually(async()=>/connected/i.test(await body()));
      const retry=page.getByRole('button',{name:/Retry/i}).first();
      if(await retry.isVisible()) await retry.click();
      await eventually(()=>Object.keys(state().figures['1'].versions).length>0);
      assert.equal(await question().inputValue(),'Unsent through disconnect');
      assert.ok((await figure().locator('g.node text').allTextContents()).includes('Acceptance node'));
    } else if(mode==='refresh') {
      await figure().getByRole('button',{name:'Save as my version',exact:true}).click();
      await eventually(()=>Object.keys(state().figures['1'].versions).length>0);
      const versionsBefore=state().figures['1'].versions;
      const select=figure().getByRole('combobox',{name:'Version',exact:true});
      const mine=Object.keys(versionsBefore)[0];
      await select.selectOption(mine);
      await addNode(); await question().fill('Unsent across regeneration');
      const before=await figure().locator('g.node text').allTextContents();
      const doc=path.join(path.dirname(live),'doc.json');
      const content=JSON.parse(fs.readFileSync(doc,'utf8'));
      content.sections.find(s=>s.markdown.includes('flowchart')).markdown+='\nUpdated source context.\n';
      // Change the actual graph source as well as prose.
      for(const section of content.sections) section.markdown=section.markdown.replace('Api[Export endpoint]','Api[Changed endpoint]');
      fs.writeFileSync(doc,JSON.stringify(content));
      cli('live',doc,live,'--provider','local');
      await eventually(async()=>/update|new page|changed/i.test(await body()));
      assert.deepEqual(await figure().locator('g.node text').allTextContents(),before);
      assert.equal(await question().inputValue(),'Unsent across regeneration');
      assert.equal(await select.inputValue(),mine);
      const staleSave=figure().getByRole('button',{name:'Save as my version',exact:true});
      if(await staleSave.isEnabled()) await staleSave.click();
      await page.waitForTimeout(500);
      assert.deepEqual(state().figures['1'].versions,versionsBefore,'Changed source blocks blind replay');
      assert.match(await body(),/source|changed|stale|update/i);
    } else throw new Error('Unknown acceptance browser mode '+mode);
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
