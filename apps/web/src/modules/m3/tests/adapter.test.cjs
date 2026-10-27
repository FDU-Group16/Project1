/** HTTP boundary tests for the real M3 adapter/session. No browser or extra dependency required. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const { createRequire } = require('node:module');
const webRequire = createRequire(path.resolve(__dirname, '../../../../package.json'));
const ts = webRequire('typescript');

function load(fetchImpl) {
  const cache = new Map();
  function moduleFor(name) {
    if (cache.has(name)) return cache.get(name);
    const exports = {};
    cache.set(name, exports);
    const source = fs.readFileSync(path.resolve(__dirname, '..', `${name}.ts`), 'utf8');
    const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
    vm.runInNewContext(code, {
      exports, require: id => id === 'vue' ? webRequire('vue') : moduleFor(id.replace('./', '')),
      Headers, DOMException, AbortController, window: { setTimeout, clearTimeout }, fetch: fetchImpl,
    }, { filename: `${name}.ts` });
    return exports;
  }
  return { api: moduleFor('api'), session: () => moduleFor('session').createM3Session() };
}
const response = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const defer = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };

// These replace only transport. All header handling, payload serialization and error logic is actual code.
test('creation and retries preserve their supplied idempotency key and authenticated JSON payload', async () => {
  const calls = [];
  const { api } = load(async (url, options) => { calls.push({ url, options }); return response({ id: 'order-1' }); });
  let token = '';
  const client = api.createM3Api(() => token);
  await client.context();
  assert.equal(calls[0].options.headers.has('Authorization'), false);
  token = 'demo-student';
  const payload = { roomId: 'room-101', title: '灯具故障', description: '无法点亮', category: 'electrical' };
  await client.create(payload, 'stable-key');
  await client.create(payload, 'stable-key');
  for (const call of calls.slice(1)) {
    assert.equal(call.url, '/api/m3/v1/work-orders');
    assert.equal(call.options.method, 'POST');
    assert.equal(call.options.headers.get('Authorization'), 'Bearer demo-student');
    assert.equal(call.options.headers.get('Idempotency-Key'), 'stable-key');
    assert.equal(call.options.headers.get('Content-Type'), 'application/json');
    assert.deepEqual(JSON.parse(call.options.body), payload);
  }
});

test('actions encode identifiers and preserve optimistic version', async () => {
  let call;
  const { api } = load(async (url, options) => { call = { url, options }; return response({ id: 'one/two' }); });
  await api.createM3Api(() => 'test').act('one/two', 'reject', { version: 7, reason: '仍有故障' });
  assert.equal(call.url, '/api/m3/v1/work-orders/one%2Ftwo/reject');
  assert.equal(JSON.parse(call.options.body).version, 7);
});

test('conflicts remain failures and malformed successful responses do not become empty success', async () => {
  const conflict = load(async () => response({ code: 'STALE_VERSION', detail: 'stale' }, 409)).api;
  await assert.rejects(conflict.createM3Api(() => '').get('order'), error => error.status === 409 && error.code === 'STALE_VERSION' && error.message.includes('刷新'));
  const malformed = load(async () => new Response('<html>proxy fallback</html>', { status: 200 })).api;
  await assert.rejects(malformed.createM3Api(() => '').context(), error => error.status === 0 && error.message.includes('转发'));
});

test('identity reset aborts all in-flight transport calls', async () => {
  const { api } = load((_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
  }));
  const client = api.createM3Api(() => 'old-identity');
  const first = client.me();
  const second = client.rooms();
  client.abortAll();
  await assert.rejects(first, error => api.isAbort(error));
  await assert.rejects(second, error => api.isAbort(error));
});

test('late identity response cannot restore the old actor or issue directory calls after a switch', async () => {
  const oldProfile = defer();
  const directoryCalls = [];
  const { session: createSession } = load(async (url, options) => {
    const token = options.headers.get('Authorization');
    if (url.endsWith('/me') && token === 'Bearer demo-student') return oldProfile.promise;
    if (url.endsWith('/me')) return response({ id: 'student-2', name: '新身份', roles: ['student'] });
    if (url.endsWith('/rooms')) { directoryCalls.push(token); return response({ items: [{ id: 'room-102', name: '新身份可见房间' }] }); }
    throw new Error(`Unexpected call ${url}`);
  });
  const session = createSession();
  session.context.value = { mode: 'development', dependencyMode: 'stub', message: '' };
  const first = session.selectIdentity('demo-student');
  await session.selectIdentity('demo-student-2');
  oldProfile.resolve(response({ id: 'student-1', name: '旧身份', roles: ['student'] }));
  await first;
  assert.equal(session.actor.value.id, 'student-2');
  assert.equal(session.rooms.value[0].id, 'room-102');
  assert.deepEqual(directoryCalls, ['Bearer demo-student-2']);
  session.pendingCreate.value = { key: 'old-key', payload: {}, uncertain: true };
  await session.selectIdentity('');
  assert.equal(session.actor.value, null);
  assert.equal(session.rooms.value.length, 0);
  assert.equal(session.pendingCreate.value, null);
  assert.equal(session.token.value, '');
});

test('normal runtime never enables synthetic identities', async () => {
  let calls = 0;
  const { session: createSession } = load(async () => { calls += 1; throw new Error('must not request'); });
  const session = createSession();
  session.context.value = { mode: 'production', dependencyMode: 'http', message: '' };
  await session.selectIdentity('demo-dispatcher');
  assert.equal(calls, 0);
  assert.equal(session.actor.value, null);
  assert.equal(session.token.value, '');
});

/** Execute the actual detail component's script with Vue reactivity, replacing only router/transport/lifecycle. */
function detailHarness() {
  const vue = webRequire('vue');
  const api = load(async () => { throw new Error('Unexpected transport'); }).api;
  const model = {
    id: 'order-1', reporterId: 'student-1', assigneeId: 'technician-1', status: 'ASSIGNED',
    version: 2, rating: null, syncStatus: 'NONE',
  };
  const transport = {
    get: async () => ({ ...model }),
    act: async () => ({ ...model, version: 3 }),
  };
  const session = {
    actor: vue.ref({ id: 'technician-1', name: '维修员 A', roles: ['technician'] }),
    technicians: vue.ref([]), context: vue.ref({ mode: 'development' }), api: transport,
  };
  const component = fs.readFileSync(path.resolve(__dirname, '../pages/OrderDetailPage.vue'), 'utf8');
  const script = component.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1];
  const source = script + '\nglobalThis.component = { refresh, act, order, fetchError, actionError, actionMessage, needsRefresh, hasActions, assigneeId, resolution, rejectReason, cancelReason, retryReason, rating, comment };';
  const sandbox = {
    exports: {}, document: { hidden: false }, setInterval, clearInterval,
    require: id => {
      if (id === 'vue') return { ...vue, onMounted: () => {}, onUnmounted: () => {} };
      if (id === 'vue-router') return { useRoute: () => ({ params: { id: 'order-1' } }) };
      if (id === '../session') return { useM3Session: () => session };
      if (id === '../api') return api;
      if (id === '../labels') return { actionLabels: {}, categoryLabels: {}, displayTime: value => value };
      return {};
    },
  };
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText, sandbox, { filename: 'OrderDetailPage.vue' });
  return { ...sandbox.component, transport, ApiError: api.ApiError };
}
const privateFields = ['assigneeId', 'resolution', 'rejectReason', 'cancelReason', 'retryReason', 'rating', 'comment'];
function populateDrafts(view) { for (const field of privateFields) view[field].value = 'sensitive draft'; }
function assertAccessCleared(view) {
  assert.equal(view.order.value, null);
  assert.equal(Boolean(view.hasActions.value), false);
  assert.equal(view.needsRefresh.value, true);
  for (const field of privateFields) assert.equal(view[field].value, '', `${field} retained private data`);
  assert.equal(view.actionMessage.value, '');
  assert.ok(view.fetchError.value, 'access failure must remain visible outside the removed order');
}

test('detail GET access loss clears prior order, all private drafts and operations for 401/403/404', async () => {
  for (const status of [401, 403, 404]) {
    const view = detailHarness();
    await view.refresh();
    assert.equal(view.order.value.id, 'order-1');
    populateDrafts(view);
    view.actionMessage.value = 'old success';
    view.transport.get = async () => { throw new view.ApiError(status, 'access lost'); };
    await view.refresh();
    assertAccessCleared(view);
    let commands = 0;
    view.transport.act = async () => { commands += 1; };
    await view.act('start');
    assert.equal(commands, 0, 'revoked resource must not submit a new command');
  }
});

test('detail command access loss clears prior order and drafts for 401/403/404', async () => {
  for (const status of [401, 403, 404]) {
    const view = detailHarness();
    await view.refresh();
    populateDrafts(view);
    view.transport.act = async () => { throw new view.ApiError(status, 'access lost'); };
    await view.act('start');
    assertAccessCleared(view);
  }
});

test('detail network failure retains a marked snapshot and prevents actions until a successful reload', async () => {
  const view = detailHarness();
  await view.refresh();
  view.resolution.value = 'unfinished note';
  view.transport.get = async () => { throw new view.ApiError(503, 'temporarily offline'); };
  await view.refresh();
  assert.equal(view.order.value.id, 'order-1');
  assert.equal(view.resolution.value, 'unfinished note');
  assert.ok(view.fetchError.value);
  assert.equal(view.needsRefresh.value, true);
  let commands = 0;
  view.transport.act = async () => { commands += 1; return { ...view.order.value, version: 4 }; };
  await view.act('start');
  assert.equal(commands, 0);
  view.transport.get = async () => ({ ...view.order.value, version: 3 });
  await view.refresh();
  assert.equal(view.needsRefresh.value, false);
  assert.equal(view.fetchError.value, '');
  await view.act('start');
  assert.equal(commands, 1);
});

test('late detail read cannot restore a resource cleared by a forbidden command', async () => {
  const view = detailHarness();
  await view.refresh();
  const oldOrder = { ...view.order.value };
  const delayed = defer();
  view.transport.get = () => delayed.promise;
  const reading = view.refresh(true);
  view.transport.act = async () => { throw new view.ApiError(403, 'access revoked'); };
  await view.act('start');
  assertAccessCleared(view);
  delayed.resolve(oldOrder);
  await reading;
  assertAccessCleared(view);
});
