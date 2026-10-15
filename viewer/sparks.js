// The light where a note meets its key: a flare on the keys' top edge, and sparks that fly up
// from it and fade. Both are functions of the music's time alone, with the sparks' randomness
// drawn from a hash of the note's pitch and onset and the spark's number, so any t draws the
// same in any order, and a note sparks the same whatever else the arrangement holds: the
// preview, a seek and the capture agree.

// Sparks alive at tMusic, as {hand, x, y, size, opacity}. A note bursts at its note-on and
// streams while it sounds; spark k of the stream is born k / rate seconds after the note-on.
export function sparks(notes, tMusic, layout, keyboardTop, p) {
  const lanes = new Map(layout.map((k) => [k.pitch, k]));
  const alive = [];
  for (const n of notes) {
    if (n.on > tMusic || n.off + p.life <= tMusic) continue;
    const key = lanes.get(n.pitch);
    const seed = Math.imul(n.pitch, 0x9e3779b1) ^ Math.round(n.on * 1000);
    const add = (born, k, speed) => {
      const age = tMusic - born;
      const r = (j) => random(seed, k, j);
      const life = p.life * (0.45 + 0.55 * r(0));
      if (age < 0 || age >= life) return;
      const angle = (r(1) * 2 - 1) * p.spread;
      const v = speed * (0.55 + 0.45 * r(2));
      // Slowed by drag from v at birth: the distance flown is v (1 - e^(-drag age)) / drag.
      const flown = (1 - Math.exp(-p.drag * age)) / p.drag;
      const fade = 1 - age / life;
      alive.push({
        hand: n.hand,
        x: key.x + key.w * r(3) + Math.sin(angle) * v * flown,
        y: keyboardTop - Math.cos(angle) * v * flown - p.rise * age,
        size: p.size * (0.45 + 0.75 * r(4)) * (0.4 + 0.6 * fade),
        opacity: fade,
      });
    };
    for (let k = 0; k < p.burst; k++) add(n.on, k, p.burstSpeed);
    // Only the stream's sparks young enough to be alive.
    const end = Math.min(tMusic, n.off);
    const first = Math.max(0, Math.ceil((tMusic - p.life - n.on) * p.rate));
    for (let k = first; n.on + k / p.rate <= end; k++) add(n.on + k / p.rate, p.burst + k, p.speed);
  }
  return alive;
}

// The flare's size at tMusic for a note sounding then: bigger at the note-on, settling to
// its size at rest.
export function flareScale(n, tMusic, p) {
  return 1 + p.flash * Math.exp(-(tMusic - n.on) / p.decay);
}

// A number in [0, 1) from three integers, the same every time.
function random(a, b, c) {
  let h = Math.imul(a, 0x9e3779b1) ^ Math.imul(b + 0x632be5ab, 0x85ebca77);
  h ^= Math.imul(c + 1, 0xc2b2ae3d);
  h = Math.imul(h ^ (h >>> 16), 0x7feb352d);
  h = Math.imul(h ^ (h >>> 15), 0x846ca68b);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

// Drawn over the keyboard, adding light to what is under it: the beams and the flares of the
// sounding notes, then the sparks.
export function drawSparks(ctx, notes, tMusic, layout, style) {
  const keyboardTop = layout[0].y;
  const lanes = new Map(layout.map((k) => [k.pitch, k]));
  const { beam, flare } = style;
  ctx.save();
  ctx.globalCompositeOperation = "lighter";
  for (const n of notes) {
    if (n.on > tMusic || n.off <= tMusic) continue;
    const key = lanes.get(n.pitch);
    const centre = key.x + key.w / 2;
    const scale = flareScale(n, tMusic, flare);
    const bw = key.w * beam.width;
    ctx.globalAlpha = Math.min(1, beam.opacity * scale);
    const column = beamSprite(style, n.hand);
    ctx.drawImage(column, centre - bw / 2, keyboardTop - beam.height, bw, beam.height);
    const w = flare.width * scale;
    const h = flare.height * scale;
    ctx.globalAlpha = flare.opacity;
    ctx.drawImage(sprite(style, n.hand, SOFT), centre - w / 2, keyboardTop - h / 2, w, h);
  }
  for (const s of sparks(notes, tMusic, layout, keyboardTop, style.sparks)) {
    ctx.globalAlpha = s.opacity;
    const image = sprite(style, s.hand, HOT);
    ctx.drawImage(image, s.x - s.size / 2, s.y - s.size / 2, s.size, s.size);
  }
  ctx.restore();
}

// The two lights' profiles from the centre out: [offset, colour] where colour is "white",
// "light" (the hand's light colour) or an opacity of the hand's colour. A flare is soft; a spark
// is a white-hot point with a small halo.
const SOFT = [
  [0, "white"],
  [0.18, "light"],
  [0.45, 0.55],
  [1, 0],
];
const HOT = [
  [0, "white"],
  [0.14, "white"],
  [0.3, "light"],
  [0.55, 0.45],
  [1, 0],
];

// The lights are drawn once each, per hand, and scaled to size.
const sprites = new Map();
function cached(key, width, height, paint) {
  if (!sprites.has(key)) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    paint(canvas.getContext("2d"));
    sprites.set(key, canvas);
  }
  return sprites.get(key);
}

// A round light of a profile.
function sprite(style, hand, profile) {
  const size = 64;
  return cached(`${hand} ${profile === HOT ? "hot" : "soft"}`, size, size, (ctx) => {
    const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    for (const [offset, colour] of profile) {
      const named = { white: "#ffffff", light: style.light[hand] }[colour];
      g.addColorStop(offset, named ?? rgba(style.hands[hand], colour));
    }
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
  });
}

// A column of the hand's colour, soft at both sides and fading out towards its top.
function beamSprite(style, hand) {
  const [w, h] = [32, 128];
  return cached(`${hand} beam`, w, h, (ctx) => {
    const across = ctx.createLinearGradient(0, 0, w, 0);
    across.addColorStop(0, rgba(style.hands[hand], 0));
    across.addColorStop(0.5, rgba(style.hands[hand], 1));
    across.addColorStop(1, rgba(style.hands[hand], 0));
    ctx.fillStyle = across;
    ctx.fillRect(0, 0, w, h);
    const up = ctx.createLinearGradient(0, h, 0, 0);
    up.addColorStop(0, "rgba(0, 0, 0, 1)");
    up.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.globalCompositeOperation = "destination-in";
    ctx.fillStyle = up;
    ctx.fillRect(0, 0, w, h);
  });
}

// "#rrggbb" at an opacity, so a gradient fades to the colour's own transparent, not black's.
export function rgba(hex, opacity) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return `rgba(${r}, ${g}, ${b}, ${opacity})`;
}
