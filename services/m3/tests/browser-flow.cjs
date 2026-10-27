// Real Vue -> M3 HTTP behavior. Run only against an explicit local development database.
// D and M1 are the marked development providers; this does not verify real seat state.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const base = process.argv[2] || 'http://127.0.0.1:5173';
const screenshots = process.env.M3_SCREENSHOT_DIR || '/tmp/pj-m3-browser';

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, timezoneId: 'Asia/Shanghai' });
    page.setDefaultTimeout(12000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const checks = [];
    const status = value => page.locator('.m3-order-heading .m3-status--' + value.toLowerCase()).waitFor();
    const identity = async value => {
      await page.locator('#m3-identity').selectOption(value);
      await page.locator('.m3-current-actor').waitFor();
    };
    const shot = async name => {
      await fs.mkdir(screenshots, { recursive: true });
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: path.join(screenshots, name + '.png'), fullPage: page.viewportSize().width > 600 });
    };
    await page.goto(base + '/m3');
    await page.locator('#m3-identity').waitFor();
    assert.match(await page.locator('main').innerText(), /模拟依赖/);
    assert.equal(await page.locator('main h1').count(), 1);
    await identity('demo-student');
    await page.locator('#m3-query').waitFor();
    await page.getByRole('link', { name: '上报故障', exact: true }).first().click();
    await page.locator('#m3-room').selectOption('room-101');
    await page.locator('#m3-category').selectOption('electrical');
    const title = '浏览器验收：靠窗灯具闪烁 ' + Date.now();
    await page.locator('#m3-title').fill(title);
    await page.locator('#m3-description').fill('合成验收数据：靠窗第一排灯具持续闪烁，请检查线路。');
    await shot('new-desktop');
    await page.getByRole('button', { name: '提交报修', exact: true }).click();
    await status('REPORTED');
    const orderUrl = page.url();
    assert.match(await page.locator('.m3-order-headline h2').innerText(), /靠窗灯具闪烁/);
    checks.push('真实 HTTP 上报、详情与开发依赖标识');

    await identity('demo-student-2');
    await page.getByText('未找到这张工单，或当前身份无权查看。', { exact: true }).waitFor();
    assert.equal(await page.locator('.m3-order-heading').count(), 0);
    await identity('demo-dispatcher');
    await page.locator('#m3-assignee').selectOption('technician-1');
    await page.getByRole('button', { name: '确认派单', exact: true }).click();
    await status('ASSIGNED');
    await identity('demo-technician-2');
    await page.getByText('未找到这张工单，或当前身份无权查看。', { exact: true }).waitFor();
    await identity('demo-technician');
    await page.getByRole('button', { name: '申请开始维修', exact: true }).click();
    await status('IN_PROGRESS');
    checks.push('身份切换清理、他人工单不可见、派单与维修下架回执');

    await page.locator('#m3-resolution').fill('第一次修复：更换灯管。');
    await page.getByRole('button', { name: '提交完工', exact: true }).click();
    await status('PENDING_ACCEPTANCE');
    await identity('demo-student');
    await page.locator('#m3-reject-reason').fill('验收仍闪烁，需要进一步检查线路。');
    await page.getByRole('button', { name: '退回维修', exact: true }).click();
    await status('IN_PROGRESS');
    await identity('demo-technician');
    await page.locator('#m3-resolution').fill('第二次修复：重新连接线路，连续测试正常。');
    await page.getByRole('button', { name: '提交完工', exact: true }).click();
    await status('PENDING_ACCEPTANCE');
    await identity('demo-student');
    await page.getByRole('button', { name: '确认验收通过', exact: true }).click();
    await status('CLOSED');
    await page.locator('#m3-rating').selectOption('4');
    await page.locator('#m3-comment').fill('问题已解决，过程可追踪。');
    await page.getByRole('button', { name: '提交评价', exact: true }).click();
    await page.getByRole('heading', { name: '报修人评价', exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: '提交评价', exact: true }).count(), 0);
    assert.match(await page.locator('.m3-history').innerText(), /验收仍闪烁/);
    await shot('closed-desktop');
    checks.push('完工、验收拒绝返工、通过、恢复回执与一次评价');

    for (const width of [1440, 768, 375, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1), false, '详情横向溢出 ' + width);
      if (width === 375) await shot('closed-mobile');
    }
    await page.getByRole('link', { name: '返回工单中心', exact: true }).click();
    await page.locator('#m3-query').fill(title);
    await page.locator('.m3-order-link').waitFor();
    assert.equal(await page.locator('.m3-order-link').count(), 1);
    await page.locator('#m3-filter').selectOption('CANCELLED');
    await page.getByRole('heading', { name: '没有符合条件的工单', exact: true }).waitFor();
    await page.getByRole('button', { name: '清除筛选', exact: true }).click();
    await shot('list-mobile');
    checks.push('320–1440px 详情响应式、列表搜索与空筛选');

    await page.getByRole('link', { name: '上报故障', exact: true }).first().click();
    await page.locator('#m3-room').selectOption('room-102');
    await page.locator('#m3-title').fill('取消流程 ' + Date.now());
    await page.locator('#m3-description').fill('合成数据，仅测试取消。');
    await page.getByRole('button', { name: '提交报修', exact: true }).click();
    await status('REPORTED');
    await page.locator('summary').filter({ hasText: '不再需要这次报修' }).click();
    await page.locator('#m3-cancel-reason').fill('重复报修，保留其他工单。');
    await page.getByRole('button', { name: '确认取消工单', exact: true }).click();
    await status('CANCELLED');
    checks.push('未开始维修的工单取消');

    // Inject only a network failure, never fabricated business success.
    await page.route('**/api/m3/v1/work-orders', route => route.abort('failed'));
    await page.getByRole('link', { name: '返回工单中心', exact: true }).click();
    await page.getByRole('button', { name: '重新加载', exact: true }).waitFor();
    await page.unroute('**/api/m3/v1/work-orders');
    await page.getByRole('button', { name: '重新加载', exact: true }).click();
    await page.locator('.m3-order-link').first().waitFor();
    await page.goto(orderUrl);
    await page.getByRole('heading', { name: '选择一个联调身份', exact: true }).waitFor();
    assert.equal(await page.locator('.m3-order-heading').count(), 0, '刷新不能沿用内存身份');
    await identity('demo-student');
    await status('CLOSED');
    checks.push('网络失败与重试、深链接刷新不持久保存身份');
    assert.deepEqual(errors, [], '浏览器 JavaScript 错误');
    console.log(JSON.stringify({ checks, orderUrl, screenshots, errors }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
