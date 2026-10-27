// Real password login and real M3 HTTP; no authentication or business response is mocked.
// Use a production build, or Vite with VITE_USE_DEV_IDENTITY=false.
// WEB_TEST_ACCOUNTS_FILE=<private seed JSON> NODE_PATH=<existing playwright> node apps/web/tests/test-accounts.browser.cjs <base>
// Optional M3_TEST_ROOM_ID adds a real, synthetic-data work-order lifecycle in that accessible room.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.argv[2] || 'http://127.0.0.1:5173';
const checks = [];
const secrets = [];
let stage = 'read private credential file';
const safeError = error => secrets.reduce((text, value) => value ? text.split(value).join('[REDACTED]') : text, String(error.message || error));

(async () => {
  assert.ok(process.env.WEB_TEST_ACCOUNTS_FILE, 'WEB_TEST_ACCOUNTS_FILE is required');
  const data = JSON.parse(fs.readFileSync(process.env.WEB_TEST_ACCOUNTS_FILE, 'utf8'));
  assert.equal(data.mode, 'test-accounts');
  assert.ok(Array.isArray(data.accounts), 'Seed file must contain accounts');
  const accounts = new Map();
  for (const item of data.accounts) {
    assert.equal(typeof item.username, 'string');
    assert.equal(typeof item.password, 'string');
    assert.ok(item.password.length > 0);
    secrets.push(item.password, JSON.stringify(item.password).slice(1, -1));
    accounts.set(item.username, item);
  }
  const expected = [['m3-student', '报修人'], ['m3-admin', '管理员'], ['m3-worker1', '维修人员'], ['m3-worker2', '维修人员']];
  for (const [username] of expected) assert.ok(accounts.has(username), `Missing account: ${username}`);
  const browser = await chromium.launch({ channel: process.env.WEB_BROWSER_CHANNEL || 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, timezoneId: 'Asia/Shanghai' });
  const errors = [];
  page.on('pageerror', error => errors.push(safeError(error)));
  const settleScreenshot = async () => {
    await page.evaluate(async () => {
      await document.fonts.ready;
      let previous = '', stable = 0;
      for (let frame = 0; frame < 60; frame += 1) {
        await new Promise(resolve => requestAnimationFrame(resolve));
        const current = [innerWidth, innerHeight, document.documentElement.scrollWidth, document.documentElement.scrollHeight,
          ...Array.from(document.querySelectorAll('.app-header, main, main h1, .app-footer')).flatMap(element => {
            const rect = element.getBoundingClientRect(); return [rect.x, rect.y, rect.width, rect.height];
          })].join(',');
        stable = current === previous ? stable + 1 : 0;
        if (stable >= 3) return;
        previous = current;
      }
      throw new Error('Screenshot layout did not stabilize');
    });
  };
  const screenshotDom = () => page.evaluate(() => {
    const geometry = selector => Array.from(document.querySelectorAll(selector)).map(element => {
      const rect = element.getBoundingClientRect();
      return { top: rect.top + scrollY, left: rect.left + scrollX, width: rect.width, height: rect.height };
    });
    return { viewport: { width: innerWidth, height: innerHeight }, scrollY,
      document: { width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight },
      appShells: geometry('.app-shell'), appHeaders: geometry('.app-header'), mainHeadings: geometry('main h1'),
      modules: geometry('.m3-module'), workbenchHeadings: geometry('#m3-title'), footers: geometry('.app-footer') };
  });
  const screenshot = async name => {
    if (!process.env.WEB_TEST_SCREENSHOT_DIR) return;
    // Capture only an empty login form or an authenticated page, never entered passwords.
    const password = page.getByLabel('密码', { exact: true });
    if (await password.count()) assert.equal(await password.inputValue(), '', 'Do not screenshot entered credentials');
    if (await page.locator('.work-orders .refresh-button').count()) {
      await page.waitForFunction(() => !document.querySelector('.work-orders .refresh-button')?.disabled);
    }
    await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: 'instant' }));
    await settleScreenshot();
    const before = await screenshotDom();
    assert.equal(before.appShells.length, 1, 'Screenshot must contain one application shell');
    assert.equal(before.appHeaders.length, 1, 'Screenshot must contain one global header');
    assert.equal(before.mainHeadings.length, 1, 'Screenshot must contain one page heading');
    if (name.includes('workbench')) {
      assert.equal(before.modules.length, 1, 'Screenshot must contain one M3 module');
      assert.equal(before.workbenchHeadings.length, 1, 'Screenshot must contain one workbench');
    }
    fs.mkdirSync(process.env.WEB_TEST_SCREENSHOT_DIR, { recursive: true });
    const output = filename => path.join(process.env.WEB_TEST_SCREENSHOT_DIR, filename);
    const screenshotOptions = { animations: 'disabled', caret: 'hide', scale: 'css' };
    // Keep a viewport capture as independent evidence if Chromium's full-page
    // compositor reuses a stale tile immediately after a viewport resize.
    await page.screenshot({ ...screenshotOptions, path: output(name + '-viewport.png'), fullPage: false });
    await page.screenshot({ ...screenshotOptions, path: output(name + '.png'), fullPage: true });
    const after = await screenshotDom();
    assert.equal(after.appHeaders.length, 1);
    assert.equal(after.mainHeadings.length, 1);
    fs.writeFileSync(output(name + '.dom.json'), JSON.stringify({ before, after }, null, 2));
    if (before.viewport.width === 320 && before.document.height > before.viewport.height) {
      await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' }));
      await settleScreenshot();
      await page.screenshot({ ...screenshotOptions, path: output(name + '-bottom.png'), fullPage: false });
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
      await settleScreenshot();
    }
  };
  const loginPage = async () => {
    await page.goto(base + '/login?redirect=%2Fm3');
    await page.getByRole('heading', { name: '登录校园资源平台' }).waitFor();
    assert.equal(await page.getByLabel('选择开发身份').count(), 0, 'Production password mode cannot expose development identity selection');
  };
  const localSession = () => page.evaluate(() => {
    const value = JSON.parse(sessionStorage.getItem('campus.session.v1') || 'null');
    return value ? { id: value.user.id, name: value.user.displayName, testAccount: value.user.testAccount, synthetic: Boolean(value.synthetic), expiresAt: value.expiresAt } : null;
  });
  const login = async (username, destination = '/m3') => {
    stage = `password login: ${username}`;
    const account = accounts.get(username);
    await page.goto(base + '/login?redirect=' + encodeURIComponent(destination));
    await page.getByLabel('账号', { exact: true }).fill(username);
    await page.getByLabel('密码', { exact: true }).fill(account.password);
    const response = page.waitForResponse(response => new URL(response.url()).pathname === '/api/d/api/v1/auth/login' && response.request().method() === 'POST');
    await page.getByRole('button', { name: '登录', exact: true }).click();
    assert.equal((await response).status(), 200, 'Password login should succeed');
    const target = new URL(destination, base);
    await page.waitForURL(url => url.pathname === target.pathname && url.search === target.search);
    await page.locator('.identity-line').waitFor();
    await page.locator('.test-account-banner').filter({ hasText: '课程测试账号' }).waitFor();
    assert.equal(await page.locator('.development-banner').count(), 0, 'Password test accounts must not be labelled as a local development token');
    const session = await localSession();
    assert.ok(session && session.testAccount === true && session.synthetic === false, 'Server-authenticated temporary identity is marked, not synthesized in Web');
    assert.ok(Date.parse(session.expiresAt) > Date.now());
    if (account.user?.id) assert.equal(session.id, account.user.id);
    const role = expected.find(item => item[0] === username)[1];
    assert.equal(await page.locator('.role-chip').innerText(), role);
  };
  const logout = async () => {
    stage = 'logout and server-side revocation';
    const token = await page.evaluate(() => JSON.parse(sessionStorage.getItem('campus.session.v1')).accessToken);
    secrets.push(token);
    await page.goto(base + '/login?redirect=%2Fm3');
    const response = page.waitForResponse(response => new URL(response.url()).pathname === '/api/d/api/v1/auth/logout' && response.request().method() === 'POST');
    await page.getByRole('button', { name: '退出登录', exact: true }).click();
    assert.equal((await response).status(), 204);
    await page.getByLabel('账号', { exact: true }).waitFor();
    assert.equal(await localSession(), null);
    const revoked = await page.evaluate(async token => (await fetch('/api/d/api/v1/auth/me', { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' })).status, token);
    assert.equal(revoked, 401, 'Logged-out token must be rejected by the real identity service');
    await page.goto(base + '/m3');
    await page.getByRole('heading', { name: '登录校园资源平台' }).waitFor();
    assert.equal(new URL(page.url()).pathname, '/login');
    assert.equal(await page.locator('.identity-line').count(), 0);
  };
  const switchAccount = async (username, destination) => { await logout(); await login(username, destination); };
  const action = async (name, prepare) => {
    stage = `work-order action: ${name}`;
    await page.getByRole('button', { name, exact: true }).click();
    const form = page.locator('#m3-action-form');
    if (prepare) await prepare(form);
    await form.getByRole('button', { name: `确认${name}`, exact: true }).click();
    await form.waitFor({ state: 'hidden' });
  };
  const status = name => page.locator('.detail-heading').getByText(name, { exact: true }).waitFor({ timeout: 20_000 });
  try {
    stage = 'optional identity context compatibility';
    for (const fixture of [{ status: 404, body: {} }, { status: 200, body: { mode: 'future-provider' } }]) {
      // Only this optional public metadata endpoint is intercepted. Login/me/logout and M3 stay real.
      await page.route('**/api/d/api/v1/auth/context', route => route.fulfill({ status: fixture.status, contentType: 'application/json', body: JSON.stringify(fixture.body) }));
      const context = page.waitForResponse(response => new URL(response.url()).pathname === '/api/d/api/v1/auth/context');
      await loginPage();
      await context;
      assert.equal(await page.locator('.test-account-notice').count(), 0);
      assert.equal(await page.getByLabel('账号', { exact: true }).isEnabled(), true);
      assert.equal(await page.getByLabel('密码', { exact: true }).isEnabled(), true);
      await page.unroute('**/api/d/api/v1/auth/context');
    }
    checks.push('Optional context 404/unknown leaves the existing password form usable');
    await loginPage();
    await page.locator('.test-account-notice').waitFor();
    for (const [username] of expected) assert.ok((await page.locator('.test-account-notice').innerText()).includes(username));
    for (const value of secrets) assert.equal((await page.locator('body').innerText()).includes(value), false, 'Public page must not display a password');
    await screenshot('test-account-login-desktop');
    await page.setViewportSize({ width: 320, height: 900 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1), false);
    await screenshot('test-account-login-320');
    await page.setViewportSize({ width: 1440, height: 1000 });
    checks.push('Runtime test-account notice lists usernames without passwords and fits 320px');

    stage = 'wrong password remains a visible form error';
    await page.getByLabel('账号', { exact: true }).fill('m3-student');
    await page.getByLabel('密码', { exact: true }).fill('deliberately-invalid-browser-check');
    const denied = page.waitForResponse(response => new URL(response.url()).pathname === '/api/d/api/v1/auth/login' && response.request().method() === 'POST');
    await page.getByRole('button', { name: '登录', exact: true }).click();
    assert.equal((await denied).status(), 401);
    await page.locator('.feature-error[role="alert"]').waitFor();
    assert.ok((await page.locator('.feature-error[role="alert"]').innerText()).trim().length > 0);
    assert.equal(new URL(page.url()).pathname, '/login');
    assert.equal(await page.getByLabel('账号', { exact: true }).inputValue(), 'm3-student');
    assert.equal(await page.getByLabel('密码', { exact: true }).inputValue(), '');
    assert.equal(await localSession(), null);
    checks.push('Wrong password returns 401, preserves the form error/account, clears password and creates no session');

    for (const [username] of expected) {
      await login(username);
      if (username === 'm3-student') {
        await page.getByRole('heading', { name: '让每个问题，都有回应。' }).waitFor();
        await screenshot('test-account-workbench-desktop');
        await page.setViewportSize({ width: 320, height: 900 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1), false);
        await screenshot('test-account-workbench-320');
        await page.setViewportSize({ width: 1440, height: 1000 });
      }
      stage = `server-verified refresh: ${username}`;
      const before = await localSession();
      const restored = page.waitForResponse(response => new URL(response.url()).pathname === '/api/d/api/v1/auth/me');
      await page.reload();
      assert.equal((await restored).status(), 200);
      await page.locator('.identity-line').waitFor();
      await page.locator('.test-account-banner').waitFor();
      assert.equal((await localSession()).id, before.id);
      await logout();
    }
    checks.push('All four real password accounts receive expected M3 roles; refresh calls /me; logout revokes tokens and clears M3');

    if (process.env.M3_TEST_ROOM_ID) {
      stage = 'real work-order lifecycle';
      await login('m3-student', '/m3/new');
      await page.getByRole('heading', { name: '告诉我们，哪里需要修复？' }).waitFor();
      await page.locator('form.report-form').getByLabel('报修房间').selectOption(process.env.M3_TEST_ROOM_ID);
      await page.getByLabel('故障分类').selectOption('electrical');
      const title = `测试账号浏览器验收 ${Date.now()}`;
      await page.getByLabel('问题标题').fill(title);
      await page.getByLabel('详细描述').fill('合成验收记录：灯具闪烁，需要检查并验证密码测试账号的维修流程。');
      await page.getByRole('button', { name: '提交报修', exact: true }).click();
      await page.waitForURL('**/m3/work-orders/*');
      await page.getByRole('heading', { name: title }).waitFor();
      const detail = new URL(page.url()).pathname;
      await status('待派单');
      await switchAccount('m3-admin', detail);
      await action('派单', form => form.getByLabel('维修人员').selectOption(accounts.get('m3-worker1').user.id));
      await status('待开工');
      await switchAccount('m3-worker1', detail);
      await page.getByRole('button', { name: '开始维修', exact: true }).waitFor();
      await switchAccount('m3-admin', detail);
      await action('重新派单', form => form.getByLabel('维修人员').selectOption(accounts.get('m3-worker2').user.id));
      await status('待开工');
      await switchAccount('m3-worker2', detail);
      await action('开始维修');
      await status('维修中');
      await action('提交完工', form => form.getByLabel('完工说明', { exact: false }).fill('合成验收：已完成灯具检查和更换。'));
      await status('待验收');
      await switchAccount('m3-student', detail);
      await action('验收通过', form => form.getByLabel('验收说明', { exact: false }).fill('合成验收：确认恢复正常。'));
      await status('已完成');
      await action('提交评价', async form => {
        await form.getByRole('radio', { name: '5', exact: false }).check();
        await form.getByLabel('评价内容', { exact: false }).fill('合成验收：流程可追踪。');
      });
      await page.getByRole('heading', { name: '报修评价' }).waitFor();
      await logout();
      checks.push('Real M3 report → assign worker1 → reassign worker2 → M1 block ACK → complete → accept → release ACK → rating');
    }
    stage = 'M2 public entry and browser errors';
    await page.goto(base + '/m2');
    await page.getByRole('heading', { name: '整教室预约与审批' }).waitFor();
    assert.equal(errors.length, 0, 'No uncaught browser JavaScript errors');
    checks.push('M2 entry remains available; no uncaught browser JavaScript errors');
    console.log(JSON.stringify({ passed: true, checks, lifecycle: Boolean(process.env.M3_TEST_ROOM_ID) }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(`Temporary-account browser check failed at ${stage}: ${safeError(error)}`); process.exitCode = 1; });
