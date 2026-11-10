// A browser-memory-only credential. Nothing is written to URL, storage or logs.
export function createApiClient({personal, fetchImpl = fetch, origin = globalThis.location?.origin}) {
  let credential = null;
  let generation = 0;
  const active = new Set();

  async function run(url, options) {
    const controller = new AbortController();
    active.add(controller);
    try {
      const safeguards = personal ? {redirect:'error', credentials:'omit', cache:'no-store',
        referrerPolicy:'no-referrer'} : {};
      return await fetchImpl(url, {...options, signal: controller.signal, ...safeguards});
    } finally {
      active.delete(controller);
    }
  }
  function lock() {
    credential = null;
    generation += 1;
    for (const controller of active) controller.abort();
    active.clear();
  }
  async function unlock(candidate) {
    if (!personal || typeof candidate !== 'string' || !candidate) return false;
    const version = ++generation;
    try {
      const response = await run('/api/status', {method:'GET', headers:{'X-Personal-Operator-Token':candidate}});
      if (!response.ok || generation !== version) return false;
      credential = candidate;
      return true;
    } catch (_) { return false; }
  }
  async function request(path, body, method='POST', sessionToken=null) {
    if (personal && credential === null) throw new Error('Unlock the personal session first.');
    const version = generation;
    const headers = {'Content-Type':'application/json',
      ...(sessionToken ? {'X-Session-ID':sessionToken} : {}),
      ...(personal ? {'X-Personal-Operator-Token':credential} : {})};
    if (typeof path !== 'string' || typeof origin !== 'string') throw new Error('Invalid API target.');
    const target = new URL(`/api/${path}`, origin);
    if (target.origin !== origin || !target.pathname.startsWith('/api/') || target.hash) throw new Error('Invalid API target.');
    const response = await run(target.pathname + target.search, {method:body === undefined ? 'GET' : method,
      headers, ...(body === undefined ? {} : {body:JSON.stringify(body)})});
    if (personal && version !== generation) throw new Error('Personal session is locked.');
    let payload;
    try {
      payload = await response.json();
    } catch (error) {
      if (personal && version !== generation) throw new Error('Personal session is locked.');
      // Error responses may be plain text, HTML or empty. Never echo their body
      // or parser diagnostics; successful responses must still be valid JSON.
      if (response.ok) throw error;
    }
    if (personal && version !== generation) throw new Error('Personal session is locked.');
    if (!response.ok) throw new Error(typeof payload?.detail === 'string' ? payload.detail : 'Check the input and try again.');
    return payload;
  }
  return {unlock, lock, request};
}
