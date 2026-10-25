// Browser acceptance for the self-contained official page. No live services are called.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
assert.ok(
    fs.existsSync(path.join(root, "index.html")),
    "official page must exist",
);
const { chromium } = await import(
    process.env.PLAYWRIGHT_MODULE || "playwright-core"
);
const executablePath =
    process.env.CHROME_PATH ||
    [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/chromium",
        "/usr/bin/google-chrome",
    ].find((p) => fs.existsSync(p));
assert.ok(executablePath, "Set CHROME_PATH to a Chromium executable");
const browser = await chromium.launch({ executablePath, headless: true });
const errors = [];
try {
    const context = await browser.newContext({
        viewport: { width: 1440, height: 1000 },
    });
    const page = await context.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (msg) => {
        if (msg.type() === "error") errors.push(msg.text());
    });
    const remote = [];
    page.on("request", (request) => {
        if (/^https?:/.test(request.url())) remote.push(request.url());
    });
    await page.goto(pathToFileURL(path.join(root, "index.html")).href);
    assert.equal(await page.locator("html").getAttribute("lang"), "zh-CN");
    assert.match(await page.locator("h1").innerText(), /业务/);
    assert.equal(
        await page
            .locator("body")
            .evaluate((e) => getComputedStyle(e).backgroundColor),
        "rgb(29, 32, 33)",
    );
    await page.locator("#tweaks-toggle").click();
    await page.locator("#motion").check();
    await page.locator("#motion").uncheck();
    await page.waitForFunction(
        () => document.documentElement.dataset.motion === "off",
    );
    await page.locator("#tweaks-toggle").click();
    assert.match(
        await page.locator("#hero-terminal").innerText(),
        /agent-entry-cli 0.1.0/,
    );
    await page.locator('[data-command="context"]').click();
    assert.match(await page.locator("#command-output").innerText(), /窗口/);
    const folder = page.locator("#tree details").first();
    await folder.locator("summary").click();
    assert.equal(await folder.getAttribute("open"), "");
    await folder.locator("summary").click();
    assert.equal(await folder.getAttribute("open"), null);
    await page.locator("#copy-install").click();
    await page.waitForFunction(() =>
        /已复制|已选中/.test(
            document.querySelector("#copy-install").textContent,
        ),
    );
    await page.locator("#language").click();
    assert.equal(await page.locator("html").getAttribute("lang"), "en");
    assert.match(
        await page.locator("#copy-install").innerText(),
        /Copied|Selected/,
    );
    assert.match(await page.locator("h1").innerText(), /business/i);
    assert.match(await page.locator("#command-output").innerText(), /window/i);
    assert.equal(
        await page
            .locator("[data-zh][data-en]")
            .evaluateAll(
                (nodes) =>
                    nodes.filter((n) => n.textContent !== n.dataset.en).length,
            ),
        0,
    );
    await page.locator("#language").click();
    assert.equal(
        await page
            .locator("[data-zh][data-en]")
            .evaluateAll(
                (nodes) =>
                    nodes.filter((n) => n.textContent !== n.dataset.zh).length,
            ),
        0,
    );
    await page.locator("#tweaks-toggle").click();
    await page.locator('[data-accent="green"]').click();
    assert.equal(
        await page
            .locator("html")
            .evaluate((e) =>
                getComputedStyle(e).getPropertyValue("--accent").trim(),
            ),
        "#b8bb26",
    );
    await page.locator('[data-accent="gold"]').click();
    await page.locator("#tweaks-toggle").click();
    assert.equal(await page.locator("#tweaks").isVisible(), false);
    for (const section of await page.locator("section.reveal").all()) {
        await section.evaluate((element) =>
            window.scrollTo(
                0,
                element.getBoundingClientRect().top + window.scrollY - 110,
            ),
        );
        await page.waitForFunction(
            (id) =>
                getComputedStyle(
                    document.querySelectorAll("section.reveal")[id],
                ).opacity === "1",
            await section.evaluate((element) =>
                [...document.querySelectorAll("section.reveal")].indexOf(
                    element,
                ),
            ),
        );
    }
    const clock = await page.locator("#clock").innerText();
    assert.match(clock, /^\d{2}:\d{2}:\d{2}$/);
    const localClock = await page.evaluate(() =>
        new Date().toLocaleTimeString("en-GB", { hour12: false }),
    );
    assert.ok(
        Math.abs(
            clock.split(":").reduce((a, v) => a * 60 + Number(v), 0) -
                localClock.split(":").reduce((a, v) => a * 60 + Number(v), 0),
        ) <= 2,
    );
    for (const width of [1440, 768, 380]) {
        await page.setViewportSize({ width, height: 1000 });
        assert.ok(
            await page.evaluate(
                () => document.documentElement.scrollWidth <= innerWidth,
            ),
            `overflow at ${width}`,
        );
        const bad = await page.locator("body").innerText();
        assert.ok(!/undefined|NaN/.test(bad));
    }
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.reload();
    assert.equal(await page.locator("html").getAttribute("data-motion"), "off");
    assert.match(
        await page.locator("#hero-terminal").innerText(),
        /agent-entry-cli 0.1.0/,
    );
    const active = await page.locator(".flow-step.active").count();
    await page.waitForTimeout(1800);
    assert.equal(await page.locator(".flow-step.active").count(), active);
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.reload();
    await page.waitForTimeout(900);
    assert.ok((await page.locator("#hero-terminal").innerText()).length > 0);
    await page.waitForTimeout(6000);
    assert.match(
        await page.locator("#hero-terminal").innerText(),
        /agent-entry-cli 0.1.0/,
    );
    const first = await page
        .locator(".flow-step.active")
        .getAttribute("data-step");
    await page.waitForTimeout(1700);
    assert.notEqual(
        await page.locator(".flow-step.active").getAttribute("data-step"),
        first,
    );
    assert.equal(
        remote.length,
        0,
        "page must work without remote runtime assets",
    );
    assert.deepEqual(errors, []);
    if (process.env.SITE_SCREENSHOT_DIR) {
        await page.emulateMedia({ reducedMotion: "reduce" });
        await page.evaluate(() => window.scrollTo(0, 0));
        const output = process.env.SITE_SCREENSHOT_DIR;
        fs.mkdirSync(output, { recursive: true });
        await page.setViewportSize({ width: 1440, height: 1000 });
        await page.screenshot({
            path: path.join(output, "desktop.png"),
            fullPage: false,
        });
        await page.setViewportSize({ width: 380, height: 900 });
        await page.screenshot({
            path: path.join(output, "mobile.png"),
            fullPage: false,
        });
    }
    console.log(
        "PASS: offline, bilingual, commands, tree, tweaks, clock, motion, 1440/768/380px, no JS errors",
    );
    await context.close();
} finally {
    await browser.close();
}
