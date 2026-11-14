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
 *   history      two manual controls; Undo returns to the state with the first
 *                one; "Remove every applied control" and its undo
 *   failure      a request that gets no usable reply (a typed request with the
 *                hand-written replies, or a provider that fails): the page names
 *                the failed call, never "no call", and nothing changes
 *   expired      the page clock passes five minutes; then the server refuses a
 *                review that a newer request replaced
 *   reject       a new category: the definition under review is rejected and the
 *                server no longer accepts it
 *   original     the original conditions A to E: on category IDs of the form
 *                category_N the instruction and the profile work; on named
 *                categories both are disabled with the reason
 *
 * For each flow the script checks, against the server's own state, that a
 * preview changes nothing (also the conditions A to E, the topic tool and the
 * fictional items), that the preview feed and the applied feed have the order
 * that the approved controls give, that Apply has exactly the approved effect,
 * and that the two-step Undo restores the exact earlier state.
 *
 * Review gates. With --review auto the script ticks the review boxes itself;
 * use that only with the scripted provider. With --review wait it stops at each
 * gate, writes gate-<name>.json and a screenshot into --out, and continues only
 * when decision-<name>.txt contains APPROVE. Anything else is recorded as a
 * decline and the flow stops with nothing applied.
 *
 * The receipt lists the script's own checks under "checks", the reviewer's
 * decisions under "review_decisions", every provider call with a reply under
 * "provider_calls", and the number of calls that the server says it began
 * (also failed ones) under "calls_attempted". A provider call is a model call only when the declared
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
  category: { manualCategory: 'K1', flows: 'manual,category,reject,history,failure,expired,original' },
  hunger: { manualCategory: 'Repair', flows: 'manual,indirect,history,failure,expired,original' },
  tags: { manualCategory: 'Cooking', flows: 'manual,vocabulary,mixed,outcomes,description,fictional,history,failure,expired,original' },
  // The built-in fixture: category IDs of the form category_N, no item descriptions, no provider.
  conditions: { manualCategory: null, flows: 'original' },
};
// A typed request that no bundled scenario holds. With the hand-written replies the server has no reply for it.
const TYPED_REQUEST = 'Hide everything about trains.';
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
  source_fingerprint: null, status: null, checks: [], review_decisions: [], flows_result: {}, provider_calls: [], calls_attempted: [], provider_attempts: [], screenshots: [], finished_utc: null, outcome: 'started',
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
  const browser = await chromium.launch(args['browser-executable'] ? {executablePath: args['browser-executable']} : {});
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
  let session = null, lastFocus = null;
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('response', async response => {
    const url = response.url();
    if (!url.startsWith(BASE + '/api/')) return;
    let body = null;
    try { body = await response.json(); } catch (_) { return; }
    if (url.endsWith('/api/session') && body && body.session_id) session = body.session_id;
    // The server counts each call that it began, also a call that failed before a reply came back.
    if (body && typeof body.calls_attempted === 'number') receipt.calls_attempted.push({ route: url.slice(BASE.length), calls_attempted: body.calls_attempted,
      outcome_source: body.outcome_source || null, ready: body.ready === true || body.definition_ready === true, observed_utc: utc() });
    // Each attempt of a call with its status, as the server lists it (also an attempt without a reply).
    if (Array.isArray(body?.call_attempts)) receipt.provider_attempts.push({ route: url.slice(BASE.length), attempts: body.call_attempts,
      outcome_source: body.outcome_source || null, observed_utc: utc() });
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
  const getJson = async route => {
    const response = await context.request.get(`${BASE}/api/${route}`, { headers: headers() });
    assert.strictEqual(response.status(), 200, `${route} read failed`);
    return response.json();
  };
  // The parts of the server state that a language control must never change: the conditions A to E,
  // the earlier topic tool and the fictional items.
  const otherState = async () => {
    const [compare, steering, fictional] = await Promise.all([getJson(`compare?user_id=${USER}`), getJson(`steering?user_id=${USER}`), getJson(`synthetic/items?user_id=${USER}`)]);
    return { compare, steering: { commands: steering.commands, text: steering.text, feed: steering.feed }, fictional: fictional.items.map(item => item.item_id) };
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
    // Where the focus is right after the result, before the script scrolls or takes a screenshot.
    try { await page.waitForFunction(() => document.activeElement && document.activeElement.id === 'review-heading', null, { timeout: 3000 }); } catch (_) { /* recorded below */ }
    lastFocus = await focusState();
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
    // The file can exist before its text is complete, and another program can still hold it. The text
    // counts when two reads, 300 ms apart, give the same text. An empty or unreadable file counts as an
    // empty decision only after five seconds.
    const read = () => { try { return fs.readFileSync(decision, 'utf8'); } catch (error) { return null; } };
    let written = read();
    for (const settle = Date.now(); ;) {
      await page.waitForTimeout(300);
      const again = read();
      if (again === written && ((written || '').trim() || Date.now() - settle > 5000)) break;
      written = again;
    }
    const answer = (written || '').trim();
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
    const scores = Object.fromEntries(kept.map(item => [item.item_id, item.base_score + (delta[item.item_id] || 0)]));
    // The server orders by the adjusted score, then by the item ID.
    const order = kept.map(item => item.item_id).sort((a, b) => Math.abs(scores[a] - scores[b]) > 1e-9 ? scores[b] - scores[a] : a - b);
    // With more eligible items than the first ten, other items can enter the list; then only the relative order of the listed ones is compared.
    return { removed: [...removed].sort((a, b) => a - b), kept: kept.map(item => item.item_id).sort((a, b) => a - b), delta,
      complete: baseline.feed.available_items === baseline.feed.items.length, scores, order };
  }
  // Is `shown` (a list of item IDs) in the order that `expected` gives?
  function inOrder(shown, expected) {
    if (expected.complete) return same(shown, expected.order.slice(0, shown.length)) && shown.length === Math.min(10, expected.order.length);
    const listed = expected.order.filter(id => shown.includes(id));
    return same(shown.filter(id => listed.includes(id)), listed);
  }

  // The members of a category-and-tag control, computed from the term list of the server: every item that carries a chosen term.
  async function vocabularyMembers(flow, review, baseline) {
    const listed = await (await context.request.post(`${BASE}/api/semantic/vocabulary/terms`, { headers: headers(), data: { user_id: USER, candidate_ids: review.groups[0].scope_ids } })).json();
    for (const control of review.vocabulary.controls) {
      const group = review.groups.find(candidate => candidate.label === control.label);
      const expected = [...new Set(control.terms.flatMap(term => (listed.terms.find(known => known.term_id === term.term_id) || { item_ids: [] }).item_ids))].sort((a, b) => a - b);
      check(`${flow}: the items of "${control.label}" are exactly the items that carry its chosen names in the term list of the server`,
        Boolean(group) && same([...group.proposal.item_ids].sort((a, b) => a - b), expected), { expected, sealed: group ? group.proposal.item_ids : null });
    }
  }

  // Approve a reviewed plan and check the result against `expectedState` (a server state) or the expected feed.
  async function approveAndRead(flow, name, kind) {
    await submit(() => approve(name).click(), '/api/semantic/apply', 30000);
    await page.waitForFunction(kind => { const node = document.querySelector('section[aria-label="Review board"] [aria-label="What changed"]'); return node && node.dataset.kind === kind; }, kind, { timeout: 30000 });
    return serverState();
  }

  async function applyAndUndo(flow, baseline, record, review, others) {
    const controls = newControls(review, baseline);
    record.controls = controls;
    record.selected_ids = [...new Set(controls.flatMap(control => control.item_ids))].sort((a, b) => a - b);
    // The script does not scroll here: the page itself must bring the result into view and move the focus to it.
    check(`${flow}: the page moves the focus to the heading of the review and shows it in the window`, Boolean(lastFocus && lastFocus.heading && lastFocus.in_view), lastFocus);
    const preview = await serverState();
    check(`${flow}: the preview left the applied groups, the revision and the applied feed unchanged`, same(preview.feed, baseline.feed) && same(preview.groups, baseline.groups) && preview.revision === baseline.revision,
      { applied_groups: preview.groups.length, revision: preview.revision, eligible: preview.feed.available_items });
    check(`${flow}: the preview left the conditions A to E, the topic tool and the fictional items unchanged`, same(await otherState(), others));
    check(`${flow}: page still shows the starting items during preview`, same(await shownIds(), record.shown_before), { shown: await shownIds() });
    check(`${flow}: the review names at least one item that would change`, record.selected_ids.length > 0, { controls });

    const boardText = await board.innerText();
    record.review_text_sha256 = crypto.createHash('sha256').update(boardText).digest('hex');
    fs.writeFileSync(path.join(OUT, `${flow}-final-review.txt`), boardText);
    const present = {};
    const blocks = blocksOf(flow === 'manual' || flow === 'history' ? 'Your selection' : replyBlock());
    for (const title of blocks) present[title] = await board.locator(`section[aria-label="${title}"]`).count();
    check(`${flow}: the review has three separate blocks (${blocks[0]}, application checks, decision) and says that nothing is applied`,
      blocks.every(title => present[title] === 1) && /NOTHING IS APPLIED YET/.test(boardText) && /Nothing has changed yet\./.test(boardText), present);
    const failedLines = await board.locator('[data-passed="false"]').allInnerTexts();
    check(`${flow}: no check line of the review is shown as failed`, failedLines.length === 0, { failed: failedLines.slice(0, 3) });
    const decisionText = await board.locator('section[aria-label="Your decision"]').innerText();
    for (const control of controls) check(`${flow}: the decision block names the control "${control.label}" and each of its items`,
      decisionText.includes(control.label) && control.item_ids.every(id => decisionText.includes(String(id))), { items: control.item_ids });

    const groups = await tableGroups();
    const expectedText = Object.fromEntries(baseline.feed.items.map(item => [item.item_id, item.source_text]));
    for (const control of controls) {
      const body = groups.find(group => group.label === control.label);
      const marked = body ? body.rows.filter(row => row.marked).map(row => row.id).sort((a, b) => a - b) : null;
      check(`${flow}: the evidence table lists every supplied item once for "${control.label}", with its own description, and marks exactly the approved ones`,
        Boolean(body) && body.fresh && body.rows.length === baseline.feed.items.length && new Set(body.rows.map(row => row.id)).size === body.rows.length
          && same(marked, control.item_ids) && body.rows.every(row => row.marked === row.member)
          && body.rows.every(row => row.description === (expectedText[row.id] || 'No description in the item data'))
          && body.rows.every(row => row.member ? /^(selected|match)/.test(row.evidence) : !/^selected/.test(row.evidence)),
        { rows: body ? body.rows.length : 0, marked });
    }
    // Each quotation of a description control must be a part of the text of its own item, as the server holds it.
    for (const group of review.groups.filter(candidate => controls.some(control => control.label === candidate.label))) {
      const quoted = (group.proposal.evidence || []).filter(row => !['first_level_category_name', 'second_level_category_name', 'third_level_category_name', 'topic_tag'].includes(row.field));
      if (!quoted.length || group.proposal.induction) continue;
      check(`${flow}: each quotation of "${group.label}" is a part of the text of its own item on the server`,
        quoted.every(row => typeof expectedText[row.item_id] === 'string' && expectedText[row.item_id].includes(row.quote)), { quotations: quoted.length });
    }
    // A control of the category and tag method holds exactly the items of its chosen terms.
    if (review.vocabulary) for (const selected of review.vocabulary.controls) {
      const expectedIds = [...new Set(selected.terms.flatMap(term => term.item_ids))].sort((a,b)=>a-b);
      const approved = controls.find(control => control.label === selected.label);
      check(`${flow}: membership equals the union of chosen term members`, Boolean(approved) && same(approved.item_ids, expectedIds), {label:selected.label, expectedIds, actual:approved?.item_ids});
    }
    const expected = expectedFeed(baseline, controls);
    if (expected.complete) {
      const expectedOrder = Object.keys(expected.scores).map(Number).sort((a,b)=>expected.scores[b]-expected.scores[a] || a-b);
      check(`${flow}: preview order and eligible count match independently calculated effects`, same(review.feed.items.map(item=>item.item_id), expectedOrder) && review.feed.available_items === expected.kept.length);
      if (flow === 'mixed') {
        const beforeOrder=baseline.feed.items.map(item=>item.item_id);
        check('mixed: at least one boosted item moves higher', controls.filter(c=>c.operation==='boost').flatMap(c=>c.item_ids).some(id=>expectedOrder.indexOf(id)>=0 && expectedOrder.indexOf(id)<beforeOrder.indexOf(id)));
      }
    }
    const resultOf = id => { const row = groups.flatMap(group => group.rows).find(candidate => candidate.id === id); return row ? row.result : null; };
    check(`${flow}: the table states the result for each item that the approved controls remove`,
      expected.removed.every(id => resultOf(id) === 'Removed from the feed'), { removed: expected.removed });
    // "Ranked higher" and "ranked lower" only for an item whose position changes.
    const previewIds = review.feed.items.map(item => item.item_id);
    const words = groups.filter(group => group.fresh).flatMap(group => group.rows).filter(row => /ranked (higher|lower)/.test(row.result));
    check(`${flow}: the table says "ranked higher" or "ranked lower" only for an item that moves in the preview feed`,
      words.every(row => baseline.feed.items.findIndex(item => item.item_id === row.id) !== previewIds.indexOf(row.id)), { moved: words.map(row => row.id) });
    fs.writeFileSync(path.join(OUT, `${flow}-review-table.txt`), await page.locator('section[aria-label="Review of every supplied item"]').innerText());
    check(`${flow}: the preview feed of the server has the order that the approved controls give`, inOrder(previewIds, expected), { preview: previewIds, expected: expected.order.slice(0, 10) });
    const before = page.locator('section[aria-label="Preview of the feed before and after"]');
    const afterList = await before.locator('[aria-label="First ten items after approval"] li').evaluateAll(rows => rows.map(row => Number(row.dataset.item)));
    check(`${flow}: the preview lists the feed now and after approval, as the server computed them, and says that the applied feed is unchanged`,
      /The applied feed is unchanged until you approve\./.test(await before.innerText())
        && same(await before.locator('[aria-label="First ten items now"] li').evaluateAll(rows => rows.map(row => Number(row.dataset.item))), baseline.feed.items.map(item => item.item_id))
        && same(afterList, previewIds), { after: afterList });
    await show(`${flow}: three review blocks (reply, application checks, your decision); nothing applied`, board, 6000);
    await show(`${flow}: evidence table of every supplied item`, page.locator('section[aria-label="Review of every supplied item"]'), 6000);
    await show(`${flow}: the feed now and after approval`, before, 4000);
    await show(`${flow}: the feed is unchanged during the preview`, page.locator('.item-card'), 3000);
    await show(`${flow}: the decision block with the approve button; waiting for the reviewer`, approve(), 2000);
    if (!await gate(`${flow}-apply`, board)) { record.outcome = 'declined before apply; nothing applied'; return; }

    const applied = await approveAndRead(flow, 'Approve this exact item set and apply', 'apply');
    const appliedIds = applied.feed.items.map(item => item.item_id);
    record.eligible_after_apply = applied.feed.available_items;
    check(`${flow}: after Apply the focus is on the heading "What changed", in the window`, await headingInView('What changed'));
    check(`${flow}: Apply removed exactly the items of the approved removal controls`,
      applied.feed.available_items === baseline.feed.available_items - expected.removed.length
        && expected.removed.every(id => !appliedIds.includes(id)) && (!expected.complete || same([...appliedIds].sort((a, b) => a - b), expected.kept)),
      { eligible_before: baseline.feed.available_items, eligible_after: applied.feed.available_items, removed: expected.removed });
    check(`${flow}: Apply changed the score of exactly the items of the approved rank controls, by the stated amount`,
      applied.feed.items.every(item => Math.abs(item.score - item.base_score - (expected.delta[item.item_id] || 0)) < 1e-9),
      { changed: applied.feed.items.filter(item => Math.abs(item.score - item.base_score) > 1e-9).map(item => ({ id: item.item_id, by: Number((item.score - item.base_score).toFixed(2)) })) });
    check(`${flow}: the applied feed has the order that the approved controls give, and it is the preview feed`, inOrder(appliedIds, expected) && same(appliedIds, previewIds), { applied: appliedIds });
    check(`${flow}: exactly the approved controls are applied, with exactly their items`,
      same(applied.groups.map(group => [group.label, [...group.proposal.item_ids].sort((a, b) => a - b)]).sort(), controls.map(control => [control.label, control.item_ids]).sort())
        && applied.revision !== baseline.revision, { applied: applied.groups.map(group => group.label), revision: applied.revision });
    check(`${flow}: Apply left the conditions A to E, the topic tool and the fictional items unchanged`, same(await otherState(), others));
    check(`${flow}: page shows the feed that the server holds`, same(await shownIds(), appliedIds), { shown: await shownIds() });
    const changed = await board.locator('[aria-label="What changed"]').innerText();
    check(`${flow}: the page records what changed and how to undo it`, controls.every(control => changed.includes(control.label)) && /To undo:/.test(changed));
    const listedControls = await panel.locator('ul.applied-controls li').allInnerTexts();
    check(`${flow}: the list of applied controls in the panel is the list of the server`, listedControls.length === applied.groups.length
      && applied.groups.every(group => listedControls.some(line => line.startsWith(group.label + ':'))), { listed: listedControls });
    record.shown_after_apply = await shownIds();
    await shot(`${flow}-applied`);
    await show(`${flow}: applied; the page records what changed`, board, 4000);
    await show(`${flow}: the feed shows the applied result`, page.locator('h2', { hasText: 'The feed with your applied controls' }), 4000);

    // Undo is two explicit steps: ask for the undo review, then approve it.
    await submit(() => panel.getByRole('button', { name: 'Undo the last change (review first)' }).click(), '/api/semantic/history/preview', 30000);
    await page.waitForFunction(() => document.querySelector('section[aria-label="Review board"]')?.dataset.variant === 'review', null, { timeout: 30000 });
    const undoPreview = await serverState();
    check(`${flow}: undo review alone changed nothing`, same(undoPreview, applied), { eligible: undoPreview.feed.available_items });
    await show(`${flow}: undo review (step 1 of 2); nothing changed yet`, approve('Approve the undo'), 3000);
    if (!await gate(`${flow}-undo`, board)) { record.outcome = 'undo declined; control still applied'; return; }
    const restored = await approveAndRead(flow, 'Approve the undo', 'undo');
    record.eligible_after_undo = restored.feed.available_items;
    check(`${flow}: Undo restored the exact earlier feed and the exact earlier controls`, same(restored.feed, baseline.feed) && same(restored.groups, baseline.groups),
      { eligible: restored.feed.available_items, identical_to_start: same(restored.feed, baseline.feed), revision: restored.revision });
    check(`${flow}: Undo left the conditions A to E, the topic tool and the fictional items unchanged`, same(await otherState(), others));
    check(`${flow}: page shows the starting items again and says that the earlier feed is restored`,
      same(await shownIds(), record.shown_before) && /The earlier feed is restored/.test(await board.innerText()), { shown: await shownIds() });
    await shot(`${flow}-restored`);
    await show(`${flow}: undo approved (step 2 of 2); the starting feed is restored`, board, 4000);
    record.outcome = 'completed: preview unchanged, apply exact, undo restored';
  }

  // The focused element: is it the heading of the review board, inside the window?
  const focusState = () => page.evaluate(() => {
    const node = document.activeElement, box = node.getBoundingClientRect();
    return { heading: node.id === 'review-heading', text: (node.innerText || '').trim().slice(0, 120), in_view: box.top >= 0 && box.bottom <= window.innerHeight };
  });
  const headingInView = async text => { const state = await focusState(); return state.heading && state.in_view && (!text || state.text === text); };
  // Open the view "Language controls" when another view is shown.
  async function ensureLanguage() {
    const tab = page.getByRole('button', { name: 'Language controls', exact: true });
    if (await tab.getAttribute('aria-pressed') !== 'true') await tab.click();
    await panel.waitFor({ state: 'visible' });
    await page.waitForFunction(() => !/Loading\.\.\./.test(document.querySelector('section[aria-label="Language controls panel"]').innerText), null, { timeout: 30000 });
  }

  async function startFlow(flow) {
    await ensureLanguage();
    const baseline = await serverState();
    const others = await otherState();
    const record = { started_utc: utc(), eligible_before: baseline.feed.available_items, shown_before: await shownIds(), outcome: 'started' };
    receipt.flows_result[flow] = record;
    check(`${flow}: starts with no applied control`, baseline.groups.length === 0, { eligible: baseline.feed.available_items });
    return { baseline, record, others };
  }

  // A result that is not a review: record what the page and the server say, and stop the flow.
  async function stopped(flow, record, answer) {
    record.outcome = `no proposal to review: ${answer.body && answer.body.status ? answer.body.status : 'HTTP ' + answer.http}: ${((answer.body && (answer.body.reason || answer.body.detail)) || (await status().innerText()) || '').slice(0, 300)}`;
    await shot(`${flow}-stopped`);
  }

  // The description route: call 1 reads the action, call 2 selects items with quotations.
  async function describedFlow(flow) {
    const { baseline, record, others } = await startFlow(flow);
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
    await applyAndUndo(flow, baseline, record, answer.body, others);
  }

  const flows = {
    async manual() {
      const { baseline, record, others } = await startFlow('manual');
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
      await applyAndUndo('manual', baseline, record, answer.body, others);
      record.provider_calls = 0;
    },

    async category() {
      const { baseline, record, others } = await startFlow('category');
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
      answer = await submit(() => definition.getByRole('button', { name: 'Approve the definition and classify the items of the scope' }).click(), '/api/semantic/definition/classify', STAGE_TIMEOUT);
      record.provider_calls += callsIn(answer.body);
      if (!answer.body || answer.body.ready !== true) return stopped('category', record, answer);
      const [body] = (await tableGroups()).filter(group => group.fresh);
      record.dispositions = body.rows.map(row => ({ item_id: row.id, verdict: row.verdict }));
      record.evidence_assessments = body.rows.map(row => ({ item_id: row.id, assessment: row.assessment }));
      check('category: every supplied item has one membership decision on screen', body.rows.length === baseline.feed.items.length
        && body.rows.every(row => ['match', 'not_match', 'unknown'].includes(row.verdict)), { shown: body.rows.length, supplied: baseline.feed.items.length });
      check('category: every supplied item has one evidence assessment on screen', body.rows.every(row => ['supported', 'contradicted', 'not_stated', 'ambiguous'].includes(row.assessment)), { shown: body.rows.filter(row => row.assessment).length });
      await shot('category-membership-review');
      await applyAndUndo('category', baseline, record, answer.body, others);
    },

    indirect: () => describedFlow('indirect'),
    description: () => describedFlow('description'),

    async vocabulary() {
      const { baseline, record, others } = await startFlow('vocabulary');
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
      await vocabularyMembers('vocabulary', answer.body, baseline);
      record.chosen_terms = vocabulary.controls.map(control => ({ control: control.label, terms: control.terms.map(term => `${term.kind}:${term.value}`) }));
      record.server_checks = vocabulary.checks.map(item => ({ check: item.check, passed: item.passed }));
      const checksText = await board.locator('section[aria-label="Application checks"]').innerText();
      check('vocabulary: every check that the server made is shown as passed in the application checks block',
        vocabulary.checks.length > 0 && vocabulary.checks.every(item => item.passed === true && checksText.includes(item.check))
          && await board.locator('section[aria-label="Application checks"] li[data-passed="false"]').count() === 0, { checks: vocabulary.checks.length });
      const output = await board.locator(`section[aria-label="${replyBlock()}"]`).innerText();
      check('vocabulary: the reply block shows the span of the request and each chosen name',
        vocabulary.controls.every(control => output.includes(control.intent_span) && control.terms.every(term => output.includes(`"${term.value}"`))), record.chosen_terms);
      // The reason of the whole reply (vocab F13): the server sends it as reply_reason.
      check('vocabulary: the server sends the reason of the whole reply, and the page shows it in the reply block and not under the application checks',
        typeof answer.body.reply_reason === 'string' && output.includes(answer.body.reply_reason.trim()) && !checksText.includes(answer.body.reply_reason.trim()));
      check('vocabulary: the chosen names are categories or tags, and the request text is not changed',
        vocabulary.controls.every(control => control.terms.every(term => ['category', 'tag'].includes(term.kind) && terms.terms.some(known => known.term_id === term.term_id && known.value === term.value)))
          && answer.body.groups.every(group => group.request === request));
      const rows = (await tableGroups()).flatMap(group => group.rows);
      check('vocabulary: an item that no chosen name selects is listed with its own categories and tags and the reason',
        vocabulary.not_selected.every(entry => { const row = rows.find(candidate => candidate.id === entry.item_id); return row && !row.member && /^not selected:/.test(row.evidence) && entry.terms.every(term => row.labels.includes(term.value)); }),
        { not_selected: vocabulary.not_selected.map(entry => entry.item_id) });
      await shot('vocabulary-review');
      await applyAndUndo('vocabulary', baseline, record, answer.body, others);
    },

    async mixed() {
      const { baseline, record, others } = await startFlow('mixed');
      await chooseMethod('vocabulary');
      await insertRequest('vocabulary:mixed');
      await shot('mixed-request');
      await show('mixed: one request with two preferences', panel.locator('#semantic-text'), 4000);
      const answer = await submit(() => panel.getByRole('button', { name: 'Interpret my request' }).click(), '/api/semantic/vocabulary/preview', STAGE_TIMEOUT);
      record.provider_calls = callsIn(answer.body);
      if (!answer.body || answer.body.ready !== true) return stopped('mixed', record, answer);
      const controls = newControls(answer.body, baseline);
      check('mixed: the bundled request produces both distinct controls', controls.length === 2 && controls.some(c => c.operation === 'boost') && controls.some(c => c.operation === 'exclude'));
      record.controls_in_one_review = controls.length;
      record.authored_expectation = 'two controls in one review';
      record.matches_authored_expectation = controls.length === 2;
      await vocabularyMembers('mixed', answer.body, baseline);
      // Each kind of control of the bundled request must have a visible effect: a rank control moves at least one item.
      const previewIds = answer.body.feed.items.map(item => item.item_id), startIds = baseline.feed.items.map(item => item.item_id);
      for (const control of controls.filter(candidate => candidate.operation !== 'exclude'))
        check(`mixed: the rank control "${control.label}" moves at least one of its items in the preview feed`,
          control.item_ids.some(id => previewIds.indexOf(id) !== startIds.indexOf(id)), { items: control.item_ids, before: startIds, after: previewIds });
      const fresh = (await tableGroups()).filter(group => group.fresh);
      check('mixed: the review shows one row group for each control of the request', fresh.length === controls.length && same(fresh.map(group => group.label), controls.map(control => control.label)), { controls: controls.map(control => `${control.label}: ${control.operation}`) });
      if (controls.length > 1) check('mixed: the decision block says that one approval applies all controls together',
        (await board.locator('section[aria-label="Your decision"]').innerText()).includes(`One approval applies all ${controls.length} new controls together.`));
      await shot('mixed-review');
      await applyAndUndo('mixed', baseline, record, answer.body, others);
    },

    async outcomes() {
      const { baseline, record, others } = await startFlow('outcomes');
      await chooseMethod('vocabulary');
      record.cases = [];
      for (const [name, expected] of Object.entries(OUTCOME_CASES)) {
        const key = 'vocabulary:' + name;
        if (!receipt.status.scenario_requests || typeof receipt.status.scenario_requests[key] !== 'string') { record.cases.push({ case: name, skipped: 'the server supplies no such bundled request' }); continue; }
        const request = await insertRequest(key);
        const answer = await submit(() => panel.getByRole('button', { name: 'Interpret my request' }).click(), '/api/semantic/vocabulary/preview', STAGE_TIMEOUT);
        const body = answer.body || {};
        const observed = body.ready === true ? 'ready' : body.status || 'HTTP ' + answer.http;
        if (receipt.status.provider?.live_model === false) check(`outcomes: authored ${name} has its exact expected status`, observed === expected, {observed, expected});
        // A model can answer in another class than the authored reply. That is recorded, not failed.
        const entry = { case: name, request, authored_expectation: expected, observed, matches_authored_expectation: observed === expected,
          model_calls_reported: Array.isArray(body.model_calls) ? body.model_calls.length : null, reason: typeof body.reason === 'string' ? body.reason.slice(0, 300) : null };
        record.cases.push(entry);
        save();
        entry.calls_attempted = typeof body.calls_attempted === 'number' ? body.calls_attempted : null;
        entry.outcome_source = body.outcome_source || null;
        // With the hand-written replies the class is known: a different class is a defect, not a model choice.
        if (authored()) check(`outcomes: ${name}: the server answers with the class of the authored reply (${expected})`, observed === expected, { observed });
        if (name === 'negated') check('outcomes: the negated command is stopped by an application check before any call, and the failed check is listed',
          body.ready !== true && body.status === 'clarify' && body.outcome_source === 'application_check' && body.calls_attempted === 0
            && ((body.vocabulary && body.vocabulary.checks) || []).some(item => item.passed === false), { observed, outcome_source: entry.outcome_source, calls_attempted: entry.calls_attempted });
        else if (body.ready !== true && answer.http === 200) check(`outcomes: ${name}: the server names the source of the result, and a call was begun`,
          ['model_report', 'reply_rejected', 'provider_failure'].includes(body.outcome_source) && body.calls_attempted >= 1, { outcome_source: entry.outcome_source, calls_attempted: entry.calls_attempted });
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
          const checksText = await board.locator('section[aria-label="Application checks"]').innerText();
          const replyText = (await board.locator(`section[aria-label="${replyBlock()}"]`).count()) ? await board.locator(`section[aria-label="${replyBlock()}"]`).innerText() : '';
          const replyReason = [body.clarification && body.clarification.model_reason, body.reply_reason, body.status === 'clarify' ? null : body.reason].find(value => typeof value === 'string' && value.trim());
          if (body.outcome_source === 'model_report') check(`outcomes: ${name}: the reason of the reply stands in the reply block, not under the application checks`,
            typeof replyReason === 'string' && replyText.includes(replyReason.trim()) && !checksText.includes(replyReason.trim()));
          if (body.outcome_source === 'application_check') check(`outcomes: ${name}: the page says that no call was made, and only for a stop before any call`,
            /The application stopped the request with its own check\./.test(replyText) && /(No model call was|did not look up an authored reply)/.test(replyText));
          else check(`outcomes: ${name}: the page does not say that no call was made`, !/(No model call was|did not look up an authored reply)/.test(text));
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

    // Undo to a state that has a control, and "Remove every applied control" with its undo.
    async history() {
      const { baseline, record, others } = await startFlow('history');
      await chooseMethod('manual_category');
      // The chooser starts with an empty option ("Choose an existing category"); it is not a category.
      const names = await panel.locator('#semantic-category option').evaluateAll(options => options.map(option => option.value).filter(Boolean));
      // The second control raises a category whose items stand low in the feed, so that its effect on the order is visible.
      const first = scenario.manualCategory;
      const low = [...baseline.feed.items].reverse().find(item => item.categories.some(name => name !== first && names.includes(name)));
      const second = low ? low.categories.find(name => name !== first && names.includes(name)) : names.find(name => name !== first);
      check('history: the scenario has two existing categories', Boolean(first && second), { names });
      const labels = state => state.groups.map(group => group.label);
      async function addManual(category, operation) {
        await panel.locator('#semantic-category').selectOption(category);
        await panel.locator('#semantic-operation').selectOption(operation);
        const before = await serverState();
        const answer = await submit(() => panel.getByRole('button', { name: 'Show the proposed change' }).click(), '/api/semantic/preview', 30000);
        check(`history: the review of "Manual: ${category}" is ready and changed nothing`, answer.body && answer.body.ready === true && same(await serverState(), before));
        return approveAndRead('history', 'Approve this exact item set and apply', 'apply');
      }
      const one = await addManual(first, 'exclude');
      const two = await addManual(second, 'boost');
      const expectedTwo = expectedFeed(baseline, newControls(two, baseline));
      check('history: with two controls the applied feed has the order that both controls give', inOrder(two.feed.items.map(item => item.item_id), expectedTwo),
        { applied: two.feed.items.map(item => item.item_id), expected: expectedTwo.order.slice(0, 10) });
      check('history: two controls are applied', same(labels(two).sort(), [`Manual: ${first}`, `Manual: ${second}`].sort()), { applied: labels(two) });
      // Undo goes back one step: to the state with the first control, not to the empty state.
      await submit(() => panel.getByRole('button', { name: 'Undo the last change (review first)' }).click(), '/api/semantic/history/preview', 30000);
      check('history: the undo review changed nothing', same(await serverState(), two));
      const undone = await approveAndRead('history', 'Approve the undo', 'undo');
      check('history: Undo returns to the exact state with the first control', same(undone.feed, one.feed) && same(undone.groups, one.groups), { applied: labels(undone) });
      check('history: the page lists the controls of the server after the undo', same((await panel.locator('ul.applied-controls li').allInnerTexts()).length, undone.groups.length));
      // "Remove every applied control": a review first, then the approval.
      await submit(() => panel.getByRole('button', { name: 'Remove every applied control (review first)' }).click(), '/api/semantic/history/preview', 30000);
      const clearText = await board.innerText();
      check('history: the removal review has its own title and changed nothing', /Remove every applied control/.test(clearText) && same(await serverState(), undone)
        && await approve('Approve: remove every control').count() === 1, { title: clearText.split('\n').slice(0, 3) });
      check('history: the stage line names the review of the removal, not an undo', /review the removal/.test(await panel.locator('ol.stage-line').innerText()));
      const cleared = await approveAndRead('history', 'Approve: remove every control', 'clear');
      check('history: the removal leaves no control and the starting feed', cleared.groups.length === 0 && same(cleared.feed, baseline.feed), { applied: labels(cleared) });
      check('history: the page says that every control is removed', /Every applied control is removed\./.test(await board.innerText()) && /every control is removed/.test(await panel.locator('ol.stage-line').innerText()));
      // The removal can be undone: the first control comes back.
      await submit(() => panel.getByRole('button', { name: 'Undo the last change (review first)' }).click(), '/api/semantic/history/preview', 30000);
      const back = await approveAndRead('history', 'Approve the undo', 'undo');
      check('history: the undo of the removal restores the exact state before it', same(back.feed, undone.feed) && same(back.groups, undone.groups), { applied: labels(back) });
      check('history: the conditions A to E, the topic tool and the fictional items are unchanged', same(await otherState(), others));
      // Leave the state as it was at the start.
      await submit(() => panel.getByRole('button', { name: 'Remove every applied control (review first)' }).click(), '/api/semantic/history/preview', 30000);
      const end = await approveAndRead('history', 'Approve: remove every control', 'clear');
      check('history: the flow ends with no control and the starting feed', end.groups.length === 0 && same(end.feed, baseline.feed));
      await shot('history-end');
      record.outcome = 'completed: undo to a state with a control, removal of every control, undo of the removal';
    },

    // A request that gets no usable reply. With the hand-written replies: a typed request. With a provider: the bundled request.
    async failure() {
      const { baseline, record, others } = await startFlow('failure');
      const method = receipt.status.scenario_requests && typeof receipt.status.scenario_requests.vocabulary === 'string' ? 'vocabulary' : 'configured_model';
      await chooseMethod(method);
      const route = method === 'vocabulary' ? '/api/semantic/vocabulary/preview' : '/api/semantic/preview';
      if (authored()) await panel.locator('#semantic-text').fill(TYPED_REQUEST); else await insertRequest(method);
      const answer = await submit(() => panel.getByRole('button', { name: 'Interpret my request' }).click(), route, STAGE_TIMEOUT);
      const body = answer.body || {};
      record.observed = { http: answer.http, status: body.status || null, outcome_source: body.outcome_source || null, calls_attempted: body.calls_attempted ?? null };
      if (body.ready === true) { await board.getByRole('button', { name: 'Discard this review and apply nothing' }).click(); record.outcome = 'the provider answered; no failure to show'; return; }
      const text = (await board.count()) ? await board.innerText() : '';
      fs.writeFileSync(path.join(OUT, 'failure-board.txt'), text);
      // The description route answers a failed call with HTTP 502 and the same structured result; the other routes with HTTP 200.
      check('failure: the server reports a begun call that gave no usable reply', [200, 502].includes(answer.http) && body.outcome_source === 'provider_failure' && body.calls_attempted >= 1, record.observed);
      check('failure: the page names the failed call and never says that no call was made',
        (authored() ? /No authored reply exists for this request/.test(text) : /The call to the provider failed/.test(text)) && !/(No model call was|did not look up an authored reply|No model was called)/.test(text));
      check('failure: the page offers no Apply and no button that sends the same refusal again',
        await approve().count() === 0 && await board.getByRole('button', { name: /Use this as|Add this meaning/ }).count() === 0 && /Nothing was applied\./.test(text));
      check('failure: the stage line shows the stop in the stage of the call', /stopped; nothing applied/.test(await panel.locator('ol.stage-line').innerText()));
      const after = await serverState();
      check('failure: nothing changed on the server', same(after, baseline) && same(await otherState(), others));
      await shot('failure-result');
      record.outcome = 'completed: the failed call is named, nothing applied';
    },

    // The page clock passes five minutes; then the server refuses a review that a newer request replaced.
    async expired() {
      const { baseline, record, others } = await startFlow('expired');
      await chooseMethod('manual_category');
      await panel.locator('#semantic-category').selectOption(scenario.manualCategory);
      await submit(() => panel.getByRole('button', { name: 'Show the proposed change' }).click(), '/api/semantic/preview', 30000);
      check('expired: the decision block states the time limit', /Approve before .+\. After that time the server no longer accepts this review\./.test(await board.locator('section[aria-label="Your decision"]').innerText()));
      await page.clock.fastForward('05:00');
      await page.waitForFunction(() => document.querySelector('section[aria-label="Review board"]')?.dataset.expired === 'true', null, { timeout: 10000 });
      const late = await board.innerText();
      check('expired: after five minutes the review is marked as expired and cannot be approved',
        /EXPIRED · NOTHING WAS APPLIED/.test(late) && /This review is older than five minutes\./.test(late) && await board.locator('section[data-block="decision"] button.primary').count() === 0
          && /expired; nothing applied/.test(await panel.locator('ol.stage-line').innerText()));
      await shot('expired-page-clock');
      await board.getByRole('button', { name: 'Close this expired review' }).click();
      check('expired: closing the expired review changes nothing', same(await serverState(), baseline) && /The expired review is closed\. Nothing was applied\./.test(await status().innerText()));
      // The server: a newer preview in the same session replaces the review that the page shows.
      await submit(() => panel.getByRole('button', { name: 'Show the proposed change' }).click(), '/api/semantic/preview', 30000);
      const newer = await context.request.post(`${BASE}/api/semantic/preview`, { headers: headers(), data: { user_id: USER, text: '', label: 'A newer review', backend: 'manual_category',
        category: scenario.manualCategory, operation: 'boost', strength: 'standard', mode: 'merge', candidate_ids: baseline.feed.baseline_items.slice(0, 10), action_source: 'ollama' } });
      check('expired: a newer review was made in the same session', newer.status() === 200);
      const refused = await submit(() => approve().click(), '/api/semantic/apply', 30000);
      const text = await board.innerText();
      check('expired: the server refuses the replaced review, and the page says that it has expired and that nothing was applied',
        refused.http >= 400 && /This review has expired/.test(text) && /Nothing was applied\./.test(text) && await approve().count() === 0, { http: refused.http });
      check('expired: nothing changed on the server', same(await serverState(), baseline) && same(await otherState(), others));
      await shot('expired-server');
      record.outcome = 'completed: page expiry and server refusal; nothing applied';
    },

    // A new category: the definition under review is rejected, and the server no longer accepts it.
    async reject() {
      const { baseline, record, others } = await startFlow('reject');
      await chooseMethod('staged');
      await insertRequest('staged');
      const answer = await submit(() => panel.getByRole('button', { name: 'Propose a definition for review' }).click(), '/api/semantic/definition/preview', STAGE_TIMEOUT);
      if (!answer.body || answer.body.definition_ready !== true) return stopped('reject', record, answer);
      const definition = board.locator('[aria-label="Category definition review"]');
      const discard = await submit(() => definition.getByRole('button', { name: 'Reject this definition' }).click(), '/api/semantic/definition/discard', 30000);
      check('reject: the server accepts the rejection', discard.http === 200, { http: discard.http, body: discard.body });
      check('reject: the definition review is gone and the page says that nothing was classified or applied',
        await definition.count() === 0 && /You rejected the definition\. Nothing was classified or applied\./.test(await status().innerText()));
      const late = await context.request.post(`${BASE}/api/semantic/definition/classify`, { headers: headers(), data: { user_id: USER, plan_id: answer.body.definition_plan_id, evidence_reviewed: true } });
      check('reject: the server no longer classifies with the rejected definition', late.status() >= 400, { http: late.status() });
      check('reject: nothing changed on the server', same(await serverState(), baseline) && same(await otherState(), others));
      await shot('reject-done');
      record.outcome = 'completed: definition rejected; nothing classified or applied';
    },

    // The original conditions A to E.
    async original() {
      const record = { started_utc: utc(), outcome: 'started' };
      receipt.flows_result.original = record;
      await page.getByRole('button', { name: 'Original study (A to E)' }).click();
      const categories = (await getJson('categories')).categories;
      const readable = categories.length > 0 && categories.every(name => /^category_\d+$/.test(name));
      const control = page.locator('section[aria-label="Original category control"]'), profile = page.locator('section[aria-label="Editable profile"]');
      if (!readable) {
        const text = await control.innerText();
        check('original: on named categories the instruction and the profile are disabled, with the reason and the command for the fixture',
          await page.locator('#control').count() === 0 && await page.locator('#profile').count() === 0
            && /This data has named categories/.test(text) && /--scenario conditions/.test(text) && /Not available on this data/.test(await profile.innerText()), { categories });
        await control.scrollIntoViewIfNeeded();
        await shot('original-disabled');
        record.outcome = 'completed: instruction and profile disabled on named categories';
        return;
      }
      const start = await getJson(`compare?user_id=${USER}`);
      const ids = condition => condition.items.map(item => item.item_id);
      check('original: the language view is not offered here, and the page says why', await page.getByRole('button', { name: 'Language controls', exact: true }).isDisabled()
        && /not available here/.test(await page.locator('[data-role="language-unavailable"]').innerText()));
      await page.locator('#control').fill(`Show me more ${categories[0]}`);
      const instruction = page.waitForResponse(response => response.url() === BASE + '/api/control', { timeout: 30000 });
      await control.getByRole('button', { name: /Apply instruction/ }).click();
      check('original: the server accepts the instruction', (await instruction).status() === 200);
      await control.locator('.alert').waitFor({ state: 'visible', timeout: 10000 });
      const said = await control.locator('.alert').innerText();
      const afterInstruction = await getJson(`compare?user_id=${USER}`);
      check('original: the message stands next to the instruction and names what was applied', said.startsWith(`Applied: show more ${categories[0]}`), { said });
      check('original: the instruction changes C and E and leaves A, B and D as they were',
        !same(ids(afterInstruction.C), ids(start.C)) && !same(ids(afterInstruction.E), ids(start.E)) && same(ids(afterInstruction.A), ids(start.A)) && same(ids(afterInstruction.B), ids(start.B)) && same(ids(afterInstruction.D), ids(start.D)));
      await page.locator('#profile').fill(`Mute ${categories[1]}.`);
      const saved = page.waitForResponse(response => response.url() === BASE + '/api/profile/text', { timeout: 30000 });
      await profile.getByRole('button', { name: 'Save profile' }).click();
      check('original: the server accepts the profile', (await saved).status() === 200);
      await profile.locator('.alert').waitFor({ state: 'visible', timeout: 10000 });
      const afterProfile = await getJson(`compare?user_id=${USER}`);
      check('original: the profile mutes its category in D and leaves A and B as they were',
        afterProfile.D.items.every(item => !item.categories.includes(categories[1])) && same(ids(afterProfile.A), ids(start.A)) && same(ids(afterProfile.B), ids(start.B)));
      await shot('original-applied');
      // A text that the rule parser cannot read: the message stands next to the instruction, and nothing changes.
      await page.locator('#control').fill('Show me more bananas');
      await control.getByRole('button', { name: /Apply instruction/ }).click();
      await control.locator('.alert').waitFor({ state: 'visible', timeout: 10000 });
      check('original: an instruction without a category is refused next to the instruction, and nothing changes',
        /Nothing was applied/.test(await control.locator('.alert').innerText()) && same(await getJson(`compare?user_id=${USER}`), afterProfile));
      await control.locator('.alert').scrollIntoViewIfNeeded();
      await shot('original-refused');
      // Reset this user: confirm first, then the conditions are as at the start.
      await page.getByRole('button', { name: 'Reset this user ↺' }).click();
      await page.getByRole('button', { name: 'Yes, remove everything' }).click();
      await page.waitForFunction(() => /Every control and all item feedback of this user is removed\./.test(document.body.innerText), null, { timeout: 30000 });
      check('original: after the reset the five conditions are as at the start', same(await getJson(`compare?user_id=${USER}`), start));
      record.outcome = 'completed: instruction, profile, refused text and reset on category IDs';
    },

    async fictional() {
      const { baseline, record, others } = await startFlow('fictional');
      const brief = receipt.status.scenario_requests ? receipt.status.scenario_requests.synthetic : undefined;
      check('fictional: the server supplies an example brief', typeof brief === 'string' && brief.length > 0);
      await page.locator('summary', { hasText: 'Open the fictional items' }).click();
      const drafts = page.locator('section[aria-label="Fictional items"]');
      await drafts.getByRole('button', { name: 'Write a fictional draft' }).waitFor({ state: 'visible', timeout: 30000 });
      const start = await fictionalState();
      check('fictional: starts with no fictional item', start.items.length === 0 && start.generation_available !== false, { provider: start.generation_provider });
      await drafts.getByRole('button', { name: 'Insert the example description' }).click();
      check('fictional: the brief is the exact example brief', await drafts.locator('#synthetic-brief').inputValue() === brief);
      await drafts.getByRole('checkbox').check();
      await show('fictional: a brief for an item that does not exist', drafts.locator('#synthetic-brief'), 4000);
      const draft = page.waitForResponse(response => response.url() === BASE + '/api/synthetic/preview', { timeout: STAGE_TIMEOUT });
      await drafts.getByRole('button', { name: 'Write a fictional draft' }).click();
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
      await reviewBlock.getByRole('button', { name: 'Approve and add to the list of fictional items' }).click();
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
      await drafts.getByRole('button', { name: `Remove fictional item ${drafted.draft.item_id}` }).click();
      await removal;
      const removed = await fictionalState();
      check('fictional: removal empties the separate feed', removed.items.length === 0 && removed.feed.items.length === 0 && same((await serverState()).feed, baseline.feed));
      await shot('fictional-removed');
      record.outcome = 'completed: draft reviewed, admitted to the separate feed, removed; observed feed unchanged';
    },
  };

  try {
    // The flow "expired" moves the clock of the page. The clock runs at its normal speed until then.
    if (FLOWS.includes('expired')) await page.clock.install();
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
    // The language view exists when the server has item descriptions; otherwise the page says why.
    await page.waitForFunction(() => [...document.querySelectorAll('.view-tabs button')].some(button => button.innerText === 'Language controls' && !button.disabled)
      || document.querySelector('[data-role="language-unavailable"]'), null, { timeout: 30000 });
    receipt.language_view = await page.getByRole('button', { name: 'Language controls', exact: true }).isDisabled() ? 'not available' : 'available';
    if (receipt.language_view === 'available') {
      await ensureLanguage();
      check('the language view names what it is and makes no accuracy claim', /It does not measure accuracy or satisfaction\./.test(await page.locator('[data-role="view-intro"]').innerText()));
    } else check('the page says why the language view is not available', /not available here/.test(await page.locator('[data-role="language-unavailable"]').innerText()));
    await shot('start');
    await show('start: the status strip names the data and the provider', page.locator('.status-strip'), 4000);
    if (receipt.language_view === 'available') await show('start: the language controls and their six stages', panel.locator('ol.stage-line'), 4000);
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
