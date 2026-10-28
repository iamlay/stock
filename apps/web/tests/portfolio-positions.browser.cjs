const { chromium } = require(
  process.env.STOCKLAB_PLAYWRIGHT_MODULE || "playwright",
);
const fs = require("fs"),
  assert = require("node:assert/strict");
const fixture = JSON.parse(
  fs.readFileSync(process.env.STOCKLAB_BROWSER_FIXTURE),
);
(async () => {
  const browser = await chromium.launch({
    executablePath:
      process.env.STOCKLAB_CHROME_PATH ||
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: true,
  });
  const ctx = await browser.newContext({
    viewport: { width: 1366, height: 1000 },
  });
  await ctx.addInitScript(
    (token) => localStorage.setItem("stocklab.token", token),
    fixture.token,
  );
  const errors = [],
    outside = [],
    writes = [];
  let delayed = false;
  let holdingsReads = 0,
    quoteOverride = null,
    failHoldings = false;
  await ctx.route("**/*", (r) => {
    const u = new URL(r.request().url());
    if (!["127.0.0.1", "localhost"].includes(u.hostname)) {
      outside.push(u.hostname);
      return r.abort();
    }
    return r.continue();
  });
  await ctx.route("**/api/v1/**", async (r) => {
    const req = r.request(),
      u = new URL(req.url());
    if (req.method() === "OPTIONS")
      return r.fulfill({
        status: 204,
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET,POST,PATCH,DELETE,OPTIONS",
          "access-control-allow-headers": "authorization,content-type",
        },
      });
    if (u.pathname.endsWith("/holdings")) {
      holdingsReads++;
      if (failHoldings)
        return r.fulfill({
          status: 503,
          contentType: "application/json",
          headers: { "access-control-allow-origin": "*" },
          body: JSON.stringify({ detail: "temporary failure" }),
        });
    }
    const response = await r.fetch({
      url: "http://127.0.0.1:8012" + u.pathname + u.search,
    });
    if (u.pathname.endsWith("/holdings") && quoteOverride && response.ok()) {
      const data = await response.json();
      for (const position of data.positions) {
        position.quote = {
          price: String(quoteOverride),
          at: new Date().toISOString(),
          time_label: "报价时间",
        };
        position.market_value = String(
          Number(position.quantity) * quoteOverride,
        );
        position.price_yield = String(
          (Number(position.forecast.annual_per_share) / quoteOverride) * 100,
        );
      }
      data.known_market_value = String(
        data.positions.reduce(
          (sum, item) => sum + Number(item.market_value),
          0,
        ),
      );
      return r.fulfill({
        response,
        headers: { ...response.headers(), "access-control-allow-origin": "*" },
        json: data,
      });
    }
    if (u.pathname.endsWith("/position-confirm"))
      writes.push(req.postDataJSON());
    if (
      u.pathname.endsWith("/stock-search") &&
      req.postDataJSON().query === "中国" &&
      !delayed
    ) {
      delayed = true;
      await new Promise((resolve) => setTimeout(resolve, 900));
    }
    try {
      return await r.fulfill({
        response,
        headers: { ...response.headers(), "access-control-allow-origin": "*" },
      });
    } catch {}
  });
  const p = await ctx.newPage();
  await p.clock.install();
  p.setDefaultTimeout(15000);
  p.on("pageerror", (e) => errors.push(e.message));
  p.on("dialog", (d) => d.accept());
  try {
    await p.goto("http://127.0.0.1:3100/portfolio");
    await p.getByText("请确认新版持仓数据范围", { exact: true }).waitFor();
    assert(
      await p
        .getByRole("button", { name: "＋ 添加持仓", exact: true })
        .isDisabled(),
    );
    await p
      .getByRole("checkbox")
      .filter({ has: p.locator("input") })
      .count();
    await p.getByRole("checkbox").first().check();
    await p
      .getByRole("button", { name: "确认并启用新版录入", exact: true })
      .click();
    await p.getByRole("button", { name: "＋ 添加持仓", exact: true }).click();
    await p.getByLabel("股票名称或代码", { exact: true }).fill("中国");
    await p.waitForTimeout(350);
    await p.getByLabel("股票名称或代码", { exact: true }).fill("招商");
    await p.getByRole("option", { name: /招商银行/ }).click();
    await p.waitForTimeout(1000);
    assert.equal(await p.getByRole("option", { name: /中国神华/ }).count(), 0);
    console.log("PASS consent and stale search cancellation, single click");
    await p.getByLabel("数量", { exact: true }).fill("500");
    await p.getByLabel("日期", { exact: true }).fill("2025-01-01");
    await p.getByLabel("成本口径", { exact: true }).selectOption("dividend");
    await p.getByLabel("成本或成交价", { exact: true }).fill("-2");
    assert.match(await p.getByTestId("input-total").innerText(), /-1000/);
    await p.getByRole("button", { name: "查看区别", exact: true }).click();
    await p.getByRole("button", { name: "知道了", exact: true }).click();
    assert.equal(
      await p.getByLabel("成本或成交价", { exact: true }).inputValue(),
      "-2",
    );
    await p.getByText("设置分红参考", { exact: true }).click();
    await p.getByLabel("分红参考", { exact: true }).selectOption("custom");
    await p.getByLabel("自定义分红", { exact: true }).fill("2.01");
    await p.getByLabel("分组", { exact: true }).fill("长期收息");
    await p.screenshot({
      path:
        (process.env.STOCKLAB_BROWSER_OUTPUT || "/tmp") +
        "/stock-v251r-form-desktop.png",
      fullPage: true,
    });
    await p.setViewportSize({ width: 390, height: 844 });
    assert.equal(
      await p.evaluate(() => document.documentElement.scrollWidth > innerWidth),
      false,
    );
    await p.screenshot({
      path:
        (process.env.STOCKLAB_BROWSER_OUTPUT || "/tmp") +
        "/stock-v251r-form-mobile.png",
      fullPage: true,
    });
    await p.getByRole("button", { name: "核对并预览", exact: true }).click();
    await p
      .getByRole("dialog")
      .filter({ hasText: "确认已有持仓快照" })
      .waitFor();
    assert.equal(writes.length, 0);
    await p.getByRole("button", { name: "返回修改", exact: true }).click();
    assert.equal(
      await p.getByLabel("成本或成交价", { exact: true }).inputValue(),
      "-2",
    );
    await p.getByRole("button", { name: "核对并预览", exact: true }).click();
    await p.getByRole("button", { name: "确认保存", exact: true }).click();
    await p
      .getByRole("link", { name: "查看招商银行持仓详情", exact: true })
      .waitFor();
    assert.equal(
      await p.getByRole("button", { name: "买入", exact: true }).count(),
      0,
    );
    assert.equal(
      await p
        .getByText("成本明细、分红依据与交易记录", { exact: true })
        .count(),
      0,
    );
    await p.screenshot({
      path:
        (process.env.STOCKLAB_BROWSER_OUTPUT || "/tmp") +
        "/stock-holdings-list-mobile.png",
      fullPage: true,
    });
    assert.equal(
      await p.evaluate(() => document.documentElement.scrollWidth > innerWidth),
      false,
    );
    await p
      .getByRole("link", { name: "查看招商银行持仓详情", exact: true })
      .click();
    await p.waitForURL("**/portfolio/600036");
    await p.reload();
    await p.getByTestId("position-detail").waitFor();
    await p.getByRole("button", { name: "卖出", exact: true }).waitFor();
    assert.equal(writes.length, 1);
    assert.equal(
      await p.getByTestId("position-annual-reference").innerText(),
      "¥1,005.00",
    );
    console.log(
      "PASS signed cost, optional custom forecast, preview no write and save",
    );
    await p.getByRole("button", { name: "买入", exact: true }).click();
    await p.getByLabel("数量", { exact: true }).fill("100");
    await p.getByLabel("日期", { exact: true }).fill("2025-01-01");
    await p.getByLabel("成本或成交价", { exact: true }).fill("5");
    await p.getByRole("button", { name: "核对并预览", exact: true }).click();
    await p.getByRole("alert").filter({ hasText: "日终快照" }).waitFor();
    assert.equal(writes.length, 1);
    await p.getByLabel("日期", { exact: true }).fill("2025-01-02");
    await p.getByRole("button", { name: "核对并预览", exact: true }).click();
    await p.getByRole("button", { name: "确认保存", exact: true }).click();
    await p.getByRole("button", { name: "卖出", exact: true }).waitFor();
    await p.getByText(/含未知费用/).waitFor();
    console.log("PASS date overlap rejection, buy and unknown fees");
    await p.getByRole("button", { name: "卖出", exact: true }).click();
    await p.getByLabel("日期", { exact: true }).fill("2025-01-03");
    await p.getByLabel("数量", { exact: true }).fill("700");
    await p.getByLabel("成本或成交价", { exact: true }).fill("8");
    await p.getByLabel("费用", { exact: true }).fill("0");
    await p.getByRole("button", { name: "核对并预览", exact: true }).click();
    await p.getByRole("alert").filter({ hasText: "历史超卖" }).waitFor();
    await p.getByLabel("数量", { exact: true }).fill("100");
    await p.getByRole("button", { name: "核对并预览", exact: true }).click();
    await p.getByRole("button", { name: "确认保存", exact: true }).click();
    await p.getByRole("button", { name: "卖出", exact: true }).waitFor();
    console.log("PASS oversell rejection and sell");
    await p.getByText("成本明细、分红依据与交易记录", { exact: true }).click();
    await p.getByRole("button", { name: "更正", exact: true }).nth(1).click();
    await p.getByLabel("费用", { exact: true }).fill("5");
    await p.getByLabel("备注", { exact: true }).fill("补充交易费用");
    await p.getByRole("button", { name: "核对并预览", exact: true }).click();
    await p.getByRole("button", { name: "确认保存", exact: true }).click();
    await p.getByRole("button", { name: "卖出", exact: true }).waitFor();
    assert.equal(await p.getByText(/含未知费用/).count(), 0);
    console.log("PASS correction recalculates unknown fee");
    await p
      .getByRole("button", { name: "分组与分红参考", exact: true })
      .click();
    await p.getByLabel("分红参考", { exact: true }).selectOption("36");
    await p.getByLabel("分组", { exact: true }).fill("观察仓");
    await p.getByRole("button", { name: "核对并预览", exact: true }).click();
    await p.getByRole("button", { name: "确认保存", exact: true }).click();
    await p
      .getByTestId("position-annual-reference")
      .filter({ hasText: "¥335.00" })
      .waitFor();
    await p.getByText(/已收录历史参考 · 过去36个月/).waitFor();
    await p
      .getByTestId("position-price-yield")
      .filter({ hasText: "1.36%" })
      .waitFor();
    console.log(
      "PASS historical reference from recorded dividends, fixed 3-year divisor and quote fallback",
    );
    await p.getByRole("button", { name: "修正当前持仓", exact: true }).click();
    await p.getByLabel("数量", { exact: true }).fill("1000");
    await p.getByLabel("日期", { exact: true }).fill("2025-01-04");
    await p.getByLabel("成本口径", { exact: true }).selectOption("dividend");
    await p.getByLabel("成本或成交价", { exact: true }).fill("-2");
    await p.getByLabel("备注", { exact: true }).fill("核对当前持仓");
    await p.getByLabel("核对依据", { exact: true }).fill("脱敏持仓数字");
    await p.getByRole("button", { name: "核对并预览", exact: true }).click();
    await p.getByRole("button", { name: "确认保存", exact: true }).click();
    await p.getByRole("button", { name: "卖出", exact: true }).waitFor();
    console.log("PASS explicit current holding rebase");
    await p
      .getByTestId("position-market-value")
      .filter({ hasText: "¥49,380.00" })
      .waitFor();
    quoteOverride = 67;
    await p.clock.fastForward(300001);
    await p
      .getByTestId("position-market-value")
      .filter({ hasText: "¥67,000.00" })
      .waitFor();
    await p
      .getByTestId("position-price-yield")
      .filter({ hasText: "1.00%" })
      .waitFor();
    // Failed background fetch retains the last known holdings, then recovers.
    failHoldings = true;
    await p.clock.fastForward(300001);
    await p.getByText(/持仓刷新失败，已保留上次数据/).waitFor();
    assert.equal(
      await p
        .getByTestId("position-market-value")
        .filter({ hasText: "¥67,000.00" })
        .count(),
      1,
    );
    failHoldings = false;
    // Hidden tabs skip requests; returning after the interval fetches immediately.
    await p.evaluate(() => {
      window.testHidden = true;
      Object.defineProperty(document, "visibilityState", {
        configurable: true,
        get: () => (window.testHidden ? "hidden" : "visible"),
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    const hiddenReads = holdingsReads;
    quoteOverride = 100;
    await p.clock.fastForward(300001);
    assert.equal(holdingsReads, hiddenReads);
    await p.evaluate(() => {
      window.testHidden = false;
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await p
      .getByTestId("position-market-value")
      .filter({ hasText: "¥100,000.00" })
      .waitFor();
    await p
      .getByTestId("position-price-yield")
      .filter({ hasText: "0.67%" })
      .waitFor();
    // Editing is never interrupted by polling and keeps unsaved values intact.
    await p.getByRole("button", { name: "买入", exact: true }).click();
    await p.getByLabel("数量", { exact: true }).fill("123");
    const editingReads = holdingsReads;
    await p.clock.fastForward(300001);
    assert.equal(holdingsReads, editingReads);
    assert.equal(
      await p.getByLabel("数量", { exact: true }).inputValue(),
      "123",
    );
    await p.getByRole("button", { name: "返回持仓", exact: true }).click();
    await p
      .getByTestId("position-market-value")
      .filter({ hasText: "¥100,000.00" })
      .waitFor();
    console.log(
      "PASS 5-minute quotes/market value/yield refresh, retry, visibility and draft protection",
    );

    await p.screenshot({
      path:
        (process.env.STOCKLAB_BROWSER_OUTPUT || "/tmp") +
        "/stock-v251r-holdings-mobile.png",
      fullPage: true,
    });
    await p.setViewportSize({ width: 1366, height: 1000 });
    await p.screenshot({
      path:
        (process.env.STOCKLAB_BROWSER_OUTPUT || "/tmp") +
        "/stock-v251r-holdings-desktop.png",
      fullPage: true,
    });
    await p.getByRole("link", { name: "← 返回我的持仓", exact: true }).click();
    await p
      .getByRole("link", { name: "查看招商银行持仓详情", exact: true })
      .waitFor();
    await p.screenshot({
      path:
        (process.env.STOCKLAB_BROWSER_OUTPUT || "/tmp") +
        "/stock-holdings-list-desktop.png",
      fullPage: true,
    });
    await p
      .getByText("账本设置 · 名称、导出、归档与删除", { exact: true })
      .click();
    const dl = p.waitForEvent("download");
    await p.getByRole("button", { name: "免费导出 JSON", exact: true }).click();
    const exported = JSON.parse(fs.readFileSync(await (await dl).path()));
    assert.equal(exported.schema_version, "portfolio-positions-export-v3");
    assert.equal(exported.ledgers[0].entries.length, 6);
    assert(exported.ledgers[0].entries.every((e) => e.details));
    console.log("PASS free export includes all immutable metadata");
    await p.getByRole("button", { name: "归档账本", exact: true }).click();
    await p
      .getByText("账本已归档，可在下方设置中恢复。", { exact: true })
      .waitFor();
    assert(
      await p
        .getByRole("button", { name: "＋ 添加持仓", exact: true })
        .isDisabled(),
    );
    console.log("PASS account version refresh and archive");
    await p.goto("http://127.0.0.1:3100/portfolio/601088");
    await p.getByText(/当前账本中没有这只股票的持仓/).waitFor();
    assert.equal(await p.getByTestId("position-detail").count(), 0);
    await p.goto("http://127.0.0.1:3100/portfolio/600036");
    await p.getByTestId("position-detail").waitFor();
    assert(
      await p.getByRole("button", { name: "买入", exact: true }).isDisabled(),
    );
    assert.deepEqual(errors, []);
    assert.deepEqual(outside, []);
    assert(writes.every((w) => typeof w.entry.quantity === "string"));
    await p.evaluate(() => {
      localStorage.removeItem("stocklab.token");
      window.dispatchEvent(
        new StorageEvent("storage", { key: "stocklab.token" }),
      );
    });
    await p
      .getByText("请登录并验证邮箱后管理自己的账本。", { exact: true })
      .waitFor();
    assert.equal(await p.getByText("招商银行", { exact: true }).count(), 0);
    const loggedOutReads = holdingsReads;
    await p.clock.fastForward(600001);
    assert.equal(holdingsReads, loggedOutReads);
    assert.match(
      await p.getByRole("link", { name: "登录后继续" }).getAttribute("href"),
      /next=%2Fportfolio%2F600036/,
    );
    console.log(
      "PASS list/detail navigation, archived/read-only, unknown stock and private deep-link logout",
    );
  } catch (e) {
    await p.screenshot({
      path:
        (process.env.STOCKLAB_BROWSER_OUTPUT || "/tmp") +
        "/stock-v251r-error.png",
      fullPage: true,
    });
    throw e;
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
