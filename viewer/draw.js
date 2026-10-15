import { phase, pressed } from "./roll.js";
import { drawKeyboard } from "./keyboard.js";
import { drawNotes } from "./falling.js";
import { drawSparks } from "./sparks.js";

// The frame for video time t. data holds the notes, the key layout, the cards' lines and the
// timeline; every colour and size comes from style.
export function drawFrame(ctx, t, data, style) {
  ctx.fillStyle = style.background;
  ctx.fillRect(0, 0, style.width, style.height);
  const now = phase(t, data.timeline, style.fall.seconds);
  if (now === "roll") {
    const tMusic = t - data.timeline.music_start;
    drawRoll(ctx, data.layout, style);
    // The keys go over the notes, which slide under them, and the light where they meet goes
    // over both.
    drawNotes(ctx, data.notes, tMusic, data.layout, style);
    drawKeyboard(ctx, data.layout, pressed(data.notes, tMusic), style);
    drawSparks(ctx, data.notes, tMusic, data.layout, style);
  } else {
    drawCard(ctx, data.cards[now], style);
  }
}

// The roll's background above the keys: its light, and a line up from each C.
function drawRoll(ctx, layout, style) {
  const keyboardTop = layout[0].y;
  const g = ctx.createLinearGradient(0, 0, 0, keyboardTop);
  g.addColorStop(0, style.roll.top);
  g.addColorStop(1, style.roll.bottom);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, style.width, keyboardTop);
  ctx.fillStyle = style.roll.octaveLine;
  const width = style.roll.octaveLineWidth;
  for (const k of layout) {
    if (k.pitch % 12 === 0) ctx.fillRect(Math.round(k.x - width / 2), 0, width, keyboardTop);
  }
}

// The lines centred as a block: the first at the title size, the rest at the line size.
function drawCard(ctx, lines, style) {
  const { cards } = style;
  const sizes = lines.map((_, i) => (i === 0 ? cards.titleSize : cards.lineSize));
  const height = sizes.reduce((sum, size) => sum + size, 0) + cards.lineGap * (lines.length - 1);
  let y = (style.height - height) / 2;
  ctx.fillStyle = cards.colour;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  lines.forEach((line, i) => {
    ctx.font = `${sizes[i]}px ${cards.fontFamily}`;
    ctx.fillText(line, style.width / 2, y + sizes[i] / 2);
    y += sizes[i] + cards.lineGap;
  });
}
