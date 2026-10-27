// Real browser + shared development login + real M3 API.
// M1/D-02 may be real services; set M3_TEST_ROOM_ID to an accessible public room.
// The default room-101 is only for the explicitly configured standalone development directory.
// npm dependencies stay unchanged; use NODE_PATH for the available Playwright.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const base = process.argv[2] || 'http://127.0.0.1:5173';
const shots = process.env.M3_SCREENSHOT_DIR;
const roomId = process.env.M3_TEST_ROOM_ID || 'room-101';

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1050 }, timezoneId: 'Asia/Shanghai' });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const identity = async (token, returnTo) => {
    const current = new URL(page.url());
    const destination = returnTo || (current.pathname === '/login' ? current.searchParams.get('redirect') || '/m3' : current.pathname + current.search);
    await page.goto(base + '/login?redirect=' + encodeURIComponent(destination));
    await page.getByRole('heading', { name: '登录校园资源平台' }).waitFor();
    await page.getByLabel('选择开发身份').selectOption(token);
    await page.getByRole('button', { name: /^(使用|切换)开发身份$/ }).click();
    const target = new URL(destination, base);
    await page.waitForURL(url => url.pathname === target.pathname && url.search === target.search);
    await page.locator('.identity-line').waitFor();
    assert.equal(await page.getByLabel('体验身份').count(), 0, 'M3 does not create a second identity selector');
  };
  const action = async (name, prepare) => {
    await page.getByRole('button', { name, exact: true }).click();
    const form = page.locator('#m3-action-form');
    if (prepare) await prepare(form);
    await form.getByRole('button', { name: `确认${name}`, exact: true }).click();
    await form.waitFor({ state: 'hidden' });
  };
  const status = async name => page.locator('.detail-heading').getByText(name, { exact: true }).waitFor({ timeout: 15000 });
  const shot = async name => {
    if (shots) { await fs.mkdir(shots, { recursive: true }); await page.screenshot({ path: path.join(shots, name + '.png'), fullPage: true }); }
  };
  try {
    await page.goto(base + '/m3');
    await page.getByRole('heading', { name: '登录校园资源平台' }).waitFor();
    assert.equal(new URL(page.url()).pathname, '/login', 'M3 requires the shared login');
    await identity('dev-student-cs', '/m3');
    await page.getByRole('heading', { name: '让每个问题，都有回应。' }).waitFor();
    await page.locator('.development-banner').filter({ hasText: '开发联调 · 合成身份' }).waitFor();
    await page.getByRole('status').filter({ hasText: '使用公共登录提供的合成开发身份。' }).waitFor();
    await shot('workbench-desktop');
    await page.locator('.module-nav').getByRole('link', { name: '发起报修' }).click();
    await page.getByRole('heading', { name: '告诉我们，哪里需要修复？' }).waitFor();
    await page.locator('form.report-form').getByLabel('报修房间').selectOption(roomId);
    await page.getByLabel('故障分类').selectOption('electrical');
    const title = `浏览器验收：照明维修 ${Date.now()}`;
    await page.getByLabel('问题标题').fill(title);
    await page.getByLabel('详细描述').fill('第一排靠窗照明灯闪烁，请检查线路与灯具。此记录为合成验收数据。');
    await shot('report-desktop');
    await page.getByRole('button', { name: '提交报修', exact: true }).click();
    await page.waitForURL('**/m3/work-orders/*');
    await page.getByRole('heading', { name: title }).waitFor();
    const detailUrl = page.url();
    await status('待派单');
    await identity('dev-repair-admin');
    await action('派单', form => form.getByLabel('维修人员').selectOption('dev-technician-1'));
    await status('待开工');
    await identity('dev-technician-1');
    await action('开始维修');
    await status('维修中');
    await action('提交完工', form => form.getByLabel('完工说明', { exact: false }).fill('已更换灯具并检查线路。'));
    await status('待验收');
    await identity('dev-student-cs');
    await action('退回返工', form => form.getByLabel('返工原因', { exact: false }).fill('邻近灯具仍有闪烁，请再次检查。'));
    await status('维修中');
    await identity('dev-technician-1');
    await action('提交完工', form => form.getByLabel('完工说明', { exact: false }).fill('已排查邻近灯具并连续测试。'));
    await status('待验收');
    await identity('dev-repair-admin');
    await action('验收通过', form => form.getByLabel('验收说明', { exact: false }).fill('代报修人现场核验，照明恢复正常。'));
    await status('已完成');
    await identity('dev-student-cs');
    await action('提交评价', async form => {
      await form.getByRole('radio', { name: '5', exact: false }).check();
      await form.getByLabel('评价内容', { exact: false }).fill('维修后照明正常，进度可追踪。');
    });
    await page.getByRole('heading', { name: '报修评价' }).waitFor();
    assert.equal(await page.getByRole('button', { name: '提交评价', exact: true }).count(), 0);
    await shot('completed-desktop');
    await page.reload();
    await page.getByRole('heading', { name: '报修评价' }).waitFor();
    await identity('dev-student-ee');
    await page.getByText(/工单不存在.*无权查看/).waitFor();
    await page.getByRole('heading', { name: '暂时无法查看工单' }).waitFor();
    assert.equal(await page.getByRole('heading', { name: title }).count(), 0, 'Other reporter cannot read private order');
    await identity('dev-student-cs');
    await page.getByRole('heading', { name: title }).waitFor();
    for (const width of [1440, 768, 375, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const route of ['/m3', '/m3/new', new URL(detailUrl).pathname, '/m1', '/m1/preview', '/m2']) {
        await page.goto(base + route);
        await page.locator('main h1').waitFor();
        if (route.startsWith('/m3')) await page.locator('.identity-line').waitFor();
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1), false, `Horizontal overflow at ${width} ${route}`);
      }
      if (width === 375) { await page.goto(detailUrl); await page.getByRole('heading', { name: title }).waitFor(); await shot('completed-mobile'); }
    }
    await page.goto(base + '/m3/new');
    await page.getByLabel('报修房间').waitFor();
    await page.keyboard.press('Tab');
    assert.ok(await page.locator(':focus').count(), 'Keyboard focus exists');
    await page.goto(base + '/login?redirect=%2Fm3');
    await page.getByRole('button', { name: '退出登录', exact: true }).click();
    await page.getByRole('button', { name: '使用开发身份', exact: true }).waitFor();
    await page.goto(base + '/m3');
    await page.getByRole('heading', { name: '登录校园资源平台' }).waitFor();
    assert.equal(new URL(page.url()).pathname, '/login', 'Shared logout prevents M3 access');
    assert.equal(await page.locator('.identity-line').count(), 0, 'Old M3 identity is cleared after logout');
    assert.deepEqual(errors, [], 'No browser JS errors');
    console.log(JSON.stringify({ passed: true, checks: ['shared login/return destination/logout', 'no module identity selector', 'real report/assign/start/complete', 'rejection/rework', 'admin acceptance reason', 'HTTP ACK and close', 'one-time rating/reload', 'identity isolation', '1440/768/375/320 layouts', 'M1/M2 routes', 'keyboard focus'], detailUrl }, null, 2));
  } catch (e) {
    await shot('failure');
    console.error(await page.locator('main').innerText().catch(() => ''));
    throw e;
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
