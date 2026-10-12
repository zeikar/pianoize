import { style } from "./style.js";
import { keyLayout } from "./keyboard.js";
import { load } from "./roll.js";
import { drawFrame } from "./draw.js";

let ctx;
let data;

// Synchronous: capture.mjs looks for window.pianoize as soon as goto returns, on the load
// event, which fires before start()'s fetches finish.
window.pianoize = { ready: start(), drawAt };

function drawAt(t) {
  drawFrame(ctx, t, data, style);
}

async function start() {
  const manifest = await (await get("/run/manifest.json")).json();
  const notes = load(await (await get(`/run/${manifest.arrangement}`)).json());
  document.body.style.background = style.background;
  const canvas = document.getElementById("screen");
  canvas.width = style.width;
  canvas.height = style.height;
  ctx = canvas.getContext("2d");
  const { height } = style.keyboard;
  data = {
    notes,
    layout: keyLayout(style.width, style.height - height, height, style.keyboard),
    cards: manifest.cards,
    timeline: manifest.timeline,
  };
  await document.fonts.ready;

  if (new URLSearchParams(location.search).has("capture")) {
    document.body.classList.add("capture");
    return;
  }
  const audio = document.getElementById("audio");
  const frame = () => {
    drawAt(audio.currentTime);
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
  // A blob seeks without range requests, which the run's server does not answer.
  audio.src = URL.createObjectURL(await (await get(`/run/${manifest.audio}`)).blob());
}

async function get(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response;
}
