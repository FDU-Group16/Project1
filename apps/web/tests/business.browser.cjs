/* Explicit local synthetic environment only; real UI, HTTP and PostgreSQL. */
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:5173';
const target = new URL(base);
assert(process.env.WEB_BUSINESS_TEST === '1', 'Set WEB_BUSINESS_TEST=1 for disposable synthetic data.');
assert(['127.0.0.1', 'localhost'].includes(target.hostname), 'Business mutations are local-only.');

(async () => {
  const browser = await chromium.launch({ channel: process.env.WEB_BROWSER_CHANNEL || 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.setDefaultTimeout(12_000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const roomName = `UI verification ${Date.now()}`;
  let roomPath;
  const day = new Date(Date.now() + 2 * 86400000).toLocaleDateString('en-CA', { timeZone: 'Asia/Shanghai' });
  async function identity(token, redirect) {
    await page.goto(`${base}/login?redirect=${encodeURIComponent(redirect)}`);
    await page.getByLabel('选择开发身份').selectOption(token);
    await page.getByRole('button', { name: /使用开发身份|切换开发身份/ }).click();
    await page.waitForURL(`${base}${redirect}`);
  }
  async function cancel() {
    await page.getByRole('button', { name: '取消预约', exact: true }).click();
    await page.getByRole('button', { name: '确认取消', exact: true }).click();
    await page.getByText('已取消', { exact: true }).waitFor();
  }
  try {
    await identity('dev-room-admin', '/d/rooms/new');
    await page.getByLabel('房间名称', { exact: true }).fill(roomName);
    await page.getByRole('button', { name: '登记房间', exact: true }).click();
    await page.waitForURL(/\/d\/rooms\/[0-9a-f-]+$/);
    roomPath = new URL(page.url()).pathname;
    await page.getByLabel('座位编号', { exact: true }).fill('UI-01');
    await page.getByLabel('配有插座', { exact: true }).check();
    await page.getByRole('button', { name: '登记座位', exact: true }).click();
    await page.getByRole('heading', { name: 'UI-01 号座位' }).waitFor();
    await page.locator('article').filter({ hasText: 'UI-01 号座位' }).getByRole('button', { name: '编辑', exact: true }).click();
    await page.getByLabel('座位编号', { exact: true }).fill('UI-02');
    await page.getByRole('button', { name: '保存修改', exact: true }).click();
    await page.getByRole('heading', { name: 'UI-02 号座位' }).waitFor();
    await page.getByRole('button', { name: '保存房间信息', exact: true }).click();
    await page.getByText('房间信息已保存。', { exact: true }).waitFor();
    console.log('PASS D-02 create/update room and seat through real API');

    await identity('dev-student-cs', '/m1');
    await page.getByLabel('预约日期', { exact: true }).fill(day);
    await page.getByLabel(/^开始时间/).selectOption('10');
    await page.getByLabel(/^结束时间/).selectOption('11');
    await page.getByLabel('仅看带插座的座位', { exact: true }).check();
    await page.getByRole('button', { name: '查询座位', exact: true }).click();
    await page.getByRole('button', { name: `${roomName} UI-02号座位，有插座`, exact: true }).click();
    await page.getByRole('button', { name: '确认预约', exact: true }).click();
    await page.waitForURL(/\/m1\/reservations\/[0-9a-f-]+$/);
    await page.getByRole('heading', { name: `${roomName} · UI-02 号座位` }).waitFor();
    const reservationPath = new URL(page.url()).pathname;
    await cancel();
    await page.getByLabel('日期', { exact: true }).fill(day);
    await page.getByLabel(/^开始/).selectOption('12');
    await page.getByLabel(/^结束/).selectOption('13');
    await page.getByRole('button', { name: '再次预约', exact: true }).click();
    await page.waitForURL(url => url.pathname.startsWith('/m1/reservations/') && url.pathname !== reservationPath);
    await cancel();
    console.log('PASS M1 search, reserve, cancel and rebook through real API');

    await identity('dev-student-ee', reservationPath);
    await page.getByRole('alert').waitFor();
    assert.equal(await page.getByRole('heading', { name: `${roomName} · UI-02 号座位` }).count(), 0);
    await page.goto(`${base}/d/rooms`);
    await page.waitForURL(`${base}/403`);
    console.log('PASS identity switch clears private details; student cannot manage rooms');

    await identity('dev-room-admin', '/m1/operations');
    await page.getByLabel('开始日期', { exact: true }).fill(day);
    await page.getByLabel('结束日期（包含当天）', { exact: true }).fill(day);
    await page.getByRole('button', { name: '查询统计', exact: true }).click();
    const roomSection = page.locator('section').filter({ has: page.getByRole('heading', { name: roomName, exact: true }) });
    await roomSection.getByRole('link', { name: '查看状态来源' }).click();
    await page.getByRole('heading', { name: 'M1 · CANCELLED' }).first().waitFor();
    await page.getByRole('button', { name: '获取当日编码' }).click();
    await page.locator('.check-in-code').waitFor();
    assert((await page.locator('.check-in-code').innerText()).length >= 6);
    console.log('PASS actual statistics, provenance and daily code display');

    await page.goto(base + roomPath);
    await page.locator('article').filter({ hasText: 'UI-02 号座位' }).getByRole('button', { name: '注销', exact: true }).click();
    await page.getByRole('button', { name: '确认注销', exact: true }).click();
    await page.locator('article').filter({ hasText: 'UI-02 号座位' }).getByText('配有插座 · 已注销', { exact: true }).waitFor();
    await page.getByRole('button', { name: '永久注销房间', exact: true }).click();
    await page.getByRole('button', { name: '确认永久注销', exact: true }).click();
    await page.getByText('房间及座位已注销，历史引用保留。', { exact: true }).waitFor();
    console.log('PASS D-02 permanent retirement with history retained');
    assert.deepEqual(errors, []);
    console.log('PASS all local business browser flows; JavaScript errors: 0. Identity/notification/audit providers remain substitutes.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
