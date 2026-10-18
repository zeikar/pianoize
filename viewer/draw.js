import { pressed, titleOpacity } from "./roll.js";
import { drawKeyboard } from "./keyboard.js";
import { drawNotes } from "./falling.js";
import { drawSparks } from "./sparks.js";

// The frame for video time t. data holds the notes, the key layout, the title card's lines and
// the timeline; every colour and size comes from style. The roll runs from 0 s, so the first notes
// fall in while the title card lies over it.
export function drawFrame(ctx, t, data, style) {
  ctx.fillStyle = style.background;
  ctx.fillRect(0, 0, style.width, style.height);
  const tMusic = t - data.timeline.music_start;
  drawRoll(ctx, data.layout, style);
  // The keys go over the notes, which slide under them, and the light where they meet goes
  // over both.
  drawNotes(ctx, data.notes, tMusic, data.layout, style);
  drawKeyboard(ctx, data.layout, pressed(data.notes, tMusic), style);
  drawSparks(ctx, data.notes, tMusic, data.layout, style);
  // The home page has no cards, and its music starts at 0 s.
  const opacity = titleOpacity(t, data.timeline, style.cards.fadeSeconds);
  if (opacity > 0 && data.cards) {
    ctx.save();
    ctx.globalAlpha = opacity;
    // Over the falling notes, the shadow keeps the lines readable.
    ctx.shadowColor = style.cards.shadow;
    ctx.shadowBlur = style.cards.shadowBlur;
    drawCard(ctx, data.cards.title, style, data.layout[0].y);
    ctx.restore();
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

// The lines centred as a block in the frame's top `area` pixels: the first at the title size,
// the rest at the line size.
function drawCard(ctx, lines, style, area) {
  const { cards } = style;
  const sizes = lines.map((_, i) => (i === 0 ? cards.titleSize : cards.lineSize));
  const height = sizes.reduce((sum, size) => sum + size, 0) + cards.lineGap * (lines.length - 1);
  let y = (area - height) / 2;
  ctx.fillStyle = cards.colour;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  lines.forEach((line, i) => {
    ctx.font = `${sizes[i]}px ${cards.fontFamily}`;
    ctx.fillText(line, style.width / 2, y + sizes[i] / 2);
    y += sizes[i] + cards.lineGap;
  });
}
