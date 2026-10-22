// Run against a real Vite preview or deployed site. Requires Playwright and Chrome.
// NODE_PATH may point to an existing Playwright installation; no application dependency is added.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const base = process.argv[2] || 'http://127.0.0.1:4187';
const screenshotDir = process.env.WEB_SCREENSHOT_DIR;
const checks = [];

(async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.WEB_BROWSER_CHANNEL || 'chrome' });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, timezoneId: 'Asia/Shanghai' });
    const errors = [];
    const businessRequests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (/\/(api|internal)\//.test(new URL(request.url()).pathname)) businessRequests.push(request.url());
    });
    const visit = async target => {
      const response = await page.goto(new URL(target, base).href);
      assert.equal(response.status(), 200, 'SPA document: ' + target);
      await page.locator('main h1').waitFor();
      assert.equal(await page.locator('main h1').count(), 1, 'Single main heading: ' + target);
    };
    const shot = async name => {
      if (!screenshotDir) return;
      await fs.mkdir(screenshotDir, { recursive: true });
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: path.join(screenshotDir, name + '.png'), fullPage: true });
    };

    await visit('/');
    await shot('home-desktop');
    await page.keyboard.press('Tab');
    assert.match(await page.locator(':focus').textContent(), /跳/);
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#main-content').evaluate(el => el === document.activeElement), true);
    checks.push('Homepage and keyboard skip link');

    for (const target of ['/m1', '/m1/reservations', '/m1/reservations/unavailable', '/login', '/m2', '/m3', '/403', '/missing-page']) {
      await visit(target);
      await page.reload();
      await page.locator('main h1').waitFor();
      assert.equal(await page.locator('main h1').count(), 1);
    }
    checks.push('All entry routes, direct access, refresh and error pages');

    for (const target of ['/m1', '/m1/reservations', '/m1/reservations/unavailable']) {
      await visit(target);
      assert.equal(await page.getByText('教学楼 A201', { exact: true }).count(), 0, 'Normal routes never show fixture rooms');
      assert.match(await page.locator('main').innerText(), /未接入|接入中|尚未|暂未/);
    }
    await visit('/login');
    assert.equal(await page.locator('input[type="password"]').count(), 0);
    for (const target of ['https://example.com', '//example.com', '/%2f%2fexample.com', '/login', '/unknown-target']) {
      await visit('/login?redirect=' + encodeURIComponent(target));
      const hrefs = await page.locator('main a[href]').evaluateAll(nodes => nodes.map(node => node.href));
      for (const href of hrefs) assert.equal(new URL(href).origin, new URL(base).origin, 'Unsafe login destination');
    }
    checks.push('No fabricated identity/data and safe login destinations');

    await visit('/login?redirect=' + encodeURIComponent('/m1/preview/reservations?tab=history'));
    await page.getByRole('link', { name: '返回刚才的页面' }).click();
    await page.waitForURL('**/m1/preview/reservations?tab=history');
    assert.equal(await page.getByRole('button', { name: '历史预约', exact: true }).getAttribute('aria-pressed'), 'true');

    await visit('/m1/preview?date=2099-01-15&start=18&end=20');
    await page.locator('.m1-room').first().waitFor();
    assert.equal(await page.locator('.m1-room').count(), 3);
    await page.getByRole('checkbox', { name: '仅看带插座的座位' }).check();
    await page.waitForURL(url => url.searchParams.get('socket') === '1');
    assert.equal(await page.locator('.m1-room').count(), 0, 'Changing filters clears old results');
    await page.getByRole('button', { name: '筛选示例', exact: true }).click();
    await page.locator('.m1-room').first().waitFor();
    assert.equal(await page.locator('.m1-room').count(), 2);
    await page.getByRole('button', { name: '查看座位', exact: true }).first().click();
    await page.getByRole('button', { name: /^A-01，/ }).click();
    assert.equal(await page.getByRole('button', { name: /^A-01，/ }).getAttribute('aria-pressed'), 'true');
    assert.equal(await page.locator('.m1-seat').filter({ hasText: '无插座' }).count(), 0);
    assert.ok(await page.locator('.m1-seat:disabled').count() > 0, 'Unavailable examples cannot be selected');
    await shot('m1-desktop');
    await page.getByRole('button', { name: '收起', exact: true }).click();
    assert.match(await page.locator(':focus').innerText(), /查看座位/);
    await page.getByRole('button', { name: '查看座位', exact: true }).first().click();
    await page.locator('#m1-end').selectOption('17');
    await page.getByText('结束时间需要晚于开始时间。', { exact: true }).waitFor();
    assert.equal(await page.locator('#m1-seat-detail').count(), 0, 'Invalid new period clears selection');
    assert.equal(await page.locator('.m1-room').count(), 0);
    await page.locator('#m1-end').selectOption('23');
    await page.getByText('单次时段最多 4 小时，请缩短时段。', { exact: true }).waitFor();
    await page.locator('#m1-end').selectOption('20');
    await page.getByRole('button', { name: '筛选示例', exact: true }).click();
    await page.locator('.m1-room').first().waitFor();
    await page.reload();
    await page.locator('.m1-room').first().waitFor();
    assert.equal(await page.locator('#m1-date').inputValue(), '2099-01-15');
    assert.equal(await page.getByRole('checkbox', { name: '仅看带插座的座位' }).isChecked(), true);
    assert.equal(await page.locator('.m1-room').count(), 2);
    await page.goBack();
    await page.getByText('按新的条件查看示例', { exact: true }).waitFor();
    assert.equal(await page.locator('.m1-room').count(), 0);
    await page.goForward();
    await page.locator('.m1-room').first().waitFor();
    assert.equal(await page.locator('.m1-room').count(), 2);
    await page.locator('#m1-start').selectOption('0');
    await page.locator('#m1-end').selectOption('1');
    await page.getByRole('button', { name: '筛选示例', exact: true }).click();
    await page.getByText('没有匹配的房间示例', { exact: true }).waitFor();
    await visit('/m1/preview?date=not-a-date&start=18&end=20');
    await page.getByText('请选择有效的预约日期。', { exact: true }).waitFor();
    assert.equal(await page.locator('.m1-room').count(), 0);
    checks.push('M1 socket/period/date filters, empty results, seat states, focus and query history');

    await visit('/m1/preview/reservations');
    await page.getByRole('link', { name: '查看教学楼 A201 A-08预约示例详情' }).click();
    await page.waitForURL('**/m1/preview/reservations/example-current');
    await page.getByRole('heading', { name: '教学楼 A201 · A-08' }).waitFor();
    await page.reload();
    await page.getByRole('heading', { name: '教学楼 A201 · A-08' }).waitFor();
    await shot('reservation-detail');
    await page.getByRole('link', { name: '返回预约示例', exact: true }).click();
    await page.getByRole('button', { name: '历史预约', exact: true }).click();
    await page.getByRole('link', { name: '查看阅览室 C101 C-02预约示例详情' }).click();
    await page.getByRole('heading', { name: '阅览室 C101 · C-02' }).waitFor();
    await page.getByRole('link', { name: '返回预约示例', exact: true }).click();
    assert.equal(await page.getByRole('button', { name: '历史预约', exact: true }).getAttribute('aria-pressed'), 'true');
    await visit('/m1/preview/reservations/unknown-example');
    await page.getByRole('heading', { name: '未找到此预约示例' }).waitFor();
    await page.getByRole('link', { name: '返回正式入口' }).click();
    await page.getByRole('heading', { name: '座位查询服务尚未接入' }).waitFor();
    assert.equal(await page.locator('.m1-room').count(), 0);
    await page.getByRole('button', { name: '查询座位', exact: true }).click();
    await page.getByText('查询条件已检查；座位服务尚未接入，暂时无法获取实时结果。', { exact: true }).waitFor();
    checks.push('Reservation current/history/detail/missing examples and return to normal service state');

    await page.setViewportSize({ width: 375, height: 1000 });
    await visit('/m1/preview');
    const menu = page.locator('button[aria-controls="section-navigation"]');
    await menu.click();
    assert.equal(await menu.getAttribute('aria-expanded'), 'true');
    await page.keyboard.press('Escape');
    assert.equal(await menu.getAttribute('aria-expanded'), 'false');
    assert.equal(await menu.evaluate(el => el === document.activeElement), true);
    await menu.click();
    await page.locator('#section-navigation').getByRole('link', { name: '我的预约' }).click();
    await page.waitForURL('**/m1/preview/reservations');
    assert.equal(await menu.getAttribute('aria-expanded'), 'false');
    checks.push('Mobile menu navigation, Escape and focus');

    for (const width of [1440, 768, 430, 375, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const target of ['/', '/m1', '/m1/preview', '/m1/preview/reservations', '/m1/preview/reservations/example-current', '/login', '/m2', '/m3', '/missing-page']) {
        await visit(target);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
        assert.equal(overflow, false, 'Horizontal overflow: ' + width + ' ' + target);
        if (width <= 430 && target === '/m1') {
          assert.ok(await page.locator('#m1-date').evaluate(el => parseFloat(getComputedStyle(el).fontSize) >= 16), 'Mobile inputs avoid focus zoom');
        }
      }
      if (width === 375) {
        await visit('/m1/preview');
        await shot('m1-mobile');
      }
    }
    checks.push('1440/768/430/375/320px shared and module layouts');

    assert.deepEqual(errors, [], 'Browser JavaScript errors');
    assert.deepEqual(businessRequests, [], 'Unavailable business APIs must not be called');
    console.log(JSON.stringify({ base, checks, errors, businessRequests }, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
