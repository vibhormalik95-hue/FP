#!/usr/bin/env node
/*
 * Drive the served Feed Control Lab through its language controls in a real
 * browser and record what the interface and the server state actually did.
 *
 *   node tests/browser/demo_flows.cjs --base http://127.0.0.1:8765 \
 *        --scenario tags --flows manual,vocabulary,mixed --out runs/browser-01
 *
 * Flows
 *   manual       existing category chosen by hand; no model call
 *   category     natural-language objective -> definition review -> membership and
 *                evidence review of every supplied item -> preview -> apply -> undo
 *   indirect     one indirect request matched to item descriptions (action call,
 *                then item call) -> preview -> apply -> undo
 *   description  the same description route, on a scenario that also has
 *                categories and tags
 *   vocabulary   one request matched to existing category and tag names (one
 *                call) -> three review blocks -> preview -> apply -> undo
 *   mixed        one request with several preferences -> one review with a row
 *                group for each control -> one Apply -> undo
 *   outcomes     requests that must not change the feed: ambiguous, unsupported,
 *                negated command, no match. The observed class is recorded beside
 *                the authored expectation; only the invariants are asserted.
 *   fictional    fictional item metadata: draft -> review -> admit to the
 *                separate feed -> remove
 *
 * For each flow the script checks, against the server's own state, that a
 * preview changes nothing, that Apply has exactly the approved effect, and
 * that the two-step Undo restores the exact starting feed.
 *
 * Review gates. With --review auto the script ticks the review boxes itself;
 * use that only with the scripted provider. With --review wait it stops at each
 * gate, writes gate-<name>.json and a screenshot into --out, and continues only
 * when decision-<name>.txt contains APPROVE. Anything else is recorded as a
 * decline and the flow stops with nothing applied.
 *
 * The receipt lists the script's own checks under "checks", the reviewer's
 * decisions under "review_decisions" and every provider call under
 * "provider_calls". A provider call is a model call only when the declared
 * provider is a model: the scripted provider answers with hand-written replies.
 * The script reports which provider the server declared. It never labels a run
 * as live inference by itself: that depends on the provider line in the receipt.
 * Exit code 0 means every flow completed; 2 means a flow stopped early (for
 * example a declined review or a rejected reply); 1 means a check failed.
 *
 * With --video the script records the page to <out>/video/<scenario>.webm. It
 * then scrolls each thing that it checks into view and pauses, so that the
 * recording shows it. It adds nothing to the page. The receipt lists the time
 * of each step in the recording.
 *
 * Needs the "playwright" package and its Chromium browser:
 *   npm install --no-save playwright && npx playwright install chromium
 */
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const crypto = require('crypto');
const { chromium } = require('playwright');

const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, value, index, all) => {
  if (value.startsWith('--')) pairs.push([value.slice(2), all[index + 1] && !all[index + 1].startsWith('--') ? all[index + 1] : 'true']);
  return pairs;
}, []));
const BASE = (args.base || 'http://127.0.0.1:8765').replace(/\/$/, '');
const SCENARIO = args.scenario || 'category';
const OUT = path.resolve(args.out || 'browser-run');
const REVIEW = args.review || 'auto';
const STAGE_TIMEOUT = Number(args['stage-timeout'] || 1200) * 1000;
const GATE_TIMEOUT = Number(args['gate-timeout'] || 280) * 1000;
const TOKEN = process.env[args['token-env'] || 'FEEDCTRL_OPERATOR_TOKEN'] || '';
const VIDEO = Boolean(args.video) && args.video !== 'false';
const USER = 1;
const WEIGHT = { light: 0.10, standard: 0.25, strong: 0.40 };

// The manual category of each bundled scenario and the flows that it supports.
// Request texts are not repeated here: the script reads them from /api/status.
const SCENARIOS = {
  category: { manualCategory: 'K1', flows: 'manual,category' },
  hunger: { manualCategory: 'Repair', flows: 'manual,indirect' },
  tags: { manualCategory: 'Cooking', flows: 'manual,vocabulary,mixed,outcomes,description,fictional' },
};
// Authored expectation for each request that must not change the feed.
const OUTCOME_CASES = { ambiguous: 'clarify', unsupported: 'unsupported', negated: 'clarify', no_match: 'no_match' };
const scenario = SCENARIOS[SCENARIO];
if (!scenario) throw new Error('Unknown scenario ' + SCENARIO);
if (!['auto', 'wait'].includes(REVIEW)) throw new Error('--review must be auto or wait');
const FLOWS = (args.flows || scenario.flows).split(',');

fs.mkdirSync(OUT, { recursive: true });
if (fs.readdirSync(OUT).length) throw new Error('--out must be a new or empty folder: an old decision file must never approve a new review');
const receipt = {
  kind: 'browser run of the served application',
  started_utc: new Date().toISOString(), base: BASE, scenario: SCENARIO, flows: FLOWS, review_mode: REVIEW,
  reviewer: args.reviewer || (REVIEW === 'auto' ? 'none: review boxes ticked by the script' : 'not stated'),
  source_fingerprint: null, status: null, checks: [], review_decisions: [], flows_result: {}, provider_calls: [], screenshots: [], finished_utc: null, outcome: 'started',
};
const save = () => fs.writeFileSync(path.join(OUT, 'browser-receipt.json'), JSON.stringify(receipt, null, 2));
const utc = () => new Date().toISOString();
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
let shotIndex = 0;

function check(name, condition, detail) {
  const passed = Boolean(condition);
  receipt.checks.push({ name, passed, detail: detail === undefined ? null : detail, utc: utc() });
  save();
  console.log(`${passed ? 'PASS' : 'FAIL'}  ${name}${detail === undefined ? '' : '  ' + JSON.stringify(detail)}`);
  if (!passed) throw new Error('Check failed: ' + name);
}

(async () => {
  const browser = await chromium.launch();
  const size = { width: 1440, height: VIDEO ? 1080 : 1100 };
  const context = await browser.newContext({ viewport: size, deviceScaleFactor: 1,
    ...(VIDEO ? { recordVideo: { dir: path.join(OUT, 'video'), size } } : {}) });
  const page = await context.newPage();
  const videoStarted = Date.now();
  if (VIDEO) receipt.video = { file: null, steps: [] };
  // For the recording only: note the time of a step, bring its region into view and pause.
  async function show(label, locator, pause = 2500) {
    if (!VIDEO) return;
    receipt.video.steps.push({ seconds: Number(((Date.now() - videoStarted) / 1000).toFixed(1)), step: label });
    save();
    // Put the top of the region at the top of the frame, so that its heading is in the recording.
    if (locator) { try { await locator.first().evaluate(node => node.scrollIntoView({ block: 'start', behavior: 'instant' }), null, { timeout: 5000 }); } catch (_) { /* region not present */ } }
    await page.waitForTimeout(pause);
  }
  let session = null;
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('response', async response => {
    const url = response.url();
    if (!url.startsWith(BASE + '/api/')) return;
    let body = null;
    try { body = await response.json(); } catch (_) { return; }
    if (url.endsWith('/api/session') && body && body.session_id) session = body.session_id;
    // Keep provider facts only: hashes, timing and declared identity, never reply text.
    for (const key of ['model_calls', 'evidence_audit_model_calls']) {
      for (const call of (body && Array.isArray(body[key]) ? body[key] : [])) {
        const requestHash = call.producer_payload_sha256 || call.request_sha256 || null;
        const responseHash = call.raw_response_sha256 || call.response_sha256 || null;
        if (receipt.provider_calls.some(seen => seen.request_sha256 === requestHash && seen.response_sha256 === responseHash)) continue;
        receipt.provider_calls.push({
          route: url.slice(BASE.length), list: key, stage: call.stage || null, status: call.status || null,
          elapsed_seconds: typeof call.elapsed_seconds === 'number' ? Number(call.elapsed_seconds.toFixed(3)) : null,
          request_sha256: requestHash, response_sha256: responseHash,
          declared_provider: call.model_provenance || body.model_provenance || null, observed_utc: utc(),
        });
      }
    }
    save();
  });

  const shot = async name => {
    const file = `${String(++shotIndex).padStart(2, '0')}-${name}.png`;
    await page.screenshot({ path: path.join(OUT, file), fullPage: true });
    receipt.screenshots.push(file);
    save();
  };
  const headers = () => ({ 'X-Session-ID': session, ...(TOKEN ? { 'X-Personal-Operator-Token': TOKEN } : {}) });
  const serverState = async () => {
    const response = await context.request.get(`${BASE}/api/semantic/groups?user_id=${USER}`, { headers: headers() });
    assert.strictEqual(response.status(), 200, 'semantic state read failed');
    return response.json();
  };
  const fictionalState = async () => {
    const response = await context.request.get(`${BASE}/api/synthetic/items?user_id=${USER}`, { headers: headers() });
    assert.strictEqual(response.status(), 200, 'fictional item state read failed');
    return response.json();
  };
  const shownIds = async () => (await page.locator('.item-card h3').allInnerTexts()).map(text => Number(text.replace('Item ', '')));
  const panel = page.locator('section[aria-label="Language controls panel"]');
  const board = page.locator('section[aria-label="Review board"]');
  const status = () => panel.locator('p[role="status"]');
  const variant = async () => (await board.count()) ? board.getAttribute('data-variant') : null;
  // The decision block holds one primary button: "Approve this exact item set and apply", "Approve the undo" or "Approve: remove every control".
  const approve = (name = 'Approve this exact item set and apply') => board.locator('section[data-block="decision"]').getByRole('button', { name, exact: true });
  // A server with hand-written replies never calls them model output. The manual method, Undo and Clear have no reply: their first block is "Your selection".
  const authored = () => Boolean(receipt.status && receipt.status.provider && receipt.status.provider.live_model === false);
  const replyBlock = () => authored() ? 'Authored reply (written by hand, not a model)' : 'Model output (not verified)';
  const blocksOf = first => [first, 'Application checks', 'Your decision'];
  // Choose a method of the language controls: one radio button for each method.
  const chooseMethod = value => panel.locator(`input[name="semantic-method"][value="${value}"]`).check();

  // Press a control and return the server's own JSON answer to the call that it starts.
  async function submit(press, route, timeout) {
    const answer = page.waitForResponse(response => response.url() === BASE + route && response.request().method() === 'POST', { timeout });
    await press();
    const response = await answer;
    let body = null;
    try { body = await response.json(); } catch (_) { /* an error page without JSON */ }
    // The page shows the result in the same tick; wait until it no longer says that it works.
    await page.waitForFunction(() => { const button = document.querySelector('section[aria-label="Language controls panel"] button.primary'); return button && !/^(Waiting for the provider|Reading the authored reply|Working)/.test(button.innerText); }, null, { timeout: 30000 });
    return { http: response.status(), body };
  }

  // Use the page's own control for a bundled request and confirm that the box holds the exact text.
  async function insertRequest(key) {
    const expected = receipt.status.scenario_requests ? receipt.status.scenario_requests[key] : undefined;
    check(`the server supplies the bundled request "${key}"`, typeof expected === 'string' && expected.length > 0);
    if (key.includes(':')) await panel.locator('#semantic-example').selectOption(key);
    else await panel.getByRole('button', { name: 'Insert the bundled scenario request' }).click();
    check(`the request text is the exact bundled request "${key}"`, await panel.locator('#semantic-text').inputValue() === expected);
    return expected;
  }

  async function gate(name, region) {
    // Open the raw model replies, as a reviewer would, so that the gate text and the screenshot hold them.
    await region.locator('details.raw').evaluateAll(nodes => nodes.forEach(node => { node.open = true; }));
    const text = await region.innerText();
    await shot(`gate-${name}`);
    if (REVIEW === 'auto') return true;
    const request = path.join(OUT, `gate-${name}.json`);
    const decision = path.join(OUT, `decision-${name}.txt`);
    fs.writeFileSync(request, JSON.stringify({ gate: name, shown_utc: utc(), expires_in_seconds: GATE_TIMEOUT / 1000, visible_text: text }, null, 2));
    console.log(`WAIT  review gate "${name}": write APPROVE into ${decision}`);
    const started = Date.now();
    while (!fs.existsSync(decision)) {
      if (Date.now() - started > GATE_TIMEOUT) { receipt.review_decisions.push({ gate: name, decision: null, note: 'no decision before the review window closed', utc: utc() }); save(); return false; }
      await page.waitForTimeout(500);
    }
    const answer = fs.readFileSync(decision, 'utf8').trim();
    // A decision is the reviewer's act. It is recorded apart from the script's own checks.
    receipt.review_decisions.push({ gate: name, decision: answer.slice(0, 200), seconds_to_decide: Number(((Date.now() - started) / 1000).toFixed(1)), utc: utc() });
    save();
    return answer === 'APPROVE';
  }

  // The controls that a reviewed plan adds to the applied state, from the server's own answer.
  function newControls(review, baseline) {
    const applied = new Set(baseline.groups.map(group => group.revision));
    return review.groups.filter(group => !applied.has(group.revision)).map(group => ({
      label: group.label, operation: group.proposal.action.operation, strength: group.proposal.action.strength,
      intent_span: group.proposal.action.intent_span, item_ids: [...group.proposal.item_ids].sort((a, b) => a - b),
    }));
  }

  // The rows of the evidence table, for each control: what the page itself shows.
  async function tableGroups() {
    return page.locator('section[aria-label="Review of every supplied item"] tbody').evaluateAll(bodies => bodies.map(body => ({
      label: body.dataset.group, route: body.dataset.route, fresh: body.dataset.new === 'true',
      rows: [...body.querySelectorAll('tr[data-item]')].map(row => ({
        id: Number(row.dataset.item), member: row.dataset.member === 'true', marked: row.classList.contains('review-member'),
        verdict: row.dataset.verdict || null, assessment: row.dataset.assessment || null,
        description: row.querySelectorAll('td')[0].innerText.trim(), labels: row.querySelectorAll('td')[1].innerText.trim(),
        evidence: row.querySelectorAll('td')[2].innerText.trim(), result: row.querySelector('td:last-child b').innerText.trim() })),
    })));
  }

  // Provider calls that the server reported in its answers to one flow.
  const callsIn = (...bodies) => bodies.reduce((sum, body) => sum + ['model_calls', 'evidence_audit_model_calls'].reduce(
    (count, key) => count + (body && Array.isArray(body[key]) ? body[key].length : 0), 0), 0);

  // What Apply must do to the starting feed, computed from the approved controls alone.
  function expectedFeed(baseline, controls) {
    const removed = new Set(controls.filter(control => control.operation === 'exclude').flatMap(control => control.item_ids));
    const delta = {};
    for (const control of controls.filter(c => c.operation !== 'exclude')) for (const id of control.item_ids)
      delta[id] = (delta[id] || 0) + (control.operation === 'boost' ? 1 : -1) * WEIGHT[control.strength];
    const kept = baseline.feed.items.filter(item => !removed.has(item.item_id));
    // With more eligible items than the first ten, other items can enter the list; then only the listed ones are compared.
    return { removed: [...removed].sort((a, b) => a - b), kept: kept.map(item => item.item_id).sort((a, b) => a - b), delta,
      complete: baseline.feed.available_items === baseline.feed.items.length,
      scores: Object.fromEntries(kept.map(item => [item.item_id, item.base_score + (delta[item.item_id] || 0)])) };
  }

  async function applyAndUndo(flow, baseline, record, review) {
    const controls = newControls(review, baseline);
    record.controls = controls;
    record.selected_ids = [...new Set(controls.flatMap(control => control.item_ids))].sort((a, b) => a - b);
    const preview = await serverState();
    check(`${flow}: preview left the applied feed unchanged`, same(preview.feed, baseline.feed) && preview.groups.length === 0 && preview.revision === baseline.revision,
      { applied_groups: preview.groups.length, revision: preview.revision, eligible: preview.feed.available_items });
    check(`${flow}: page still shows the starting items during preview`, same(await shownIds(), record.shown_before), { shown: await shownIds() });
    check(`${flow}: the review names at least one item that would change`, record.selected_ids.length > 0, { controls });

    const boardText = await board.innerText();
    record.review_text_sha256 = crypto.createHash('sha256').update(boardText).digest('hex');
    fs.writeFileSync(path.join(OUT, `${flow}-final-review.txt`), boardText);
    const present = {};
    const blocks = blocksOf(flow === 'manual' ? 'Your selection' : replyBlock());
    for (const title of blocks) present[title] = await board.locator(`section[aria-label="${title}"]`).count();
    check(`${flow}: the review has three separate blocks (${blocks[0]}, application checks, decision) and says that nothing is applied`,
      blocks.every(title => present[title] === 1) && /NOTHING IS APPLIED YET/.test(boardText) && /Nothing has changed yet\./.test(boardText), present);
    for (const control of controls) check(`${flow}: the decision block names the control "${control.label}" and its items`,
      (await board.locator('section[aria-label="Your decision"]').innerText()).includes(control.label), { items: control.item_ids });

    const groups = await tableGroups();
    const expectedText = Object.fromEntries(baseline.feed.items.map(item => [item.item_id, item.source_text]));
    for (const control of controls) {
      const body = groups.find(group => group.label === control.label);
      const marked = body ? body.rows.filter(row => row.marked).map(row => row.id).sort((a, b) => a - b) : null;
      check(`${flow}: the evidence table lists every supplied item once for "${control.label}", with its own description, and marks exactly the approved ones`,
        Boolean(body) && body.fresh && body.rows.length === baseline.feed.items.length && new Set(body.rows.map(row => row.id)).size === body.rows.length
          && same(marked, control.item_ids) && body.rows.every(row => row.marked === row.member)
          && body.rows.every(row => row.description === (expectedText[row.id] || 'No description supplied'))
          && body.rows.every(row => row.member ? /^(selected|match)/.test(row.evidence) : !/^selected/.test(row.evidence)),
        { rows: body ? body.rows.length : 0, marked });
    }
    const expected = expectedFeed(baseline, controls);
    const resultOf = id => { const row = groups.flatMap(group => group.rows).find(candidate => candidate.id === id); return row ? row.result : null; };
    check(`${flow}: the table states the result for each item that the approved controls remove`,
      expected.removed.every(id => resultOf(id) === 'Removed from the feed'), { removed: expected.removed });
    fs.writeFileSync(path.join(OUT, `${flow}-review-table.txt`), await page.locator('section[aria-label="Review of every supplied item"]').innerText());
    const before = page.locator('section[aria-label="Preview of the feed before and after"]');
    check(`${flow}: the preview lists the feed now and after approval and says that the applied feed is unchanged`,
      /The applied feed is unchanged until you approve\./.test(await before.innerText())
        && same(await before.locator('[aria-label="First ten items now"] li').evaluateAll(rows => rows.map(row => Number(row.dataset.item))), baseline.feed.items.map(item => item.item_id)),
      { after: await before.locator('[aria-label="First ten items after approval"] li').evaluateAll(rows => rows.map(row => Number(row.dataset.item))) });
    await show(`${flow}: three review blocks (model output, application checks, your decision); nothing applied`, board, 6000);
    await show(`${flow}: evidence table of every supplied item`, page.locator('section[aria-label="Review of every supplied item"]'), 6000);
    await show(`${flow}: the feed now and after approval`, before, 4000);
    await show(`${flow}: the feed is unchanged during the preview`, page.locator('.item-card'), 3000);
    await show(`${flow}: the decision block with the approve button; waiting for the reviewer`, approve(), 2000);
    if (!await gate(`${flow}-apply`, board)) { record.outcome = 'declined before apply; nothing applied'; return; }

    await submit(() => approve().click(), '/api/semantic/apply', 30000);
    await page.waitForFunction(() => { const node = document.querySelector('section[aria-label="Review board"] [aria-label="What changed"]'); return node && node.dataset.kind === 'apply'; }, null, { timeout: 30000 });
    const applied = await serverState();
    const appliedIds = applied.feed.items.map(item => item.item_id);
    record.eligible_after_apply = applied.feed.available_items;
    check(`${flow}: Apply removed exactly the items of the approved removal controls`,
      applied.feed.available_items === baseline.feed.available_items - expected.removed.length
        && expected.removed.every(id => !appliedIds.includes(id)) && (!expected.complete || same([...appliedIds].sort((a, b) => a - b), expected.kept)),
      { eligible_before: baseline.feed.available_items, eligible_after: applied.feed.available_items, removed: expected.removed });
    check(`${flow}: Apply changed the score of exactly the items of the approved rank controls, by the stated amount`,
      applied.feed.items.every(item => Math.abs(item.score - item.base_score - (expected.delta[item.item_id] || 0)) < 1e-9),
      { changed: applied.feed.items.filter(item => Math.abs(item.score - item.base_score) > 1e-9).map(item => ({ id: item.item_id, by: Number((item.score - item.base_score).toFixed(2)) })) });
    check(`${flow}: exactly the approved controls are applied`, same(applied.groups.map(group => group.label).sort(), controls.map(control => control.label).sort()), { applied: applied.groups.map(group => group.label) });
    check(`${flow}: page shows the feed that the server holds`, same(await shownIds(), appliedIds), { shown: await shownIds() });
    const changed = await board.locator('[aria-label="What changed"]').innerText();
    check(`${flow}: the page records what changed and how to undo it`, controls.every(control => changed.includes(control.label)) && /To undo:/.test(changed));
    record.shown_after_apply = await shownIds();
    await shot(`${flow}-applied`);
    await show(`${flow}: applied; the page records what changed`, board, 4000);
    await show(`${flow}: the feed shows the applied result`, page.locator('h2', { hasText: 'The feed with your applied controls' }), 4000);

    // Undo is two explicit steps: ask for the undo review, then approve it.
    await submit(() => panel.getByRole('button', { name: 'Undo the last change (review first)' }).click(), '/api/semantic/history/preview', 30000);
    await page.waitForFunction(() => document.querySelector('section[aria-label="Review board"]')?.dataset.variant === 'review', null, { timeout: 30000 });
    const undoPreview = await serverState();
    check(`${flow}: undo review alone changed nothing`, same(undoPreview.feed, applied.feed) && undoPreview.groups.length === applied.groups.length,
      { eligible: undoPreview.feed.available_items });
    await show(`${flow}: undo review (step 1 of 2); nothing changed yet`, approve('Approve the undo'), 3000);
    if (!await gate(`${flow}-undo`, board)) { record.outcome = 'undo declined; control still applied'; return; }
    await submit(() => approve('Approve the undo').click(), '/api/semantic/apply', 30000);
    await page.waitForFunction(() => { const node = document.querySelector('section[aria-label="Review board"] [aria-label="What changed"]'); return node && node.dataset.kind === 'undo'; }, null, { timeout: 30000 });
    const restored = await serverState();
    record.eligible_after_undo = restored.feed.available_items;
    check(`${flow}: Undo restored the exact starting feed`, same(restored.feed, baseline.feed) && restored.groups.length === 0,
      { eligible: restored.feed.available_items, identical_to_start: same(restored.feed, baseline.feed), revision: restored.revision });
    check(`${flow}: page shows the starting items again and says that the earlier feed is restored`,
      same(await shownIds(), record.shown_before) && /The earlier feed is restored/.test(await board.innerText()), { shown: await shownIds() });
    await shot(`${flow}-restored`);
    await show(`${flow}: undo approved (step 2 of 2); the starting feed is restored`, board, 4000);
    record.outcome = 'completed: preview unchanged, apply exact, undo restored';
  }

  async function startFlow(flow) {
    const baseline = await serverState();
    const record = { started_utc: utc(), eligible_before: baseline.feed.available_items, shown_before: await shownIds(), outcome: 'started' };
    receipt.flows_result[flow] = record;
    check(`${flow}: starts with no applied control`, baseline.groups.length === 0, { eligible: baseline.feed.available_items });
    return { baseline, record };
  }

  // A result that is not a review: record what the page and the server say, and stop the flow.
  async function stopped(flow, record, answer) {
    record.outcome = `no proposal to review: ${answer.body && answer.body.status ? answer.body.status : 'HTTP ' + answer.http}: ${((answer.body && (answer.body.reason || answer.body.detail)) || (await status().innerText()) || '').slice(0, 300)}`;
    await shot(`${flow}-stopped`);
  }

  // The description route: call 1 reads the action, call 2 selects items with quotations.
  async function describedFlow(flow) {
    const { baseline, record } = await startFlow(flow);
    await chooseMethod('configured_model');
    const request = await insertRequest('configured_model');
    await shot(`${flow}-request`);
    await show(`${flow}: request entered; it names no category`, panel.locator('#semantic-text'), 4000);
    await show(`${flow}: waiting for the model (action, then items)`, null, 1000);
    const answer = await submit(() => panel.getByRole('button', { name: 'Interpret my request' }).click(), '/api/semantic/preview', STAGE_TIMEOUT);
    record.provider_calls = callsIn(answer.body);
    if (!answer.body || answer.body.ready !== true) return stopped(flow, record, answer);
    const [control] = newControls(answer.body, baseline);
    record.interpreted_action = `${control.operation}/${control.strength}`;
    check(`${flow}: the original request is shown unchanged above the three blocks`, (await board.locator('p.your-request').first().innerText()).includes(request));
    await shot(`${flow}-review`);
    await applyAndUndo(flow, baseline, record, answer.body);
  }

  const flows = {
    async manual() {
      const { baseline, record } = await startFlow('manual');
      await chooseMethod('manual_category');
      const category = panel.locator('#semantic-category');
      if (await category.evaluate(node => node.tagName) === 'SELECT') await category.selectOption(scenario.manualCategory); else await category.fill(scenario.manualCategory);
      await panel.locator('#semantic-operation').selectOption('exclude');
      const callsBefore = receipt.provider_calls.length;
      check('manual: the stage line marks the interpretation stage as not used', await panel.locator('ol.stage-line li').nth(1).getAttribute('data-state') === 'skipped');
      await show('manual: existing category and action chosen by hand', panel.locator('#semantic-category'), 2500);
      const answer = await submit(() => panel.getByRole('button', { name: 'Show the proposed change' }).click(), '/api/semantic/preview', 30000);
      check('manual: review appears', answer.body && answer.body.ready === true && await variant() === 'review', { http: answer.http });
      check('manual: the server reported no model call for this review', receipt.provider_calls.length === callsBefore && (answer.body.model_calls || []).length === 0, { model_calls: receipt.provider_calls.length - callsBefore });
      check('manual: the first block is "Your selection", says that no model is used, and no model block exists',
        /No model is used\./.test(await board.locator('section[aria-label="Your selection"]').innerText())
          && await board.locator('section[aria-label="Model output (not verified)"], section[aria-label="Authored reply (written by hand, not a model)"]').count() === 0);
      await shot('manual-review');
      await applyAndUndo('manual', baseline, record, answer.body);
      record.provider_calls = 0;
    },

    async category() {
      const { baseline, record } = await startFlow('category');
      await chooseMethod('staged');
      await insertRequest('staged');
      await panel.locator('#semantic-operation').selectOption('exclude');
      await shot('category-objective');
      await show('category: natural-language objective entered', panel.locator('#semantic-text'), 4000);
      await show('category: waiting for the model (definition)', null, 1000);
      let answer = await submit(() => panel.getByRole('button', { name: 'Propose a definition for review' }).click(), '/api/semantic/definition/preview', STAGE_TIMEOUT);
      record.provider_calls = callsIn(answer.body);
      const definition = board.locator('[aria-label="Category definition review"]');
      const resolution = board.locator('[aria-label="Unresolved semantic interpretations"]');
      if (await variant() === 'resolution') {
        // The model returned a primary definition with competing meanings.
        record.competing_meanings_shown = true;
        fs.writeFileSync(path.join(OUT, 'category-resolution.txt'), await resolution.innerText());
        await show('category: the model returned competing meanings; waiting for the reviewer', resolution, 6000);
        if (!await gate('category-resolution', resolution)) { record.outcome = 'declined at competing meanings; nothing applied'; return; }
        await resolution.getByRole('checkbox').check();
        answer = await submit(() => resolution.getByRole('button', { name: 'Continue to definition review' }).click(), '/api/semantic/definition/resolve', 30000);
      }
      if (await variant() !== 'definition') return stopped('category', record, answer);
      fs.writeFileSync(path.join(OUT, 'category-definition-review.txt'), await definition.innerText());
      record.definition_label = (await definition.locator('strong').first().innerText()).trim();
      const afterDefinition = await serverState();
      check('category: definition proposal changed nothing', same(afterDefinition.feed, baseline.feed) && afterDefinition.groups.length === 0, { label: record.definition_label });
      await show('category: definition review (label and definition); waiting for the reviewer', definition.locator('strong'), 8000);
      await show('category: definition review (approve box and button)', definition.getByRole('checkbox'), 3000);
      if (!await gate('category-definition', definition)) { record.outcome = 'definition declined by the reviewer; nothing classified or applied'; return; }
      await definition.getByRole('checkbox').check();
      await show('category: definition approved; waiting for the model (classification, then separate evidence assessment)', null, 1000);
      answer = await submit(() => definition.getByRole('button', { name: 'Approve definition and classify supplied items' }).click(), '/api/semantic/definition/classify', STAGE_TIMEOUT);
      record.provider_calls += callsIn(answer.body);
      if (!answer.body || answer.body.ready !== true) return stopped('category', record, answer);
      const [body] = (await tableGroups()).filter(group => group.fresh);
      record.dispositions = body.rows.map(row => ({ item_id: row.id, verdict: row.verdict }));
      record.evidence_assessments = body.rows.map(row => ({ item_id: row.id, assessment: row.assessment }));
      check('category: every supplied item has one membership decision on screen', body.rows.length === baseline.feed.items.length
        && body.rows.every(row => ['match', 'not_match', 'unknown'].includes(row.verdict)), { shown: body.rows.length, supplied: baseline.feed.items.length });
      check('category: every supplied item has one evidence assessment on screen', body.rows.every(row => ['supported', 'contradicted', 'not_stated', 'ambiguous'].includes(row.assessment)), { shown: body.rows.filter(row => row.assessment).length });
      await shot('category-membership-review');
      await applyAndUndo('category', baseline, record, answer.body);
    },

    indirect: () => describedFlow('indirect'),
    description: () => describedFlow('description'),

    async vocabulary() {
      const { baseline, record } = await startFlow('vocabulary');
      await chooseMethod('vocabulary');
      const listed = panel.locator('[aria-label="Existing categories and tags in the scope"]');
      await page.waitForFunction(() => /Categories:/.test(document.querySelector('[aria-label="Existing categories and tags in the scope"]')?.innerText || ''), null, { timeout: 30000 });
      const terms = await (await context.request.post(`${BASE}/api/semantic/vocabulary/terms`, { headers: headers(), data: { user_id: USER, candidate_ids: baseline.feed.baseline_items.slice(0, 10) } })).json();
      const listedText = await listed.innerText();
      check('vocabulary: the page lists every existing category and tag of the scope before any model call',
        terms.terms.length > 0 && terms.terms.every(term => listedText.includes(`${term.value} (${term.item_ids.length})`)) && /No model was called/.test(terms.note),
        { terms: terms.terms.length, note: terms.note });
      const request = await insertRequest('vocabulary');
      await shot('vocabulary-request');
      await show('vocabulary: the existing categories and tags, and a request that names none of them', listed, 5000);
      await show('vocabulary: waiting for the model (one call)', null, 1000);
      const answer = await submit(() => panel.getByRole('button', { name: 'Interpret my request' }).click(), '/api/semantic/vocabulary/preview', STAGE_TIMEOUT);
      record.provider_calls = callsIn(answer.body);
      if (!answer.body || answer.body.ready !== true) return stopped('vocabulary', record, answer);
      const vocabulary = answer.body.vocabulary;
      record.chosen_terms = vocabulary.controls.map(control => ({ control: control.label, terms: control.terms.map(term => `${term.kind}:${term.value}`) }));
      record.server_checks = vocabulary.checks.map(item => ({ check: item.check, passed: item.passed }));
      const checksText = await board.locator('section[aria-label="Application checks"]').innerText();
      check('vocabulary: every check that the server made is shown as passed in the application checks block',
        vocabulary.checks.length > 0 && vocabulary.checks.every(item => item.passed === true && checksText.includes(item.check))
          && await board.locator('section[aria-label="Application checks"] li[data-passed="false"]').count() === 0, { checks: vocabulary.checks.length });
      const output = await board.locator(`section[aria-label="${replyBlock()}"]`).innerText();
      check('vocabulary: the reply block shows the span of the request and each chosen name',
        vocabulary.controls.every(control => output.includes(control.intent_span) && control.terms.every(term => output.includes(`"${term.value}"`))), record.chosen_terms);
      check('vocabulary: the chosen names are categories or tags, and the request text is not changed',
        vocabulary.controls.every(control => control.terms.every(term => ['category', 'tag'].includes(term.kind) && terms.terms.some(known => known.term_id === term.term_id && known.value === term.value)))
          && answer.body.groups.every(group => group.request === request));
      const rows = (await tableGroups()).flatMap(group => group.rows);
      check('vocabulary: an item that no chosen name selects is listed with its own categories and tags and the reason',
        vocabulary.not_selected.every(entry => { const row = rows.find(candidate => candidate.id === entry.item_id); return row && !row.member && /^not selected:/.test(row.evidence) && entry.terms.every(term => row.labels.includes(term.value)); }),
        { not_selected: vocabulary.not_selected.map(entry => entry.item_id) });
      await shot('vocabulary-review');
      await applyAndUndo('vocabulary', baseline, record, answer.body);
    },

    async mixed() {
      const { baseline, record } = await startFlow('mixed');
      await chooseMethod('vocabulary');
      await insertRequest('vocabulary:mixed');
      await shot('mixed-request');
      await show('mixed: one request with two preferences', panel.locator('#semantic-text'), 4000);
      const answer = await submit(() => panel.getByRole('button', { name: 'Interpret my request' }).click(), '/api/semantic/vocabulary/preview', STAGE_TIMEOUT);
      record.provider_calls = callsIn(answer.body);
      if (!answer.body || answer.body.ready !== true) return stopped('mixed', record, answer);
      const controls = newControls(answer.body, baseline);
      record.controls_in_one_review = controls.length;
      record.authored_expectation = 'two controls in one review';
      record.matches_authored_expectation = controls.length === 2;
      const fresh = (await tableGroups()).filter(group => group.fresh);
      check('mixed: the review shows one row group for each control of the request', fresh.length === controls.length && same(fresh.map(group => group.label), controls.map(control => control.label)), { controls: controls.map(control => `${control.label}: ${control.operation}`) });
      if (controls.length > 1) check('mixed: the decision block says that one approval applies all controls together',
        (await board.locator('section[aria-label="Your decision"]').innerText()).includes(`One approval applies all ${controls.length} new controls together.`));
      await shot('mixed-review');
      await applyAndUndo('mixed', baseline, record, answer.body);
    },

    async outcomes() {
      const { baseline, record } = await startFlow('outcomes');
      await chooseMethod('vocabulary');
      record.cases = [];
      for (const [name, expected] of Object.entries(OUTCOME_CASES)) {
        const key = 'vocabulary:' + name;
        if (!receipt.status.scenario_requests || typeof receipt.status.scenario_requests[key] !== 'string') { record.cases.push({ case: name, skipped: 'the server supplies no such bundled request' }); continue; }
        const request = await insertRequest(key);
        const answer = await submit(() => panel.getByRole('button', { name: 'Interpret my request' }).click(), '/api/semantic/vocabulary/preview', STAGE_TIMEOUT);
        const body = answer.body || {};
        const observed = body.ready === true ? 'ready' : body.status || 'HTTP ' + answer.http;
        // A model can answer in another class than the authored reply. That is recorded, not failed.
        const entry = { case: name, request, authored_expectation: expected, observed, matches_authored_expectation: observed === expected,
          model_calls_reported: Array.isArray(body.model_calls) ? body.model_calls.length : null, reason: typeof body.reason === 'string' ? body.reason.slice(0, 300) : null };
        record.cases.push(entry);
        save();
        if (name === 'negated') check('outcomes: the negated command is stopped by the application without a model call', body.ready !== true && entry.model_calls_reported === 0, { observed });
        if (body.ready === true) {
          // The model proposed a change where the authored reply does not. The script never applies it.
          await shot(`outcomes-${name}-unexpected-proposal`);
          await board.getByRole('button', { name: 'Discard this review and apply nothing' }).click();
          entry.script_action = 'discarded the unexpected proposal; nothing applied';
        } else {
          const shown = board.locator('[aria-label="Result without a proposed change"]');
          const text = (await board.count()) ? await board.innerText() : '';
          check(`outcomes: ${name}: the page shows a result without a change (${observed}) and offers no Apply`,
            (answer.http !== 200 ? await variant() === 'failure' : await shown.getAttribute('data-status') === observed)
              && /NOTHING WAS APPLIED/.test(text) && /Nothing was applied\./.test(text) && await approve().count() === 0 && body.plan_id === undefined, { observed, expected });
          entry.alternatives_shown = await board.locator('[aria-label="Alternatives named in the reply"] li').count();
          await shot(`outcomes-${name}`);
          await show(`outcomes: ${name}: ${observed}; nothing applied`, board, 5000);
        }
        const after = await serverState();
        check(`outcomes: ${name}: the applied feed and the applied controls are unchanged`, same(after.feed, baseline.feed) && after.groups.length === 0 && after.revision === baseline.revision
          && same(await shownIds(), record.shown_before), { observed });
      }
      record.provider_calls = record.cases.reduce((sum, entry) => sum + (entry.model_calls_reported || 0), 0);
      const mismatched = record.cases.filter(entry => entry.matches_authored_expectation === false).map(entry => `${entry.case}: ${entry.observed} (authored: ${entry.authored_expectation})`);
      record.outcome = `completed: ${record.cases.filter(entry => !entry.skipped).length} cases, nothing applied in any of them` + (mismatched.length ? `; classes that differ from the authored expectation: ${mismatched.join('; ')}` : '');
    },

    async fictional() {
      const { baseline, record } = await startFlow('fictional');
      const brief = receipt.status.scenario_requests ? receipt.status.scenario_requests.synthetic : undefined;
      check('fictional: the server supplies an example brief', typeof brief === 'string' && brief.length > 0);
      await page.locator('summary', { hasText: 'Fictional item drafts' }).click();
      const drafts = page.locator('section[aria-label="Synthetic item drafts"]');
      await drafts.getByRole('button', { name: 'Generate fictional metadata draft' }).waitFor({ state: 'visible', timeout: 30000 });
      const start = await fictionalState();
      check('fictional: starts with no fictional item', start.items.length === 0 && start.generation_available !== false, { provider: start.generation_provider });
      await drafts.getByRole('button', { name: 'Insert the example brief' }).click();
      check('fictional: the brief is the exact example brief', await drafts.locator('#synthetic-brief').inputValue() === brief);
      await drafts.getByRole('checkbox').check();
      await show('fictional: a brief for an item that does not exist', drafts.locator('#synthetic-brief'), 4000);
      const draft = page.waitForResponse(response => response.url() === BASE + '/api/synthetic/preview', { timeout: STAGE_TIMEOUT });
      await drafts.getByRole('button', { name: 'Generate fictional metadata draft' }).click();
      const drafted = await (await draft).json();
      record.provider_calls = Array.isArray(drafted.model_calls) ? drafted.model_calls.length : null;
      if (drafted.ready !== true) { record.outcome = `no draft to review: ${drafted.status || 'error'}: ${(drafted.reason || '').slice(0, 300)}`; await shot('fictional-stopped'); return; }
      const reviewBlock = drafts.locator('[aria-label="Fictional draft review"]');
      await reviewBlock.waitFor({ state: 'visible', timeout: 30000 });
      record.draft = { item_id: drafted.draft.item_id, origin: drafted.draft.origin, title_sha256: crypto.createHash('sha256').update(drafted.draft.title).digest('hex') };
      const afterDraft = await fictionalState();
      check('fictional: the draft is shown for review and adds nothing', afterDraft.items.length === 0 && (await reviewBlock.innerText()).includes(drafted.draft.title)
        && same((await serverState()).feed, baseline.feed), { origin: drafted.draft.origin });
      check('fictional: the draft is marked as generated fictional metadata without a media asset',
        drafted.draft.origin === 'model_generated_synthetic' && drafted.draft.is_synthetic === true && drafted.draft.media_asset === null && /^synthetic-[a-f0-9]{24}$/.test(drafted.draft.item_id));
      await shot('fictional-draft');
      await show('fictional: the draft; waiting for the reviewer', reviewBlock, 6000);
      if (!await gate('fictional-admit', reviewBlock)) { record.outcome = 'draft declined by the reviewer; nothing admitted'; return; }
      const admit = page.waitForResponse(response => response.url() === BASE + '/api/synthetic/admit', { timeout: 30000 });
      await reviewBlock.getByRole('button', { name: 'Approve fictional draft and admit to synthetic feed' }).click();
      await admit;
      const admitted = await fictionalState();
      const observed = await serverState();
      check('fictional: the approved item is in the separate feed only', admitted.items.length === 1 && admitted.items[0].item_id === drafted.draft.item_id
        && admitted.feed.isolated_from_observed_catalogue === true && admitted.feed.uses_trained_scorer === false && admitted.feed.items.length === 1 && admitted.feed.items[0].score === 0,
        { separate_feed_ids: admitted.feed.items.map(item => item.item_id) });
      check('fictional: the observed feed and its items are unchanged', same(observed.feed, baseline.feed) && same(await shownIds(), record.shown_before)
        && !(await shownIds()).some(id => String(id) === drafted.draft.item_id), { eligible: observed.feed.available_items });
      await shot('fictional-admitted');
      await show('fictional: admitted to the separate feed; the observed feed is unchanged', drafts.locator('article').first(), 5000);
      const removal = page.waitForResponse(response => response.url() === BASE + '/api/synthetic/remove', { timeout: 30000 });
      await drafts.getByRole('button', { name: `Remove synthetic item ${drafted.draft.item_id}` }).click();
      await removal;
      const removed = await fictionalState();
      check('fictional: removal empties the separate feed', removed.items.length === 0 && removed.feed.items.length === 0 && same((await serverState()).feed, baseline.feed));
      await shot('fictional-removed');
      record.outcome = 'completed: draft reviewed, admitted to the separate feed, removed; observed feed unchanged';
    },
  };

  try {
    await page.goto(BASE + '/', { waitUntil: 'networkidle' });
    if (await page.locator('#personal-token').count()) {
      const refused = await context.request.get(BASE + '/api/status');
      check('the API refuses a request that has no operator token', refused.status() === 403, { status: refused.status() });
      check('an operator token was supplied to this script', TOKEN.length > 0);
      await page.locator('#personal-token').fill(TOKEN);
      await page.getByRole('button', { name: 'Unlock' }).click();
    }
    await page.locator('.status-strip').waitFor({ state: 'visible', timeout: 30000 });
    const statusResponse = await context.request.get(BASE + '/api/status', { headers: TOKEN ? { 'X-Personal-Operator-Token': TOKEN } : {} });
    receipt.status = await statusResponse.json();
    receipt.source_fingerprint = receipt.status.source_fingerprint || null;
    receipt.status_strip_text = (await page.locator('.status-strip').innerText()).replace(/\s+/g, ' ');
    save();
    check('session established', Boolean(session));
    const provider = receipt.status.provider;
    check('automatic review is used only when no model is connected',
      REVIEW === 'wait' || provider === null || provider.live_model === false,
      { review_mode: REVIEW, provider: provider ? provider.backend : null });
    const tab = page.getByRole('button', { name: 'Language controls', exact: true });
    await page.waitForFunction(() => [...document.querySelectorAll('.view-tabs button')].some(button => button.innerText === 'Language controls' && !button.disabled), null, { timeout: 30000 });
    await tab.click();
    await panel.waitFor({ state: 'visible' });
    await page.waitForFunction(() => !/Loading\.\.\./.test(document.querySelector('section[aria-label="Language controls panel"]').innerText), null, { timeout: 30000 });
    check('the language view names what it is and makes no accuracy claim', /It does not measure accuracy or satisfaction\./.test(await page.locator('[aria-label="About this view"]').innerText()));
    await shot('start');
    await show('start: the status strip names the data and the provider', page.locator('.status-strip'), 4000);
    await show('start: the language controls and their six stages', panel.locator('ol.stage-line'), 4000);
    for (const flow of FLOWS) {
      if (!flows[flow]) throw new Error('Unknown flow ' + flow);
      await flows[flow]();
      receipt.flows_result[flow].finished_utc = utc();
      save();
    }
    check('no script error was raised by the page', pageErrors.length === 0, pageErrors.slice(0, 3));
    const complete = Object.values(receipt.flows_result).every(flow => flow.outcome.startsWith('completed'));
    receipt.outcome = complete ? 'all flows completed' : 'stopped before completion; see flows_result';
    if (!complete) process.exitCode = 2;
  } catch (error) {
    receipt.outcome = 'failed: ' + error.message;
    try { await shot('failure'); } catch (_) { /* page may be gone */ }
    process.exitCode = 1;
  } finally {
    receipt.finished_utc = utc();
    save();
    if (VIDEO) {
      // The recording is complete only after the context is closed.
      const video = page.video();
      try {
        await context.close();
        const target = path.join(OUT, 'video', SCENARIO + '.webm');
        fs.renameSync(await video.path(), target);
        receipt.video.file = 'video/' + SCENARIO + '.webm';
      } catch (error) { receipt.video.error = String(error.message || error); }
      save();
    }
    await browser.close();
    console.log('OUTCOME', receipt.outcome);
    console.log('RECEIPT', path.join(OUT, 'browser-receipt.json'));
  }
})();
