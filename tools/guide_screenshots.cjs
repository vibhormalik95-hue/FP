// Screenshots for docs/guide/PROFESSOR-GUIDE.md from the running app (English text layer).
// Usage: node tools/guide_screenshots.cjs --base http://127.0.0.1:8765 --out docs/guide/images --user 14
// The app must run with the provider used for the model steps (for example gpt-5-mini); the manual
// steps and conditions A to E call no model. Every shot is also checked for visible CJK characters.
const fs = require('fs'), path = require('path');
const { chromium } = require(path.join(process.cwd(), 'node_modules', 'playwright'));
const arg = n => { const i = process.argv.indexOf(n); return i > 0 ? process.argv[i + 1] : undefined; };
const base = arg('--base') || 'http://127.0.0.1:8765', out = arg('--out') || 'docs/guide/images';
const user = String(arg('--user') || 14);
const examples = JSON.parse(fs.readFileSync('tools/demo_examples.json', 'utf8'));
const PROBE = fs.readFileSync(path.join('tests', 'browser', 'cjk_probe.js'), 'utf8').trim();
fs.mkdirSync(out, {recursive: true});
const log = [];

(async () => {
  const browser = await chromium.launch({channel: 'chrome'});
  const page = await browser.newPage({viewport: {width: 1600, height: 1000}});
  const shot = async (name, clip) => {
    const hits = await page.evaluate(`(${PROBE})()`);
    if (hits.length) throw new Error(`CJK on screen for ${name}: ${hits.slice(0, 3).join(' | ')}`);
    await page.screenshot({path: path.join(out, name), fullPage: false, ...(clip ? {clip} : {})});
    log.push(name); console.log('shot', name);
  };
  const waitReview = () => page.waitForSelector('[data-role="review"], [data-role="error"]', {timeout: 600000});
  const noReview = () => page.waitForFunction(() => !document.querySelector('[data-role="review"]'), null, {timeout: 60000});
  const top = () => page.evaluate(() => window.scrollTo(0, 0));
  await fetch(base + '/api/lab/reset', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({user_id: Number(user)})});

  await page.goto(base); await page.waitForSelector('[data-view="lab"]', {timeout: 60000});
  await page.selectOption('.user-select select', user); await page.waitForTimeout(1200);
  await page.click('button.condition:has-text("Free text")');
  await page.fill('#control', 'Show me more category_5');
  await page.click('button:has-text("Apply instruction")'); await page.waitForSelector('.active-instruction');
  await page.waitForTimeout(800); await shot('01-ae-condition-c.png');
  await page.click('button:has-text("Compare A to E")'); await page.waitForTimeout(1200); await shot('11-compare-a-to-e.png');

  await page.click('[data-view="lab"]'); await page.waitForSelector('.lab-card');
  await page.selectOption('[data-role="provider-kind"]', 'openai'); await page.waitForTimeout(300);
  await shot('02-provider-key-field.png', {x: 0, y: 0, width: 1600, height: 330});
  // Back to the provider the server started with (the model steps below use it).
  await page.reload(); await page.waitForSelector('[data-view="lab"]'); await page.selectOption('.user-select select', user); await page.waitForTimeout(800);
  await page.click('[data-view="lab"]'); await page.waitForSelector('.lab-card');

  // Manual: dance, show more, strong.
  const m = examples.manual[1];
  await page.click('[data-tab="manual"]');
  await page.fill('[data-role="label-filter"]', m.value); await page.waitForTimeout(600);
  await page.click(`[data-role="label-list"] option[value="${m.value}"]`);
  await page.selectOption('[data-role="manual-action"]', m.action); await page.selectOption('[data-role="lab-strength"]', m.strength);
  await page.click('[data-role="manual-preview"]'); await waitReview(); await top();
  await shot('03-manual-preview-after.png');
  await page.click('.view-tabs button:has-text("Before")'); await shot('04-manual-preview-before.png');
  await page.click('.view-tabs button:has-text("After")');
  await page.click('[data-role="apply"]'); await noReview(); await page.waitForTimeout(500);
  await page.locator('[data-role="applied"]').scrollIntoViewIfNeeded(); await shot('12-manual-applied-undo.png');
  await page.click('[data-role="undo"]'); await page.waitForTimeout(800); await top();

  // Requests in your own words.
  for (const [n, file] of [[2, '05-interpret-food.png'], [3, '06-interpret-news.png']]) {
    await page.click('[data-tab="interpret"]'); await page.fill('[data-role="request"]', examples.interpret[n].request);
    await page.click('[data-role="interpret-preview"]'); await waitReview();
    await page.locator('[data-role="review"]').scrollIntoViewIfNeeded(); await page.waitForTimeout(400);
    await shot(file);
    if (await page.$('[data-role="discard"]')) await page.click('[data-role="discard"]');
    await top();
  }

  // New category: outdoors, scope 20.
  await page.click('[data-tab="category"]'); await page.fill('[data-role="category-description"]', examples.new_category[0].description);
  await page.selectOption('[data-role="scope"]', '20');
  await page.click('[data-role="define"]'); await page.waitForSelector('[data-role="definition"], [data-role="error"]', {timeout: 600000});
  await page.locator('[data-role="definition"]').scrollIntoViewIfNeeded(); await page.waitForTimeout(400);
  await shot('07-category-definition.png');
  await page.selectOption('[data-role="category-action"]', 'boost');
  await page.click('[data-role="classify"]'); await waitReview();
  await page.locator('.lab-table').first().scrollIntoViewIfNeeded(); await page.waitForTimeout(400);
  await shot('08-category-review.png');
  if (await page.$('[data-role="apply"]:not([disabled])')) { await page.click('[data-role="apply"]'); await noReview(); }
  await top();

  // New item.
  const ni = examples.new_items[0].items[0];
  await page.click('[data-tab="items"]'); await page.fill('[data-role="new-title-0"]', ni.title); await page.fill('[data-role="new-description-0"]', ni.description);
  await page.click('[data-role="new-items-preview"]'); await waitReview();
  await page.locator('[data-role="review"]').scrollIntoViewIfNeeded(); await page.waitForTimeout(400);
  await shot('09-new-items-review.png');
  await page.click('[data-role="apply"]'); await noReview(); await page.waitForTimeout(500);
  await page.locator('[data-role="applied"]').scrollIntoViewIfNeeded(); await shot('14-new-item-applied.png');
  await page.click('[data-role="lab-reset"]'); await page.waitForTimeout(800); await top();

  // Auto-apply with the manual pets hide.
  const p = examples.manual[0];
  await page.check('[data-role="auto-apply"]'); await page.click('[data-tab="manual"]');
  await page.fill('[data-role="label-filter"]', p.value); await page.waitForTimeout(600);
  await page.click(`[data-role="label-list"] option[value="${p.value}"]`);
  await page.selectOption('[data-role="manual-action"]', p.action);
  await page.click('[data-role="manual-preview"]');
  await page.waitForFunction(() => document.querySelector('[data-role="applied"]').textContent.includes('Hide'), null, {timeout: 30000});
  await page.waitForTimeout(600); await shot('13-auto-apply.png');
  await page.uncheck('[data-role="auto-apply"]'); await page.click('[data-role="lab-reset"]'); await page.waitForTimeout(600);

  await page.click('[data-view="results"]'); await page.waitForSelector('[data-role="results"]'); await page.waitForTimeout(600);
  await shot('10-results.png');
  const calls = await (await fetch(base + '/api/lab/calls')).json();
  fs.writeFileSync(path.join(out, 'screenshots-receipt.json'), JSON.stringify({base, user, shots: log, model_calls: calls.calls.length, cost_usd: calls.total_usd, cjk: 'none visible in any shot'}, null, 1));
  console.log('cost', calls.total_usd);
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
