// A page function: every visible CJK character on the current page (U+3000-U+303F, U+3400-U+9FFF,
// U+FF00-U+FFEF). Returns a list of "where: text" strings; an empty list means none.
// Used by tests/browser/cjk_check.cjs and live by the recorder during a take.
() => {
  const c = String.fromCharCode;
  const R = new RegExp('[' + c(0x3000) + '-' + c(0x303f) + c(0x3400) + '-' + c(0x9fff) + c(0xff00) + '-' + c(0xffef) + ']');
  const hits = [];
  const add = (where, text) => {
    if (!text) return;
    for (const line of String(text).split('\n')) if (R.test(line)) hits.push(where + ': ' + line.trim().slice(0, 100));
  };
  add('page', document.body.innerText);
  add('title', document.title);
  document.querySelectorAll('option').forEach(o => add('option', o.textContent));
  document.querySelectorAll('input, textarea').forEach(e => { add('field', e.value); add('placeholder', e.placeholder); });
  document.querySelectorAll('[title], [aria-label]').forEach(e => { add('title', e.getAttribute('title')); add('label', e.getAttribute('aria-label')); });
  return hits;
}
