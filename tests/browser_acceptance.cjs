/* Run: FEEDCTRL_PYTHON=.venv/bin/python node tests/browser_acceptance.cjs
   Install optional browser runner first: npm --prefix web install --no-save playwright
   Then: npx --prefix web playwright install chromium
   Runtime-owned Playwright is used when CODEX_PRIMARY_RUNTIME_NODE_MODULES exists. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { chromium } = require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES
  ? path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES, 'playwright')
  : path.join(__dirname, '../web/node_modules/playwright'));
const root = path.resolve(__dirname, '..');
const out = path.resolve(root, process.env.FEEDCTRL_VERIFICATION_DIR || 'results/verification');
fs.mkdirSync(out, { recursive: true });
const python = process.env.FEEDCTRL_PYTHON || path.join(root, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
const port = Number(process.env.FEEDCTRL_TEST_PORT || 8011);
const origin = `http://127.0.0.1:${port}`;
const server = spawn(python, ['-m','uvicorn','feedctrl.api:app','--host','127.0.0.1','--port',String(port)],
  {cwd:root, env:{...process.env, OLLAMA_BASE_URL:'http://127.0.0.1:9'}});
const logs = [];
server.stdout.on('data', v => logs.push(v.toString()));
server.stderr.on('data', v => logs.push(v.toString()));
const report = { started_at: new Date().toISOString(), checks: [], environment: null, browser_errors: [],
  runtime: {platform:process.platform,node:process.version},
  backend_failure_test:'Server deliberately uses loopback port 9 to verify visible operational failure. This run does not claim successful LLM inference.' };
const check = (name, details) => { report.checks.push({name, status:'passed', ...details}); console.log('PASS',name); };
let browser;

(async () => {
  for (let attempt=0; attempt<180; attempt++) {
    try { const r = await fetch(`${origin}/api/status`); if (r.ok) {report.environment = await r.json(); break;} }
    catch (_) {}
    if (server.exitCode !== null) throw new Error(`Server exited: ${logs.join('')}`);
    await new Promise(resolve => setTimeout(resolve,500));
  }
  assert.ok(report.environment, 'Server must become healthy');
  browser = await chromium.launch({ headless:true, args:['--no-sandbox'], ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? {executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE} : {}) });
  report.runtime.chromium=browser.version();
  const context = await browser.newContext({viewport:{width:1440,height:1100}});
  const page = await context.newPage();
  page.on('pageerror', err => report.browser_errors.push(err.message));
  await page.goto(origin);
  const ready = async () => {
    await page.locator('.results[aria-busy="false"]').waitFor({timeout:90000});
    assert.equal(await page.locator('[role="alert"]').count(),0);
  };
  await ready();
  assert.equal(await page.title(),'Feed Control Lab');
  assert.equal(await page.locator('.item-card').count(),10);
  assert.ok((await page.locator('.status-strip').innerText()).includes(report.environment.model_mode));
  check('Desktop loads ten metadata cards and independently labels data/model/parser');
  const categoryIds = (await (await fetch(`${origin}/api/categories`)).json()).categories;
  const users = await (await fetch(`${origin}/api/users`)).json();
  const c0=categoryIds[0], c1=categoryIds[1];
  const initialProfile = await page.locator('#profile').inputValue();
  assert.ok(initialProfile.includes('observed interaction history'));
  assert.ok(initialProfile.split(/\s+/).length <= 200);
  check('Editable profile initializes from bounded factual history');
  const explanationLabels = await page.locator('.explanation-origin').allTextContents();
  if (report.environment.data_mode !== 'fixture') {
    assert.ok(explanationLabels.includes('Cached LLM · verified facts'));
    check('Shipped real-data feed displays the recorded cached LLM explanation provenance',
      {cached_labels:explanationLabels.filter(v=>v==='Cached LLM · verified facts').length,
       template_labels:explanationLabels.filter(v=>v==='Verified template · no LLM').length});
  }
  await page.screenshot({path:path.join(out,'app-desktop.png'), fullPage:true});
  await page.setViewportSize({width:1440,height:900});
  await page.locator('.workspace').scrollIntoViewIfNeeded();
  await page.evaluate(() => window.scrollTo(0, document.querySelector('.workspace').getBoundingClientRect().top + window.scrollY - 20));
  await page.screenshot({path:path.join(out,'app-presentation.png'),fullPage:false});
  const condition = async c => {await page.locator('.condition').filter({has:page.locator('b',{hasText:new RegExp(`^${c}$`)})}).click(); await ready();};
  const itemIds = () => page.locator('.item-title h3').allTextContents();
  await condition('A'); const a = await itemIds();
  await condition('B'); assert.deepEqual(await itemIds(),a);
  assert.ok(await page.locator('.explanation-origin').count() > 0);
  check('A/B rankings identical; B explanations explicitly identify their provenance');
  const beforeSignals = await itemIds();
  await page.getByLabel('Show signals').uncheck();
  assert.equal(await page.locator('.signals').count(),0);
  assert.deepEqual(await itemIds(),beforeSignals);
  await page.getByLabel('Show signals').check();
  check('Explanation toggle changes visibility without reranking');
  await condition('C');
  await page.locator('#control').fill(`Mute ${c0}`);
  await page.locator('#control').press('Control+Enter'); await ready();
  assert.ok((await page.locator('[role="status"]').innerText()).includes('applied'));
  assert.ok(!(await page.locator('.category-pills').allTextContents()).some(v => v.split(/\s+/).includes(c0)));
  check('Ctrl+Enter submits a rule command and hard-mutes the exact requested category in C');
  const savedText = `${initialProfile}\nShow me more ${c0}. Mute ${c1}.`;
  await page.locator('#profile').fill(savedText);
  await page.getByRole('button',{name:'Save profile',exact:true}).click(); await ready();
  await condition('D');
  assert.ok((await page.locator('.saved-profile').innerText()).includes(c0));
  assert.ok(!(await page.locator('.category-pills').allTextContents()).some(v=>v.split(/\s+/).includes(c1)));
  check('Natural-language profile parses and affects D independently of C');
  if(users.length > 1) {
    await page.locator('.user-select select').selectOption(String(users[1].user_id)); await ready();
    assert.notEqual(await page.locator('#profile').inputValue(),savedText);
    assert.equal(await page.locator('.preference').count(),0);
    await page.locator('.user-select select').selectOption(String(users[0].user_id)); await ready();
    assert.equal(await page.locator('#profile').inputValue(),savedText);
    check('User switching preserves raw profile text and isolates preferences');
  }
  await page.getByRole('button',{name:'Compare A–E',exact:true}).click();
  assert.equal(await page.locator('tbody tr').count(),5);
  assert.ok((await page.locator('.comparison-check').innerText()).includes('verified in this preview'));
  await page.screenshot({path:path.join(out,'app-comparison.png'),fullPage:true});
  check('Five-condition comparison table renders with A/B invariance check');
  await page.getByRole('button',{name:'Explore feed',exact:true}).click();
  await condition('A');
  const removed = (await itemIds())[0];
  await page.getByRole('button',{name:`Dislike ${removed.toLowerCase()}`,exact:true}).click(); await ready();
  assert.ok(!(await itemIds()).includes(removed));
  check('Item-only negative feedback removes the selected item from A');
  await page.getByRole('button',{name:'Reset this user'}).click(); await ready();
  assert.equal(await page.locator('.preference').count(),0);
  assert.equal(await page.locator('#profile').inputValue(),initialProfile);
  assert.deepEqual(await itemIds(),a);
  check('Reset restores original ranking and neutral history profile');
  const beforeFailure = await itemIds();
  await page.locator('#parser').selectOption('ollama');
  await page.locator('#control').fill(`Mute ${c0}`);
  await page.getByRole('button',{name:'Apply instruction'}).click();
  await page.locator('[role="alert"]').waitFor({timeout:30000});
  assert.ok((await page.locator('[role="alert"]').innerText()).includes('ollama parser failed'));
  assert.deepEqual(await itemIds(),beforeFailure);
  check('Unavailable Ollama produces a visible error and preserves the previous feed');
  await page.locator('#parser').selectOption('rule');
  await page.locator('#control').fill(`Show me more ${c0}`);
  await page.locator('#control').press('Meta+Enter'); await ready();
  assert.ok((await page.locator('[role="status"]').innerText()).includes('applied'));
  check('Cmd+Enter submits an instruction and recovers from the visible backend error');
  const page2 = await context.newPage(); await page2.goto(origin);
  await page2.locator('.results[aria-busy="false"]').waitFor({timeout:90000});
  assert.equal(await page2.locator('.active-instruction').count(),0); await page2.close();
  check('Separate browser page receives an isolated new session');
  await page.keyboard.press('Tab');
  assert.ok(await page.evaluate(() => document.activeElement !== document.body));
  check('Keyboard Tab reaches an interactive element');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  await page.screenshot({path:path.join(out,'app-mobile.png'),fullPage:true});
  await page.getByRole('button',{name:'Compare A–E',exact:true}).click();
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  check('390px mobile feed and comparison do not overflow the document');
  assert.deepEqual(report.browser_errors,[]);
  check('No uncaught browser errors');
  report.status='passed';
})().catch(error=> {report.status='failed'; report.failure=error.stack; console.error(error); process.exitCode=1;})
.finally(async()=>{
  if(browser) await browser.close();
  server.kill();
  report.finished_at=new Date().toISOString();
  fs.writeFileSync(path.join(out,'browser-acceptance.json'), JSON.stringify(report,null,2));
  fs.writeFileSync(path.join(out,'browser-server.log'), logs.join(''));
});
