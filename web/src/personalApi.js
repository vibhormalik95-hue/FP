// API client. Personal (loopback) mode adds browser fetch safeguards; there is no credential.
export function createApiClient({personal, fetchImpl = fetch, origin = globalThis.location?.origin}) {
  async function run(url, options) {
    const safeguards = personal ? {redirect:'error', credentials:'omit', cache:'no-store',
      referrerPolicy:'no-referrer'} : {};
    return await fetchImpl(url, {...options, ...safeguards});
  }
  async function request(path, body, method='POST', sessionToken=null) {
    const headers = {'Content-Type':'application/json',
      ...(sessionToken ? {'X-Session-ID':sessionToken} : {})};
    if (typeof path !== 'string' || typeof origin !== 'string') throw new Error('Invalid API target.');
    const target = new URL(`/api/${path}`, origin);
    if (target.origin !== origin || !target.pathname.startsWith('/api/') || target.hash) throw new Error('Invalid API target.');
    const response = await run(target.pathname + target.search, {method:body === undefined ? 'GET' : method,
      headers, ...(body === undefined ? {} : {body:JSON.stringify(body)})});
    let payload;
    try {
      payload = await response.json();
    } catch (error) {
      // Error responses may be plain text, HTML or empty. Never echo their body
      // or parser diagnostics; successful responses must still be valid JSON.
      if (response.ok) throw error;
    }
    // An error answer can carry a structured result (for example a failed provider call); keep it for the page.
    if (!response.ok) throw Object.assign(new Error(typeof payload?.detail === 'string' ? payload.detail : 'Check the input and try again.'),
      {status: response.status, payload: payload && typeof payload === 'object' && !Array.isArray(payload) ? payload : null});
    return payload;
  }
  return {request};
}
