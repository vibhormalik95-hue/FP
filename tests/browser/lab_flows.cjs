// Drive the KuaiRec language controls in a real browser (system Chrome through Playwright).
// Usage: node tests/browser/lab_flows.cjs --base http://127.0.0.1:8765 --out <folder>
// Works on the mock provider with no key. Writes lab-browser-receipt.json and screenshots.
const fs = require('fs'), path = require('path');
const { chromium } = require(path.join(process.cwd(), 'node_modules', 'playwright'));
const arg = n => { const i = process.argv.indexOf(n); return i > 0 ? process.argv[i + 1] : undefined; };
const base = arg('--base') || 'http://127.0.0.1:8765', out = arg('--out') || 'runs/lab-browser';
const examples = JSON.parse(fs.readFileSync('tools/demo_examples.json', 'utf8'));
fs.mkdirSync(out, {recursive: true});
const checks = []; let shot = 0;
const check = (name, ok, detail = '') => { checks.push({name, ok: Boolean(ok), detail}); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ' · ' + detail : ''}`); };
const eligible = async p => Number((await p.textContent('.lab-count')).match(/(\d+) of/)[1]);
const noReview = p => p.waitForFunction(() => !document.querySelector('[data-role="review"]'), null, {timeout: 60000});

(async () => {
  const browser = await chromium.launch({channel: 'chrome'});
  const page = await browser.newPage({viewport: {width: 1920, height: 1080}});
  const errors = []; page.on('pageerror', e => errors.push(String(e)));
  const snap = async name => page.screenshot({path: path.join(out, `${String(++shot).padStart(2, '0')}-${name}.png`)});
  const t0 = Date.now();
  await page.goto(base); await page.waitForSelector('[data-view="lab"]', {timeout: 60000});
  // The original A to E view on KuaiRec: the rule parser of C reads category_N.
  check('A to E view loads on processed KuaiRec', (await page.textContent('.status-strip')).includes('PROCESSED DATASET'));
  await page.click('button.condition:has-text("Free text")');
  await page.fill('#control', 'Show me more category_0');
  await page.click('button:has-text("Apply instruction")');
  await page.waitForSelector('.active-instruction', {timeout: 30000});
  check('Condition C applies a category instruction on KuaiRec', (await page.textContent('.active-instruction')).includes('category_0'));
  await snap('ae-condition-c');

  await page.click('[data-view="lab"]'); await page.waitForSelector('.lab-card');
  await page.selectOption('[data-role="provider-kind"]', 'openai');
  check('Key field is masked when a hosted provider is chosen', (await page.getAttribute('[data-role="api-key"]', 'type')) === 'password');
  await page.selectOption('[data-role="provider-kind"]', 'mock');
  await page.click('[data-role="provider-save"]'); await page.waitForTimeout(300);
  const start = await eligible(page);

  // 1. manual
  const m = examples.manual[0];
  const pickManual = async () => {
    await page.click('[data-tab="manual"]'); await page.selectOption('[data-role="manual-kind"]', m.kind);
    await page.fill('[data-role="label-filter"]', m.value); await page.waitForTimeout(500);
    await page.selectOption('[data-role="label-list"]', m.value); await page.selectOption('[data-role="manual-action"]', m.action);
  };
  await pickManual();
  await page.click('[data-role="manual-preview"]'); await page.waitForSelector('[data-role="review"]');
  check('Manual preview leaves the applied feed unchanged', (await page.textContent('[data-role="applied"]')).includes('No control is applied'));
  await snap('manual-review');
  await page.click('[data-role="apply"]'); await noReview(page);
  const afterManual = await eligible(page);
  check('Manual Apply removes the label', afterManual < start, `${start} -> ${afterManual}`);
  await page.click('[data-role="undo"]'); await page.waitForTimeout(600);
  check('Undo restores the feed', (await eligible(page)) === start);

  // 2. interpret: every example; the mock can only match literal words.
  for (const ex of examples.interpret) {
    await page.click('[data-tab="interpret"]'); await page.fill('[data-role="request"]', ex.request);
    await page.click('[data-role="interpret-preview"]'); await page.waitForSelector('[data-role="review"], [data-role="error"]', {timeout: 120000});
    const text = await page.textContent('[data-role="review"]').catch(() => '');
    check(`Interpret (${ex.domain}, ${ex.kind}) returns a reviewed proposal`, text.includes('What the application checked'), (text.match(/Model status: (\w+)/) || [])[1] || 'error');
    if (await page.$('[data-role="apply"]:not([disabled])')) {
      await page.click('[data-role="apply"]'); await noReview(page);
      check(`Interpret Apply (${ex.domain}) adds a control`, !(await page.textContent('[data-role="applied"]')).includes('No control is applied'));
      await page.click('[data-role="undo"]'); await page.waitForTimeout(500);
    } else if (await page.$('[data-role="discard"]')) await page.click('[data-role="discard"]');
  }
  check('Feed column is in view', await page.evaluate(() => { const r = document.querySelector('.lab-feed').getBoundingClientRect(); return r.top < innerHeight && r.bottom > 0 && r.left < innerWidth; }));

  // 3. new category
  const nc = examples.new_category[0];
  await page.click('[data-tab="category"]'); await page.fill('[data-role="category-description"]', nc.description);
  await page.click('[data-role="define"]'); await page.waitForSelector('[data-role="definition"], [data-role="error"]', {timeout: 120000});
  const defined = await page.$('[data-role="classify"]:not([disabled])');
  check('New category: a definition is proposed for review', Boolean(defined));
  if (defined) {
    await snap('definition'); await page.click('[data-role="classify"]'); await page.waitForSelector('[data-role="review"]', {timeout: 300000});
    check('New category: classification table with quotations', (await page.$$('.lab-table tbody tr')).length > 0);
    await page.evaluate(() => window.scrollTo(0, document.querySelector('[data-role="review"]').offsetTop - 20));
    check('Feed column stays visible while the review is scrolled into view', await page.evaluate(() => { const r = document.querySelector('.lab-feed').getBoundingClientRect(); return r.top < innerHeight && r.bottom > 0; }));
    await snap('category-review');
    if (await page.$('[data-role="apply"]:not([disabled])')) {
      await page.click('[data-role="apply"]'); await noReview(page);
      check('New category Apply filters the feed', (await eligible(page)) <= start);
    }
  }
  // 4. new items, also judged against the new category
  const ni = examples.new_items[0].items[0];
  await page.click('[data-tab="items"]'); await page.fill('[data-role="new-title-0"]', ni.title); await page.fill('[data-role="new-description-0"]', ni.description);
  await page.click('[data-role="new-items-preview"]'); await page.waitForSelector('[data-role="review"]', {timeout: 120000});
  await page.click('[data-role="apply"]'); await noReview(page);
  check('New item is added', (await page.textContent('[data-role="applied"]')).includes(ni.title));
  await snap('new-item');
  await page.click('[data-role="undo"]'); await page.waitForTimeout(500);
  check('Undo removes the new item', !(await page.textContent('[data-role="applied"]')).includes(ni.title));
  await page.click('[data-role="lab-reset"]'); await page.waitForTimeout(600);
  check('Reset restores the trained ranking', (await eligible(page)) === start);

  // Auto-apply
  await page.check('[data-role="auto-apply"]'); await pickManual();
  await page.click('[data-role="manual-preview"]');
  await page.waitForFunction(() => document.querySelector('[data-role="applied"]').textContent.includes('Hide'), null, {timeout: 30000});
  check('Auto-apply applies the preview at once', true);
  await page.uncheck('[data-role="auto-apply"]'); await page.click('[data-role="lab-reset"]'); await page.waitForTimeout(400);

  await page.click('[data-view="results"]'); await page.waitForSelector('[data-role="results"], .empty-state');
  check('Results page renders from the result files', true); await snap('results');
  check('No page errors', errors.length === 0, errors.join(' | '));
  await browser.close();
  const failed = checks.filter(c => !c.ok).length;
  fs.writeFileSync(path.join(out, 'lab-browser-receipt.json'), JSON.stringify({base, seconds: (Date.now() - t0) / 1000, passed: checks.length - failed, failed, checks}, null, 1));
  console.log(`OUTCOME ${failed ? failed + ' check(s) failed' : 'all flows completed'} (${checks.length} checks)`);
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
