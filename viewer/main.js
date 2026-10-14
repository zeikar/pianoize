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
  document.body.style.background = style.background;
  const canvas = document.getElementById("screen");
  canvas.width = style.width;
  canvas.height = style.height;
  ctx = canvas.getContext("2d");
  // Relative, so the page works below a path too, as on GitHub Pages.
  const response = await fetch("run/manifest.json");
  // Only pianoize's own server has a run. Anywhere else the user picks the files.
  if (response.status === 404) {
    pickFiles();
    return;
  }
  const manifest = await checked(response).json();
  show(load(await (await get(`run/${manifest.arrangement}`)).json()), manifest);
  await document.fonts.ready;

  if (new URLSearchParams(location.search).has("capture")) {
    document.body.classList.add("capture");
    return;
  }
  const audio = document.getElementById("audio");
  follow(audio);
  // A blob seeks without range requests, which the run's server does not answer.
  audio.src = URL.createObjectURL(await (await get(`run/${manifest.audio}`)).blob());
}

function show(notes, { cards, timeline }) {
  const { height } = style.keyboard;
  data = {
    notes,
    layout: keyLayout(style.width, style.height - height, height, style.keyboard),
    cards,
    timeline,
  };
}

// Draws the frame at the audio control's time on every animation frame.
function follow(audio) {
  const frame = () => {
    drawAt(audio.currentTime);
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}

// An arrangement JSON and its audio, read in the browser and sent nowhere. The audio's 0 s is
// the music's 0 s, and there are no cards: the roll runs from the start and never ends. Until
// both are picked, the keyboard is empty.
function pickFiles() {
  const form = document.getElementById("files");
  const error = document.getElementById("error");
  const audio = document.getElementById("audio");
  const timeline = { music_start: 0, music_end: Infinity };
  form.hidden = false;
  form.style.padding = form.style.gap = `${style.picker.padding}px`;
  form.style.fontFamily = style.cards.fontFamily;
  error.style.color = style.picker.error;
  audio.addEventListener("error", () => {
    error.textContent = `${form.elements.audio.files[0]?.name}: the browser can't play this audio`;
  });
  form.addEventListener("change", async () => {
    const [json] = form.elements.arrangement.files;
    const [sound] = form.elements.audio.files;
    if (!json || !sound) return;
    error.textContent = "";
    try {
      show(load(JSON.parse(await json.text())), { timeline });
    } catch (e) {
      error.textContent = `${json.name}: ${e.message}`;
      return;
    }
    const previous = audio.src;
    audio.src = URL.createObjectURL(sound);
    if (previous) URL.revokeObjectURL(previous);
  });
  show([], { timeline });
  follow(audio);
}

async function get(path) {
  return checked(await fetch(path));
}

function checked(response) {
  if (!response.ok) throw new Error(`${response.url}: HTTP ${response.status}`);
  return response;
}
