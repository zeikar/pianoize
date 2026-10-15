import { style } from "./style.js";
import { keyLayout } from "./keyboard.js";
import { load } from "./roll.js";
import { drawFrame } from "./draw.js";
import { picker } from "./picker.js";

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

// Plays what the user picks. The audio's 0 s is the music's 0 s, and there are no cards: the
// roll runs from the start and never ends. Until both files are picked, the keyboard is empty.
function pickFiles() {
  const audio = document.getElementById("audio");
  const timeline = { music_start: 0, music_end: Infinity };
  let name;
  const files = picker(document.getElementById("files"), style, (notes, sound) => {
    show(notes, { timeline });
    name = sound.name;
    const previous = audio.src;
    audio.src = URL.createObjectURL(sound);
    if (previous) URL.revokeObjectURL(previous);
  });
  audio.addEventListener("error", () => files.fail(`${name}: the browser can't play this audio`));
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
