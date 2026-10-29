// Run against a real Vite preview. NODE_PATH may point to a bundled Playwright installation.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

const base = process.argv[2] || 'http://127.0.0.1:4187';

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.WEB_BROWSER_CHANNEL ? { channel: process.env.WEB_BROWSER_CHANNEL } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 850 } });
    const errors = [];
    const apiRequests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/')) apiRequests.push(request.url()); });
    const response = await page.goto(new URL('/m2', base).href);
    assert.equal(response.status(), 200);
    assert.equal(await page.locator('main h1').count(), 1);
    assert.match(await page.locator('main').innerText(), /正式提交与审批服务仍在接入中/);
    assert.equal(await page.getByRole('link', { name: /准备申请草稿/ }).count(), 1);
    assert.equal(await page.locator('main button').count(), 0, 'no fake submission controls');
    await page.getByRole('link', { name: /准备申请草稿/ }).click();
    await page.waitForURL('**/m2/apply');
    assert.equal(new URL(page.url()).pathname, '/m2/apply');
    assert.equal(await page.locator('main h1').innerText(), '准备整室申请');
    await page.goto(new URL('/m2', base).href);
    await page.setViewportSize({ width: 320, height: 700 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'no horizontal overflow at 320px');
    await page.getByRole('link', { name: /准备申请草稿/ }).focus();
    assert.equal(await page.getByRole('link', { name: /准备申请草稿/ }).evaluate(el => el === document.activeElement), true);
    assert.deepEqual(apiRequests, []);
    assert.deepEqual(errors, []);
    console.log('M2 home browser: one heading, honest boundaries, draft navigation, 320px, focus and no API PASS');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
