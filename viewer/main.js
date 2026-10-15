import { style } from "./style.js";
import { keyLayout } from "./keyboard.js";
import { load } from "./roll.js";
import { drawFrame } from "./draw.js";
import { picker } from "./picker.js";
import { transport } from "./transport.js";
import { effectsPanel, tune } from "./effects.js";

let ctx;
let data;
// The style a frame is drawn in: style.js's, or the effects panel's tuning of it. The capture
// never tunes it.
let look = style;

// Synchronous: capture.mjs looks for window.pianoize as soon as goto returns, on the load
// event, which fires before start()'s fetches finish.
window.pianoize = { ready: start(), drawAt };

function drawAt(t) {
  drawFrame(ctx, t, data, look);
}

async function start() {
  theme();
  const canvas = document.getElementById("screen");
  canvas.width = style.width;
  canvas.height = style.height;
  ctx = canvas.getContext("2d");
  // Relative, so the page works below a path too, as on GitHub Pages.
  const response = await fetch("run/manifest.json");
  // Only pianoize's own server has a run. Anywhere else the page is the home page.
  if (response.status === 404) {
    home();
    return;
  }
  document.body.classList.add("run");
  const manifest = await checked(response).json();
  show(load(await (await get(`run/${manifest.arrangement}`)).json()), manifest);
  await document.fonts.ready;

  if (new URLSearchParams(location.search).has("capture")) {
    document.body.classList.add("capture");
    return;
  }
  const audio = document.getElementById("audio");
  player(audio);
  follow(audio);
  // A blob seeks without range requests, which the run's server does not answer.
  audio.src = URL.createObjectURL(await (await get(`run/${manifest.audio}`)).blob());
}

// The page's colours, font and corner radius come from style.js, as the frame's do; style.css
// reads them as custom properties.
function theme() {
  const set = (name, value) => document.documentElement.style.setProperty(`--${name}`, value);
  set("background", style.background);
  set("text", style.cards.colour);
  set("key", style.keyboard.whiteKey);
  set("felt", style.keyboard.edge);
  set("right", style.hands.right);
  set("left", style.hands.left);
  set("error", style.page.error);
  set("font", style.cards.fontFamily);
  set("radius", `${style.notes.cornerRadius}px`);
  // The keyboard's share of the frame's height, which the picker keeps clear.
  set("keyboard", `${(style.keyboard.height / style.height) * 100}%`);
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

// The controls under the picture: the player and the effects panel.
function player(audio) {
  transport(document.getElementById("transport"), audio, document.getElementById("screen"));
  const toggle = document.querySelector(".effects-toggle");
  effectsPanel(document.getElementById("effects"), toggle, (levels) => {
    look = tune(style, levels);
  });
}

// Draws the frame at the audio's time on every animation frame.
function follow(audio) {
  const frame = () => {
    drawAt(audio.currentTime);
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}

// Plays what the user picks. The audio's 0 s is the music's 0 s, and there are no cards: the
// roll runs from the start and never ends. Until both files are picked, the keyboard is empty.
function home() {
  const audio = document.getElementById("audio");
  const stage = document.querySelector(".stage");
  const controls = document.getElementById("transport");
  const timeline = { music_start: 0, music_end: Infinity };
  let playing = null;
  // Brings the stage and the player into view with the focus on Play, so the next key or
  // click plays.
  const present = () => {
    const above = stage.getBoundingClientRect().top < 0;
    if (above || controls.getBoundingClientRect().bottom > innerHeight) {
      const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
      stage.scrollIntoView({ block: "start", behavior: still ? "auto" : "smooth" });
    }
    controls.querySelector(".play").focus({ preventScroll: true });
  };
  const elements = {
    form: document.getElementById("files"),
    stage,
    loaded: document.getElementById("loaded"),
  };
  const files = picker(elements, (notes, sound) => {
    show(notes, { timeline });
    // A new arrangement on the same audio keeps its place.
    if (sound === playing) return present();
    playing = sound;
    const previous = audio.src;
    audio.src = URL.createObjectURL(sound);
    if (previous) URL.revokeObjectURL(previous);
    // Play is enabled on this event, by the player's listener, which comes first.
    audio.addEventListener("loadedmetadata", present, { once: true });
  });
  audio.addEventListener("error", () => {
    files.fail(`${playing.name}: this browser can't play this audio`);
  });
  player(audio);
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
