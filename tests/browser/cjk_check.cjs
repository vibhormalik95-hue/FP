// Walk every screen of the app and every step of the recorded demo; fail on any visible CJK character.
// Usage: node tests/browser/cjk_check.cjs --base http://127.0.0.1:8765 --out <folder>
// Runs on the mock provider with no key. CJK here means U+3000-U+303F, U+3400-U+9FFF and U+FF00-U+FFEF.
// Checked on every screen: the visible text of the page, every option of every list (also closed
// lists), every input and textarea value, placeholders, titles and ARIA labels.
const fs = require('fs'), path = require('path');
const { chromium } = require(path.join(process.cwd(), 'node_modules', 'playwright'));
const arg = n => { const i = process.argv.indexOf(n); return i > 0 ? process.argv[i + 1] : undefined; };
const base = arg('--base') || 'http://127.0.0.1:8765', out = arg('--out') || 'runs/cjk-check';
const user = Number(arg('--user') || 14);
const examples = JSON.parse(fs.readFileSync('tools/demo_examples.json', 'utf8'));
fs.mkdirSync(out, {recursive: true});

// The probe also runs live inside the recorder (tools/recording/record_demo.py reads it from here).
const PROBE = fs.readFileSync(path.join(__dirname, 'cjk_probe.js'), 'utf8');

const screens = [];
let failed = 0, shot = 0, selftest = false;
async function probe(page, name) {
  await page.waitForTimeout(250);
  const hits = await page.evaluate(`(${PROBE.trim()})()`);
  screens.push({screen: name, hits});
  if (hits.length) {
    failed++;
    await page.screenshot({path: path.join(out, `${String(++shot).padStart(2, '0')}-FAIL-${name.replace(/\W+/g, '-')}.png`)});
  }
  console.log(`${hits.length ? 'FAIL' : 'PASS'}  ${name}${hits.length ? ' · ' + hits.slice(0, 3).join(' | ') : ''}`);
}
const waitReview = p => p.waitForSelector('[data-role="review"], [data-role="error"]', {timeout: 300000});
const noReview = p => p.waitForFunction(() => !document.querySelector('[data-role="review"]'), null, {timeout: 60000});

(async () => {
  const browser = await chromium.launch({channel: 'chrome'});
  const page = await browser.newPage({viewport: {width: 1920, height: 1080}});
  const errors = []; page.on('pageerror', e => errors.push(String(e)));
  const t0 = Date.now();
  const api = async (p, body) => {
    const r = await fetch(base + '/api/' + p, body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {});
    return r.json();
  };

  await page.goto(base); await page.waitForSelector('[data-view="lab"]', {timeout: 60000});
  await api('lab/reset', {user_id: user});
  await page.selectOption('.user-select select', String(user)).catch(() => {});
  await page.waitForTimeout(800);
  // Self-test: the probe must see a CJK character that is put on the page, and must not see a hidden one.
  await page.evaluate(() => { const d = document.createElement('div'); d.id = 'cjk-selftest'; d.textContent = 'self-test ' + String.fromCharCode(0x4e2d); document.body.appendChild(d); });
  const seen = (await page.evaluate(`(${PROBE.trim()})()`)).length;
  await page.evaluate(() => { document.getElementById('cjk-selftest').style.display = 'none'; });
  const hidden = (await page.evaluate(`(${PROBE.trim()})()`)).length;
  await page.evaluate(() => document.getElementById('cjk-selftest').remove());
  selftest = seen > 0 && hidden === 0;
  console.log(`${selftest ? 'PASS' : 'FAIL'}  probe self-test (visible ${seen}, hidden ${hidden})`);
  if (!selftest) failed++;
  await probe(page, 'start page (A to E)');

  // Original study: every condition, the compare view and every top-level view.
  for (const button of await page.$$('.conditions button')) {
    const label = (await button.textContent()).trim().slice(0, 30);
    await button.click(); await page.waitForTimeout(600);
    await probe(page, `condition ${label}`);
  }
  for (const text of ['Compare A to E', 'Original study']) {
    const b = page.locator(`button:has-text("${text}")`).first();
    if (await b.count()) { await b.click(); await page.waitForTimeout(800); await probe(page, `view ${text}`); }
  }
  const free = page.locator('button.condition:has-text("Free text")');
  if (await free.count()) {
    await free.click(); await page.fill('#control', 'Show me more category_5');
    await page.click('button:has-text("Apply instruction")'); await page.waitForSelector('.active-instruction', {timeout: 30000});
    await probe(page, 'condition C instruction applied');
  }

  // Language controls: the same steps as the recorded demo, on the mock provider.
  await page.click('[data-view="lab"]'); await page.waitForSelector('.lab-card');
  await probe(page, 'language controls start');
  for (const kind of ['openai', 'anthropic', 'ollama', 'claude-cli', 'mock']) {
    await page.selectOption('[data-role="provider-kind"]', kind); await page.waitForTimeout(200);
    await probe(page, `provider ${kind}`);
  }
  await page.click('[data-role="provider-save"]'); await page.waitForTimeout(400);
  for (const kind of ['category', 'tag', 'custom', 'feature']) {
    await page.selectOption('[data-role="manual-kind"]', kind); await page.waitForTimeout(700);
    await probe(page, `label list ${kind}`);
  }
  await page.selectOption('[data-role="manual-kind"]', 'category');

  // Manual: hide the five news and incident categories, preview, before/after, apply.
  const labels = (await api(`lab/labels?user_id=${user}&kind=category&limit=2000`)).labels.map(l => l.value);
  const news = labels.filter(v => /incident|news|disaster/i.test(v)).slice(0, 5);
  for (const v of news) {
    await page.fill('[data-role="label-filter"]', v); await page.waitForTimeout(500);
    await page.selectOption('[data-role="label-list"]', v); await page.click(`[data-role="label-list"] option[value="${v}"]`);
  }
  await page.selectOption('[data-role="manual-action"]', 'hide');
  await probe(page, 'manual labels picked');
  await page.click('[data-role="manual-preview"]'); await waitReview(page);
  await probe(page, 'manual preview (after)');
  await page.click('.view-tabs button:has-text("Before")'); await probe(page, 'manual preview (before)');
  await page.click('.view-tabs button:has-text("After")');
  await page.locator('details').evaluateAll(ds => ds.forEach(d => { d.open = true; }));
  await probe(page, 'manual preview, checks and calls open');
  await page.click('[data-role="apply"]'); await noReview(page);
  await probe(page, 'manual applied');

  for (const m of examples.manual) {
    await page.selectOption('[data-role="manual-kind"]', m.kind);
    await page.fill('[data-role="label-filter"]', m.value); await page.waitForTimeout(500);
    await page.selectOption('[data-role="label-list"]', m.value); await page.click(`[data-role="label-list"] option[value="${m.value}"]`);
    await page.selectOption('[data-role="manual-action"]', m.action);
    if (m.strength) await page.selectOption('[data-role="lab-strength"]', m.strength);
    await page.click('[data-role="manual-preview"]'); await waitReview(page);
    await probe(page, `manual ${m.domain} preview`);
    await page.click('[data-role="apply"]'); await noReview(page);
    await page.click('[data-role="undo"]'); await page.waitForTimeout(600);
    await probe(page, `manual ${m.domain} undone`);
  }

  for (const ex of examples.interpret) {
    await page.click('[data-tab="interpret"]'); await page.fill('[data-role="request"]', ex.request);
    await page.click('[data-role="interpret-preview"]'); await waitReview(page);
    await page.locator('details').evaluateAll(ds => ds.forEach(d => { d.open = true; }));
    await probe(page, `interpret ${ex.domain}`);
    if (await page.$('[data-role="apply"]:not([disabled])')) {
      await page.click('[data-role="apply"]'); await noReview(page);
      await probe(page, `interpret ${ex.domain} applied`);
      await page.click('[data-role="undo"]'); await page.waitForTimeout(500);
    } else if (await page.$('[data-role="discard"]')) await page.click('[data-role="discard"]');
  }

  for (const nc of examples.new_category) {
    await page.click('[data-tab="category"]'); await page.fill('[data-role="category-description"]', nc.description);
    await page.selectOption('[data-role="scope"]', '10');
    await probe(page, `new category ${nc.domain} form`);
    await page.click('[data-role="define"]'); await page.waitForSelector('[data-role="definition"], [data-role="error"]', {timeout: 300000});
    await probe(page, `new category ${nc.domain} definition`);
    if (await page.$('[data-role="classify"]:not([disabled])')) {
      await page.click('[data-role="classify"]'); await waitReview(page);
      await page.locator('details').evaluateAll(ds => ds.forEach(d => { d.open = true; }));
      await probe(page, `new category ${nc.domain} classification`);
      if (await page.$('[data-role="apply"]:not([disabled])')) {
        await page.click('[data-role="apply"]'); await noReview(page);
        await probe(page, `new category ${nc.domain} applied`);
      } else if (await page.$('[data-role="discard"]')) await page.click('[data-role="discard"]');
    }
  }
  for (const ni of examples.new_items) {
    await page.click('[data-tab="items"]');
    await page.fill('[data-role="new-title-0"]', ni.items[0].title); await page.fill('[data-role="new-description-0"]', ni.items[0].description);
    await page.click('[data-role="new-items-preview"]'); await waitReview(page);
    await probe(page, `new items ${ni.domain}`);
    if (await page.$('[data-role="apply"]:not([disabled])')) {
      await page.click('[data-role="apply"]'); await noReview(page);
      await probe(page, `new items ${ni.domain} applied`);
      await page.click('[data-role="undo"]'); await page.waitForTimeout(500);
    }
  }
  await page.check('[data-role="auto-apply"]'); await probe(page, 'auto-apply on'); await page.uncheck('[data-role="auto-apply"]');
  await page.click('[data-role="lab-reset"]'); await page.waitForTimeout(600);
  await probe(page, 'after reset');

  await page.click('[data-view="results"]'); await page.waitForSelector('[data-role="results"], .empty-state');
  await probe(page, 'results page');

  await browser.close();
  const receipt = {base, user, probe_selftest: selftest, seconds: (Date.now() - t0) / 1000, screens: screens.length, failed,
                   page_errors: errors, ranges: 'U+3000-U+303F, U+3400-U+9FFF, U+FF00-U+FFEF', results: screens};
  fs.writeFileSync(path.join(out, 'cjk-check-receipt.json'), JSON.stringify(receipt, null, 1));
  console.log(`OUTCOME ${failed ? failed + ' screen(s) show CJK characters' : 'no visible CJK on ' + screens.length + ' screens'}`);
  process.exit(failed || errors.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
