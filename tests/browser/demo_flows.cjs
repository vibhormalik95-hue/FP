#!/usr/bin/env node
/*
 * Drive the served Feed Control Lab through its three controls in a real browser
 * and record what the interface and the server state actually did.
 *
 *   node tests/browser/demo_flows.cjs --base http://127.0.0.1:8765 \
 *        --scenario category --flows manual,category --out runs/browser-01
 *
 * Flows
 *   manual    existing category chosen by hand; no model call
 *   category  natural-language objective -> definition review -> membership and
 *             evidence review of every supplied item -> preview -> apply -> undo
 *   indirect  one indirect request -> action and item proposal -> apply -> undo
 *
 * For each flow the script checks, against the server's own state, that a
 * preview changes nothing, that Apply removes exactly the approved items, and
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
const FLOWS = (args.flows || (SCENARIO === 'category' ? 'manual,category' : 'manual,indirect')).split(',');
const USER = 1;

const SCENARIOS = {
  category: {
    manualCategory: 'K1',
    objective: 'Propose one useful new category from these eight descriptions. Decide the shared concept yourself from the stated facts, rather than taking an existing category code as its meaning. Give a precise definition supported by the descriptions; do not merely rename an existing category or invent missing facts.',
  },
  hunger: {
    manualCategory: 'Repair',
    request: "I'm not hungry, remove all the stuff that makes me hungry.",
    label: 'Reviewed indirect request',
  },
};
const scenario = SCENARIOS[SCENARIO];
if (!scenario) throw new Error('Unknown scenario ' + SCENARIO);
if (!['auto', 'wait'].includes(REVIEW)) throw new Error('--review must be auto or wait');

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
    if (locator) { try { await locator.first().scrollIntoViewIfNeeded({ timeout: 5000 }); } catch (_) { /* region not present */ } }
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
          declared_provider: call.model_provenance || null, observed_utc: utc(),
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
  const shownIds = async () => (await page.locator('.item-card h3').allInnerTexts()).map(text => Number(text.replace('Item ', '')));
  const panel = page.locator('section[aria-label="Reviewed semantic groups"]');
  const status = () => panel.locator('p[role="status"]');
  const reviewHeading = () => page.getByRole('heading', { name: 'Review the meaning and evidence yourself' });
  const reviewBlock = () => panel.locator('div.saved-profile', { has: reviewHeading() });

  // Use the page's own button for the bundled request when it is offered, and
  // confirm that the text in the box is the exact scenario request.
  async function insertRequest(expected) {
    const button = panel.getByRole('button', { name: 'Insert the bundled scenario request' });
    if (await button.count()) await button.click(); else await panel.locator('#semantic-text').fill(expected);
    check('the request text is the exact scenario request', await panel.locator('#semantic-text').inputValue() === expected);
  }

  async function gate(name, region) {
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

  // Wait until the panel shows either the expected region or a status message.
  async function outcome(regions, timeout) {
    const started = Date.now();
    while (Date.now() - started < timeout) {
      for (const [name, locator] of Object.entries(regions)) if (await locator.count() && await locator.first().isVisible()) return name;
      if (await status().count() && (await status().innerText()).trim()) return 'message';
      await page.waitForTimeout(250);
    }
    throw new Error('No result appeared within ' + timeout / 1000 + ' s');
  }

  async function applyAndUndo(flow, baseline, record) {
    const pending = reviewBlock();
    const preview = await serverState();
    check(`${flow}: preview left the applied feed unchanged`, JSON.stringify(preview.feed) === JSON.stringify(baseline.feed) && preview.groups.length === 0 && preview.revision === baseline.revision,
      { applied_groups: preview.groups.length, revision: preview.revision, eligible: preview.feed.available_items });
    check(`${flow}: page still shows the starting items during preview`, JSON.stringify(await shownIds()) === JSON.stringify(record.shown_before), { shown: await shownIds() });
    const reviewText = await pending.innerText();
    const selected = (reviewText.match(/Selected existing IDs: ([0-9, ]+);/) || [])[1];
    record.selected_ids = selected ? selected.split(',').map(value => Number(value.trim())) : [];
    record.review_text_sha256 = require('crypto').createHash('sha256').update(reviewText).digest('hex');
    fs.writeFileSync(path.join(OUT, `${flow}-final-review.txt`), reviewText);
    check(`${flow}: review names the items that would be removed`, record.selected_ids.length > 0, { selected_ids: record.selected_ids });
    const table = page.locator('section[aria-label="Review of every supplied item"]');
    const listed = (await table.locator('tbody tr').evaluateAll(rows => rows.map(row => ({
      id: Number(row.dataset.item), marked: row.classList.contains('review-member'),
      description: row.querySelectorAll('td')[0].innerText.trim(), result: row.querySelector('td:last-child b').innerText.trim() }))));
    const marked = listed.filter(row => row.marked).map(row => row.id).sort();
    const expectedText = Object.fromEntries(baseline.feed.items.map(item => [item.item_id, item.source_text]));
    check(`${flow}: review table lists every supplied item with its own description and marks exactly the approved ones`,
      listed.length === baseline.feed.items.length && new Set(listed.map(row => row.id)).size === listed.length
        && JSON.stringify(marked) === JSON.stringify([...record.selected_ids].sort())
        && listed.every(row => row.description === expectedText[row.id])
        && listed.every(row => row.marked === (row.result !== 'Unchanged'))
        && /NOTHING IS APPLIED YET/.test(await table.innerText()),
      { rows: listed.length, marked });
    fs.writeFileSync(path.join(OUT, `${flow}-review-table.txt`), await table.innerText());
    await show(`${flow}: review table of every supplied item (preview, nothing applied)`, table, 6000);
    await show(`${flow}: the feed is unchanged during the preview`, page.locator('.item-card'), 3000);
    await show(`${flow}: review block with the approve button; waiting for the reviewer`, pending.getByRole('button', { name: 'Approve this exact item set and apply' }), 2000);
    if (!await gate(`${flow}-apply`, pending)) { record.outcome = 'declined before apply; nothing applied'; return; }

    await pending.getByRole('button', { name: 'Approve this exact item set and apply' }).click();
    await page.waitForFunction(() => /Reviewed item set applied/.test(document.body.innerText), null, { timeout: 30000 });
    const applied = await serverState();
    const appliedIds = applied.feed.items.map(item => item.item_id);
    record.eligible_after_apply = applied.feed.available_items;
    check(`${flow}: Apply removed exactly the approved items`,
      applied.feed.available_items === baseline.feed.available_items - record.selected_ids.length
        && record.selected_ids.every(id => !appliedIds.includes(id))
        && baseline.feed.items.map(item => item.item_id).filter(id => !record.selected_ids.includes(id)).every(id => appliedIds.includes(id)),
      { eligible_before: baseline.feed.available_items, eligible_after: applied.feed.available_items, removed: record.selected_ids });
    check(`${flow}: page shows the reduced feed`, JSON.stringify(await shownIds()) === JSON.stringify(appliedIds), { shown: await shownIds() });
    record.shown_after_apply = await shownIds();
    await shot(`${flow}-applied`);
    await show(`${flow}: applied; the feed shows the reduced item set`, page.locator('h2', { hasText: 'Your reviewed topic feed' }), 5000);

    // Undo is two explicit steps: ask for the undo review, then approve it.
    await panel.getByRole('button', { name: 'Review semantic undo' }).click();
    await pending.waitFor({ state: 'visible', timeout: 30000 });
    const undoPreview = await serverState();
    check(`${flow}: undo review alone changed nothing`, JSON.stringify(undoPreview.feed) === JSON.stringify(applied.feed) && undoPreview.groups.length === applied.groups.length,
      { eligible: undoPreview.feed.available_items });
    await show(`${flow}: undo review (step 1 of 2); nothing changed yet`, pending.getByRole('button', { name: 'Approve this exact item set and apply' }), 3000);
    if (!await gate(`${flow}-undo`, pending)) { record.outcome = 'undo declined; control still applied'; return; }
    await pending.getByRole('button', { name: 'Approve this exact item set and apply' }).click();
    await page.waitForFunction(count => document.querySelectorAll('.item-card').length === count, baseline.feed.items.length, { timeout: 30000 });
    const restored = await serverState();
    record.eligible_after_undo = restored.feed.available_items;
    check(`${flow}: Undo restored the exact starting feed`, JSON.stringify(restored.feed) === JSON.stringify(baseline.feed) && restored.groups.length === 0,
      { eligible: restored.feed.available_items, identical_to_start: JSON.stringify(restored.feed) === JSON.stringify(baseline.feed), revision: restored.revision });
    check(`${flow}: page shows the starting items again`, JSON.stringify(await shownIds()) === JSON.stringify(record.shown_before), { shown: await shownIds() });
    await shot(`${flow}-restored`);
    await show(`${flow}: undo approved (step 2 of 2); the starting feed is restored`, page.locator('h2', { hasText: 'Your reviewed topic feed' }), 5000);
    record.outcome = 'completed: preview unchanged, apply exact, undo restored';
  }

  async function startFlow(flow) {
    const baseline = await serverState();
    const record = { started_utc: utc(), eligible_before: baseline.feed.available_items, shown_before: await shownIds(), outcome: 'started' };
    receipt.flows_result[flow] = record;
    check(`${flow}: starts with no applied semantic group`, baseline.groups.length === 0, { eligible: baseline.feed.available_items });
    return { baseline, record };
  }

  const flows = {
    async manual() {
      const { baseline, record } = await startFlow('manual');
      await panel.locator('#semantic-backend').selectOption('manual_category');
      await panel.locator('#semantic-label').fill('Manual ' + scenario.manualCategory);
      await panel.locator('#semantic-category').fill(scenario.manualCategory);
      await panel.locator('#semantic-operation').selectOption('exclude');
      const callsBefore = receipt.provider_calls.length;
      await show('manual: existing category and action chosen by hand', panel.locator('#semantic-category'), 2500);
      await panel.getByRole('button', { name: 'Review semantic proposal' }).click();
      check('manual: review appears', await outcome({ review: reviewHeading() }, 30000) === 'review');
      check('manual: the server reported no model call for this review', receipt.provider_calls.length === callsBefore, { model_calls: receipt.provider_calls.length - callsBefore });
      await shot('manual-review');
      await applyAndUndo('manual', baseline, record);
      record.provider_calls = 0;
    },

    async category() {
      const { baseline, record } = await startFlow('category');
      await panel.locator('#semantic-backend').selectOption('staged');
      await insertRequest(scenario.objective);
      await panel.locator('#semantic-operation').selectOption('exclude');
      await shot('category-objective');
      await show('category: natural-language objective entered', panel.locator('#semantic-text'), 4000);
      await panel.getByRole('button', { name: 'Propose a definition for review' }).click();
      await show('category: waiting for the model (definition)', null, 1000);
      const definition = panel.locator('[aria-label="Category definition review"]');
      const resolution = panel.locator('[aria-label="Unresolved semantic interpretations"]');
      let result = await outcome({ definition, resolution }, STAGE_TIMEOUT);
      if (result === 'resolution') {
        // The model returned a primary definition with competing meanings.
        record.competing_meanings_shown = true;
        fs.writeFileSync(path.join(OUT, 'category-resolution.txt'), await resolution.innerText());
        await show('category: the model returned competing meanings; waiting for the reviewer', resolution, 6000);
        if (!await gate('category-resolution', resolution)) { record.outcome = 'declined at competing meanings; nothing applied'; return; }
        await resolution.getByRole('radio').check();
        await resolution.getByRole('button', { name: 'Continue to definition review' }).click();
        result = await outcome({ definition }, 30000);
      }
      if (result !== 'definition') { record.outcome = 'no definition to review: ' + (await status().innerText()); await shot('category-stopped'); return; }
      const definitionText = await definition.innerText();
      fs.writeFileSync(path.join(OUT, 'category-definition-review.txt'), definitionText);
      record.definition_label = (await definition.locator('strong').first().innerText()).trim();
      const afterDefinition = await serverState();
      check('category: definition proposal changed nothing', JSON.stringify(afterDefinition.feed) === JSON.stringify(baseline.feed) && afterDefinition.groups.length === 0, { label: record.definition_label });
      await show('category: definition review (label and definition); waiting for the reviewer', definition.locator('strong'), 8000);
      await show('category: definition review (approve box and button)', definition.getByRole('checkbox'), 3000);
      if (!await gate('category-definition', definition)) { record.outcome = 'definition declined by the reviewer; nothing classified or applied'; return; }
      await definition.getByRole('checkbox').check();
      await definition.getByRole('button', { name: 'Approve definition and classify supplied items' }).click();
      await show('category: definition approved; waiting for the model (classification, then separate evidence assessment)', null, 1000);
      result = await outcome({ review: reviewHeading() }, STAGE_TIMEOUT);
      if (result !== 'review') { record.outcome = 'no membership to review: ' + (await status().innerText()); await shot('category-stopped'); return; }
      const reviewText = await reviewBlock().innerText();
      const dispositions = [...reviewText.matchAll(/Item (\d+): (match|not_match|unknown);/g)].map(match => ({ item_id: Number(match[1]), verdict: match[2] }));
      const assessments = [...reviewText.matchAll(/Item (\d+) evidence assessment: (supported|contradicted|not_stated|ambiguous);/g)].map(match => ({ item_id: Number(match[1]), assessment: match[2] }));
      record.dispositions = dispositions;
      record.evidence_assessments = assessments;
      check('category: every supplied item has one membership decision on screen', dispositions.length === baseline.feed.items.length && new Set(dispositions.map(row => row.item_id)).size === baseline.feed.items.length, { shown: dispositions.length, supplied: baseline.feed.items.length });
      check('category: every supplied item has one evidence assessment on screen', assessments.length === baseline.feed.items.length, { shown: assessments.length });
      await shot('category-membership-review');
      await applyAndUndo('category', baseline, record);
      record.provider_calls = receipt.provider_calls.filter(call => call.route.includes('/definition/')).length;
    },

    async indirect() {
      const { baseline, record } = await startFlow('indirect');
      await panel.locator('#semantic-backend').selectOption('configured_model');
      await panel.locator('#semantic-label').fill(scenario.label);
      await insertRequest(scenario.request);
      await shot('indirect-request');
      await show('indirect: request entered; it names no category', panel.locator('#semantic-text'), 4000);
      await panel.getByRole('button', { name: 'Review semantic proposal' }).click();
      await show('indirect: waiting for the model (action, then items)', null, 1000);
      const result = await outcome({ review: reviewHeading() }, STAGE_TIMEOUT);
      if (result !== 'review') { record.outcome = 'no proposal to review: ' + (await status().innerText()); await shot('indirect-stopped'); return; }
      const reviewText = await reviewBlock().innerText();
      record.interpreted_action = (reviewText.match(/: (exclude|boost|reduce) \((none|light|standard|strong)\)/) || []).slice(1, 3).join('/');
      check('indirect: original request is shown unchanged', reviewText.includes(scenario.request));
      await shot('indirect-review');
      await applyAndUndo('indirect', baseline, record);
      record.provider_calls = receipt.provider_calls.filter(call => call.route.endsWith('/api/semantic/preview')).length;
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
    await page.getByRole('button', { name: 'Reviewed topic feed' }).click();
    await page.locator('summary', { hasText: 'Experimental semantic groups' }).click();
    await panel.waitFor({ state: 'visible' });
    await page.waitForFunction(() => !/Loading\.\.\./.test(document.querySelector('section[aria-label="Reviewed semantic groups"]').innerText), null, { timeout: 30000 });
    await shot('start');
    await show('start: the status strip names the data and the provider', page.locator('.status-strip'), 4000);
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
