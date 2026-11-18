// Live integration of the four Lab workflows through the page, with a real provider.
// Usage: node tests/browser/lab_live.cjs --base http://127.0.0.1:PORT --out <folder> --provider openai|claude-cli|ollama
//        --model <model> [--effort low] [--scope 50]
// The key is never typed by this script: for a keyed provider the field is left empty and the server uses its own
// environment variable (the page says so). Every step records the exact server state (full ranking, controls,
// new-category members, added items) before and after; Undo and Reset must restore it exactly. Each workflow has
// one positive and one negative semantic check. Writes live-receipt.json (no key, no request bodies).
const fs = require('fs'), path = require('path');
const { chromium } = require(path.join(process.cwd(), 'node_modules', 'playwright'));
const arg = (n, d) => { const i = process.argv.indexOf(n); return i > 0 ? process.argv[i + 1] : d; };
const base = arg('--base'), out = arg('--out'), provider = arg('--provider'), model = arg('--model');
const effort = arg('--effort', 'low'), scope = arg('--scope', '50');
fs.mkdirSync(out, {recursive: true});
const ex = JSON.parse(fs.readFileSync('tools/demo_examples.json', 'utf8'));
const checks = [], steps = []; let user = null;
const check = (name, ok, detail = '') => { checks.push({name, ok: Boolean(ok), detail}); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ' · ' + detail : ''}`); };

(async () => {
  const browser = await chromium.launch({channel: 'chrome'});
  const page = await browser.newPage({viewport: {width: 1920, height: 1080}});
  const errors = []; page.on('pageerror', e => errors.push(String(e)));
  page.on('request', r => { const m = r.url().match(/lab\/state\?user_id=(\d+)/); if (m) user = Number(m[1]); });
  const state = () => page.evaluate(u => fetch(`/api/lab/state?user_id=${u}`).then(r => r.json()).then(s => ({
    ranked: s.feed.ranked_ids, eligible: s.feed.eligible, top10: s.feed.ranked_ids.slice(0, 10),
    controls: s.controls.map(c => `${c.action}:${c.target.kind}:${c.target.value}:${c.strength}:${c.group}`),
    custom: Object.fromEntries(Object.entries(s.custom).map(([k, v]) => [v.label, v.members])),
    added: s.added.map(a => `${a.item_id}:${a.title}`),
    cats: Object.fromEntries(s.feed.items.map(i => [i.item_id, i.kuairec_categories || []]))})), user);
  const same = (a, b) => JSON.stringify([a.ranked, a.controls, a.custom, a.added]) === JSON.stringify([b.ranked, b.controls, b.custom, b.added]);
  const rankChanged = (a, b) => JSON.stringify(a.ranked) !== JSON.stringify(b.ranked);
  const brief = s => ({eligible: s.eligible, top10: s.top10, controls: s.controls, custom: s.custom, added: s.added});
  const done = async (before, ms = 900000) => page.waitForFunction(b => (window.labDone || 0) > b, before, {timeout: ms});
  const labDone = () => page.evaluate(() => { window.labLastPreview = null; window.labLastError = null; window.labLastDefinition = null; return window.labDone || 0; });
  const preview = () => page.evaluate(() => window.labLastPreview || null);
  const lastErr = () => page.evaluate(() => window.labLastError || null);
  const apply = async () => { const b = await labDone(); await page.click('[data-role="apply"]'); await done(b, 60000); };
  const undo = async () => { const b = await labDone(); await page.click('[data-role="undo"]'); await done(b, 60000); };
  const t0 = Date.now();
  await page.goto(base); await page.waitForSelector('[data-view="lab"]', {timeout: 60000});
  await page.click('[data-view="lab"]'); await page.waitForSelector('.lab-card');
  await page.selectOption('[data-role="provider-kind"]', provider);
  await page.fill('[data-role="provider-model"]', model);
  if (await page.$('[data-role="provider-effort"]')) await page.selectOption('[data-role="provider-effort"]', effort);
  await page.click('[data-role="provider-save"]'); await page.waitForTimeout(1500);
  const st = await page.evaluate(() => fetch('/api/lab/status').then(r => r.json()));
  check('Provider set through the page', st.provider.provider === (provider === 'claude-cli' ? 'claude-cli' : provider) && st.provider.model === model,
    JSON.stringify({provider: st.provider.provider, model: st.provider.model, effort: st.provider.effort, key_source: st.provider.key_source}));
  const start = await state();
  steps.push({step: 'start', user, ...brief(start)});

  // 1. Manual (no model): positive = Pets hidden; negative = an unrelated label stays.
  await page.click('[data-tab="manual"]'); await page.selectOption('[data-role="manual-kind"]', 'category');
  await page.fill('[data-role="label-filter"]', 'Pets'); await page.waitForTimeout(500);
  await page.selectOption('[data-role="label-list"]', 'Pets'); await page.selectOption('[data-role="manual-action"]', 'hide');
  let b = await labDone(); await page.click('[data-role="manual-preview"]'); await done(b, 60000);
  await apply(); let s1 = await state();
  steps.push({step: 'manual hide Pets', ...brief(s1)});
  check('Manual: positive — no shown video carries Pets', Object.values(s1.cats).every(c => !c.includes('Pets')) && s1.eligible < start.eligible, `${start.eligible} -> ${s1.eligible}`);
  check('Manual: negative — nothing outside Pets removed (eligible drop equals the Pets count)', start.eligible - s1.eligible === (await page.evaluate(u => fetch(`/api/lab/labels?user_id=${u}&kind=category&q=Pets&limit=50`).then(r => r.json()), user)).labels.find(l => l.value === 'Pets').item_count);
  await undo(); check('Manual: Undo restores the exact state', same(await state(), start));

  // 2. Interpret: positive = literal request proposes the label; nonliteral pets request proposes an animal hide;
  //    negative = abstain example changes nothing.
  const interpret = async (request) => { await page.click('[data-tab="interpret"]'); await page.fill('[data-role="request"]', request);
    const b = await labDone(); await page.click('[data-role="interpret-preview"]'); await done(b); return [await preview(), await lastErr()]; };
  let [p, err] = await interpret(ex.interpret[1].request);
  check('Interpret: positive literal — "more basketball" proposes a Basketball control', p && p.applicable && p.controls.some(c => /basketball/i.test(c) && /more/i.test(c)), err || (p && p.controls.join('; ')));
  if (p && p.applicable) { const before = await state(); await apply(); const a = await state();
    steps.push({step: 'interpret basketball', ...brief(a)}); check('Interpret: Apply changes the ranking', rankChanged(a, before));
    await undo(); check('Interpret: Undo restores the exact state', same(await state(), before)); }
  [p, err] = await interpret(ex.interpret[4].request);
  check('Interpret: positive nonliteral — the pets request proposes hiding/reducing animal labels', p && p.applicable && p.controls.some(c => /(hide|less)/i.test(c) && /(pet|animal|cat|dog)/i.test(c)), err || (p && p.controls.join('; ')));
  if (p && p.applicable) { await page.click('[data-role="discard"]').catch(() => {}); }
  [p, err] = await interpret(ex.interpret_abstain[0].request);
  check('Interpret: negative — the abstain request changes nothing (the call succeeded)', p && !err && !p.applicable && p.controls.length === 0, err || (p && `applicable ${p.applicable}`));
  await page.click('[data-role="discard"]').catch(() => {});
  check('Interpret: feed unchanged after the previews', same(await state(), start));

  // 3. New category: positive = Dogs selects members that become a filter; negative = Voyager selects none.
  const defineClassify = async (description, label) => {
    await page.click('[data-tab="category"]'); await page.fill('[data-role="category-description"]', description);
    await page.selectOption('[data-role="scope"]', scope);
    let b = await labDone(); await page.click('[data-role="define"]'); await done(b);
    const d = await page.evaluate(() => window.labLastDefinition || null);
    if (!d || d.status !== 'propose') return [d, null];
    if (label) await page.fill('[data-role="definition-label"]', label);
    await page.selectOption('[data-role="category-action"]', 'boost').catch(() => {});
    b = await labDone(); await page.click('[data-role="classify"]'); await done(b);
    return [d, await preview()];
  };
  let [d, q] = await defineClassify(ex.new_category[2].description, 'Dogs');
  const selected = q ? q.selected : 0;
  check('New category: positive — Dogs selects at least one member of the scope', selected > 0, `${selected} of ${q ? q.rows : 0}; definition status ${d && d.status}`);
  let catState = null;
  if (q && q.applicable) { const before = await state(); await apply(); catState = await state();
    steps.push({step: 'new category Dogs applied', selected, ...brief(catState)});
    check('New category: Apply stores exactly the selected members and changes the ranking',
      (catState.custom.Dogs || []).length === selected && rankChanged(catState, before), JSON.stringify(catState.custom));
  }
  const [d2, q2] = await defineClassify(ex.new_category_negative[0].description, null);
  const e2 = await lastErr();
  check('New category: negative — the Voyager description selects no member (the calls succeeded)', d2 && !e2 && (!q2 || q2.selected === 0), e2 || `definition ${d2 && d2.status}; selected ${q2 ? q2.selected : 0}`);
  await page.click('[data-role="discard"]').catch(() => {});

  // 4. New items: positive = the puppy video joins Dogs; negative = the cooking video does not.
  const addItem = async (item) => { await page.click('[data-tab="items"]'); await page.fill('[data-role="new-title-0"]', item.title);
    await page.fill('[data-role="new-description-0"]', item.description); const b = await labDone();
    await page.click('[data-role="new-items-preview"]'); await done(b); return [await preview(), await lastErr()]; };
  let [ni, e3] = await addItem(ex.new_items[1].items[0]);
  check('New items: negative — the cooking video does not join Dogs (a Dogs category exists and the preview succeeded)', catState && ni && !e3 && ni.joined === 0, e3 || `joined ${ni && ni.joined}`);
  await page.click('[data-role="discard"]').catch(() => {});
  [ni, e3] = await addItem(ex.new_items[2].items[0]);
  check('New items: positive — the puppy video joins Dogs (match + quotation + independent check)', ni && ni.joined === 1, e3 || `joined ${ni && ni.joined}`);
  if (ni && ni.applicable) { const before = await state(); await apply(); const a = await state();
    steps.push({step: 'new item added', ...brief(a)});
    check('New items: the item is added', a.added.length === before.added.length + 1, a.added.join(', '));
    await undo(); check('New items: Undo removes the item and restores the exact state', same(await state(), before)); }

  // Reset restores the exact start.
  b = await labDone(); await page.click('[data-role="lab-reset"]'); await done(b, 60000);
  const end = await state(); steps.push({step: 'after Reset', ...brief(end)});
  check('Reset restores the exact start state (full ranking, ids, order, no controls, no categories, no items)', same(end, start));
  check('No page errors', errors.length === 0, errors.join(' | '));
  const calls = await page.evaluate(() => fetch('/api/lab/calls').then(r => r.json()));
  await browser.close();
  const failed = checks.filter(c => !c.ok).length;
  fs.writeFileSync(path.join(out, 'live-receipt.json'), JSON.stringify({base, provider, model, effort, scope, user,
    seconds: (Date.now() - t0) / 1000, passed: checks.length - failed, failed, checks, steps,
    model_calls: calls.calls.length, provider_reported_or_estimated_usd: calls.total_usd,
    unknown_cost_calls: calls.calls.filter(c => c.cost_usd === null || c.cost_usd === undefined).length,
    call_errors: calls.calls.filter(c => c.error).map(c => String(c.error).slice(0, 200))}, null, 1));
  console.log(`OUTCOME ${failed ? failed + ' check(s) failed' : 'all live checks passed'} (${checks.length} checks)`);
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
