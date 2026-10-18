// node social.mjs: draws social.html in the installed Chrome and writes it to social.png, the
// home page's link preview, which is also the README's hero and the repository's social
// preview. Run it again when the look in style.js changes.
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const HERE = new URL("./", import.meta.url);
// Chrome refuses ES modules from file://, so the page is loaded from a made-up origin whose
// requests Playwright answers from this directory.
const ORIGIN = "http://social.invalid/";

// Without the GPU, so a run with nothing changed writes the same bytes: on the GPU a few pixels
// came out one level apart from run to run.
const browser = await chromium.launch({
  channel: "chrome",
  headless: true,
  args: ["--force-color-profile=srgb", "--disable-gpu"],
});
try {
  const context = await browser.newContext({
    viewport: { width: 1280, height: 640 },
    deviceScaleFactor: 1.5,
  });
  await context.route(`${ORIGIN}**`, (route) => {
    const path = new URL(route.request().url()).pathname.slice(1);
    return route.fulfill({ path: fileURLToPath(new URL(path, HERE)) });
  });
  const page = await context.newPage();
  await page.goto(`${ORIGIN}social.html`);
  await page.evaluate(() => window.social.ready);
  const out = fileURLToPath(new URL("social.png", HERE));
  await page.screenshot({ path: out });
  console.log(`wrote ${out}`);
} finally {
  await browser.close();
}
