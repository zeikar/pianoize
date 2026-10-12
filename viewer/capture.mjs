// node capture.mjs --url URL --frames N --fps FPS: loads the page in capture mode in the
// installed Chrome and writes N PNG frames to stdout, frame i drawn at i / FPS seconds.
// render-video pipes them into ffmpeg.
import { once } from "node:events";
import { parseArgs } from "node:util";
import { chromium } from "playwright-core";
import { style } from "./style.js";

const PROGRESS_EVERY = 300;

// A write to a pipe ffmpeg has closed fails later, as an error event; without a listener that
// would crash the script before the browser is closed.
let broken = null;
process.stdout.on("error", (error) => {
  broken ??= error;
});

async function write(png) {
  // Stop at the first failed write rather than queue more frames behind it.
  if (broken) throw broken;
  // once() rejects if the error comes while it waits.
  if (!process.stdout.write(png)) await once(process.stdout, "drain");
}

async function capture() {
  const { values } = parseArgs({
    options: {
      url: { type: "string" },
      frames: { type: "string" },
      fps: { type: "string" },
    },
  });
  const frames = Number(values.frames);
  const fps = Number(values.fps);
  const positive = [frames, fps].every((n) => Number.isInteger(n) && n > 0);
  if (!values.url || !positive) {
    throw new Error("usage: capture.mjs --url URL --frames N --fps FPS");
  }
  const browser = await chromium.launch({
    channel: "chrome",
    headless: true,
    args: ["--force-color-profile=srgb"],
  });
  try {
    const context = await browser.newContext({
      viewport: { width: style.width, height: style.height },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    await page.goto(`${values.url}?capture`);
    await page.evaluate(() => window.pianoize.ready);
    for (let i = 0; i < frames; i++) {
      await page.evaluate((t) => window.pianoize.drawAt(t), i / fps);
      await write(await page.screenshot({ type: "png", animations: "disabled", caret: "hide" }));
      if ((i + 1) % PROGRESS_EVERY === 0) process.stderr.write(`frame ${i + 1}/${frames}\n`);
    }
  } finally {
    // Closing the browser is what deletes its temporary profile.
    await browser.close();
  }
}

try {
  await capture();
} catch (error) {
  process.stderr.write(`capture.mjs: ${error.message}\n`);
  process.exitCode = 1;
}
