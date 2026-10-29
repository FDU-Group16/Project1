// Run against a real Vite preview. NODE_PATH may point to a bundled Playwright installation.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

const base = process.argv[2] || 'http://127.0.0.1:4187';
const localTime = date => new Intl.DateTimeFormat('sv-SE', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', hour12: false,
}).format(date).replace(' ', 'T');

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.WEB_BROWSER_CHANNEL ? { channel: process.env.WEB_BROWSER_CHANNEL } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, timezoneId: 'Asia/Shanghai' });
    const errors = [];
    const apiRequests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (new URL(request.url()).pathname.startsWith('/api/')) apiRequests.push(request.url());
    });
    const response = await page.goto(new URL('/m2/apply', base).href);
    assert.equal(response.status(), 200);
    assert.equal(await page.locator('main h1').innerText(), '准备整室申请');
    await page.reload();
    assert.equal(await page.locator('main h1').count(), 1);

    await page.getByRole('button', { name: '检查并预览' }).click();
    assert.equal(await page.locator('#m2-room').evaluate(el => el === document.activeElement), true);
    assert.match(await page.locator('[role="alert"]').allTextContents().then(items => items.join(' ')), /房间 ID/);

    await page.locator('#m2-room').fill('room-opaque-7');
    await page.locator('#m2-count').fill('12');
    await page.locator('#m2-start').fill(localTime(new Date(Date.now() + 48 * 60 * 60_000)));
    await page.locator('#m2-end').fill(localTime(new Date(Date.now() + 49 * 60 * 60_000)));
    await page.locator('#m2-purpose').fill('学术讨论');
    await page.getByRole('button', { name: '检查并预览' }).click();
    assert.match(await page.locator('.m2-preview').innerText(), /仅本地预览 · 未提交/);
    assert.match(await page.locator('.m2-preview').innerText(), /room-opaque-7/);
    assert.match(await page.locator('.m2-preview').innerText(), /Z/);
    assert.equal(apiRequests.length, 0, 'draft must not submit to an API');

    await page.setViewportSize({ width: 320, height: 700 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'no horizontal overflow at 320px');
    await page.getByRole('button', { name: '清空草稿' }).click();
    assert.equal(await page.locator('.m2-preview').count(), 0);
    assert.equal(await page.locator('#m2-room').inputValue(), '');
    await page.keyboard.press('Tab');
    assert.equal(await page.locator('#m2-count').evaluate(el => el === document.activeElement), true);
    assert.deepEqual(errors, []);
    console.log('M2 draft browser: direct route/reload, validation, preview, no API, reset, 320px and keyboard PASS');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
