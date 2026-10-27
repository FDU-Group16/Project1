// Real shared HTTP client in Vite + real browser Fetch/AbortController.
// Only dedicated __transport-test endpoints are intercepted; no business endpoint or module is replaced.
// Run: NODE_PATH=<existing playwright> node apps/web/tests/shared-client.browser.cjs <vite-base>
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const base = process.argv[2] || 'http://127.0.0.1:5173';
const checks = [];

(async () => {
  const browser = await chromium.launch({ channel: process.env.WEB_BROWSER_CHANNEL || 'chrome', headless: true });
  const page = await browser.newPage();
  const errors = [];
  const gates = new Map();
  const releaseAll = [];
  page.on('pageerror', error => errors.push(error.message));
  const deadline = (promise, label) => {
    let timer;
    const timeout = new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(`Timeout: ${label}`)), 8000); });
    return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
  };
  const session = async id => page.evaluate(async value => {
    const { setSession } = await import('/src/shared/auth/session.ts');
    setSession({ accessToken: `transport-token-${value}`, expiresAt: new Date(Date.now() + 60_000).toISOString(), user: { id: value, displayName: `HTTP test ${value}`, departmentId: null, permissions: [] } });
  }, id);
  const invoke = (service, path, cancellable = false) => page.evaluate(async ({ service, path, cancellable }) => {
    const { request } = await import('/src/shared/api/client.ts');
    const abort = new AbortController();
    if (cancellable) window.__transportAbort = () => abort.abort();
    try { return { ok: true, value: await request(service, path, cancellable ? { signal: abort.signal } : {}) }; }
    catch (error) { return { ok: false, name: error.name, status: error.status, code: error.code, message: error.message }; }
    finally { if (cancellable) delete window.__transportAbort; }
  }, { service, path, cancellable });
  const state = () => page.evaluate(async () => {
    const { auth, storedSession } = await import('/src/shared/auth/session.ts');
    return { id: auth.session?.user.id ?? null, notice: auth.notice, stored: storedSession()?.user.id ?? null };
  });
  const delayed = (name, status, body) => {
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    releaseAll.push(release);
    gates.set(name, { gate, status, body });
    return release;
  };

  try {
    await page.route('**/__transport-test/**', async route => {
      const name = new URL(route.request().url()).pathname.split('/').pop();
      const fixture = gates.get(name);
      if (fixture) {
        await fixture.gate;
        await route.fulfill({ status: fixture.status, contentType: 'application/json', body: JSON.stringify(fixture.body) }).catch(error => {
          // Chromium may discard the intercepted request after caller cancellation.
          if (name !== 'cancel') throw error;
        });
        return;
      }
      if (name === 'problem') return route.fulfill({ status: 409, contentType: 'application/problem+json', body: JSON.stringify({ type: 'about:blank', title: 'Conflict', status: 409, code: 'STALE_REVISION', detail: '原请求版本已过期。' }) });
      if (name === 'nested') return route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({ error: { code: 'INVALID_INPUT', message: '维修说明不能为空。' } }) });
      if (name === 'unauthorized') return route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ error: { code: 'UNAUTHENTICATED', message: '身份已失效。' } }) });
      throw new Error(`Unexpected test endpoint: ${name}`);
    });
    await page.goto(base + '/m2');
    await page.getByRole('heading', { name: '整教室预约与审批' }).waitFor();
    await session('original');

    const problem = await invoke('m1', '/api/v1/__transport-test/problem');
    assert.equal(problem.ok, false);
    assert.equal(problem.status, 409);
    assert.equal(problem.code, 'STALE_REVISION');
    assert.equal(problem.message, '原请求版本已过期。');
    assert.equal((await state()).id, 'original');
    checks.push('M1 Problem+JSON preserves status/code/detail without clearing login');

    const nested = await invoke('m3', '/v1/__transport-test/nested');
    assert.equal(nested.ok, false);
    assert.equal(nested.status, 422);
    assert.equal(nested.code, 'INVALID_INPUT');
    assert.equal(nested.message, '维修说明不能为空。');
    checks.push('M3 nested error preserves status/code/message');

    const denied = await invoke('m3', '/v1/__transport-test/unauthorized');
    assert.equal(denied.status, 401);
    assert.equal(denied.code, 'UNAUTHENTICATED');
    const cleared = await state();
    assert.equal(cleared.id, null);
    assert.equal(cleared.stored, null);
    assert.match(cleared.notice, /登录已过期|无效/);
    checks.push('Current-session 401 clears shared memory/storage and records the expiry notice');

    await session('cancellation');
    const releaseCancel = delayed('cancel', 200, { value: 'must not be delivered' });
    const sentCancel = page.waitForRequest(request => new URL(request.url()).pathname.endsWith('/__transport-test/cancel'));
    const cancellation = invoke('m1', '/api/v1/__transport-test/cancel', true);
    await sentCancel;
    await page.waitForFunction(() => typeof window.__transportAbort === 'function');
    await page.evaluate(() => window.__transportAbort());
    const cancelled = await deadline(cancellation, 'caller AbortSignal cancels the in-flight request');
    releaseCancel();
    assert.equal(cancelled.ok, false);
    assert.equal(cancelled.name, 'AbortError');
    assert.equal((await state()).id, 'cancellation');
    checks.push('Caller AbortSignal cancels Fetch promptly without clearing login');

    for (const responseStatus of [200, 401]) {
      const name = `late-${responseStatus}`;
      await session(`old-${responseStatus}`);
      const release = delayed(name, responseStatus, responseStatus === 200 ? { value: 'old private response' } : { error: { code: 'UNAUTHENTICATED', message: 'old session only' } });
      const sent = page.waitForRequest(request => new URL(request.url()).pathname.endsWith(`/__transport-test/${name}`));
      const pending = invoke('m3', `/v1/__transport-test/${name}`);
      const request = await sent;
      assert.equal(request.headers().authorization, `Bearer transport-token-old-${responseStatus}`);
      await session(`new-${responseStatus}`);
      release();
      const result = await deadline(pending, `identity switch rejects late HTTP ${responseStatus}`);
      assert.equal(result.ok, false);
      assert.equal(result.code, 'SESSION_CHANGED');
      assert.equal((await state()).id, `new-${responseStatus}`, 'Late response cannot erase the new identity');
      assert.equal((await state()).stored, `new-${responseStatus}`);
    }
    checks.push('Identity switch rejects late success and late 401 while preserving the new session');

    await page.evaluate(async () => { const { clearSession } = await import('/src/shared/auth/session.ts'); clearSession(); });
    await page.goto(base + '/m2');
    await page.getByRole('heading', { name: '整教室预约与审批' }).waitFor();
    assert.equal(await page.locator('main h1').count(), 1);
    await page.reload();
    await page.getByRole('heading', { name: '整教室预约与审批' }).waitFor();
    assert.equal(new URL(page.url()).pathname, '/m2');
    checks.push('M2 entry remains available after shared-session changes and refresh');
    assert.deepEqual(errors, [], 'No uncaught browser JavaScript errors');
    console.log(JSON.stringify({ base, checks, errors }, null, 2));
  } finally {
    releaseAll.forEach(release => release());
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
