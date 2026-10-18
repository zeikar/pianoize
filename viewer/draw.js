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

// The thumbnail, drawn at the frame's size for ffmpeg to scale down: the frame at its moment,
// zoomed in on the keys and centred on the notes, a dark band over its top, and the title card's
// lines on the band. The first line is the title, the last a tag in the right hand's light, and
// any between them a subtitle; a line too wide for the band shrinks to fit.
export function drawThumbnail(ctx, data, style) {
  const look = style.thumbnail;
  const { music_seconds, pitch } = data.thumbnail;
  const frame = document.createElement("canvas");
  frame.width = style.width;
  frame.height = style.height;
  drawFrame(frame.getContext("2d"), data.timeline.music_start + music_seconds, data, style);
  const w = style.width / look.zoom;
  const h = style.height / look.zoom;
  const key = data.layout.find((k) => k.pitch === pitch);
  const x = Math.min(Math.max(key.x + key.w / 2 - w / 2, 0), style.width - w);
  ctx.drawImage(frame, x, style.height - h, w, h, 0, 0, style.width, style.height);

  const band = ctx.createLinearGradient(0, 0, 0, look.band.height);
  band.addColorStop(0, look.band.top);
  band.addColorStop(0.7, look.band.middle);
  band.addColorStop(1, look.band.end);
  ctx.fillStyle = band;
  ctx.fillRect(0, 0, style.width, look.band.height);

  ctx.save();
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.shadowColor = look.shadow;
  ctx.shadowBlur = look.shadowBlur;
  const lines = data.cards.title;
  let y = look.top;
  lines.forEach((line, i) => {
    const kind = i === 0 ? look.title : i === lines.length - 1 ? look.tag : look.subtitle;
    const font = (size) => `${kind.weight} ${size}px ${style.cards.fontFamily}`;
    ctx.font = font(kind.size);
    const width = ctx.measureText(line).width;
    const size = width > look.maxWidth ? Math.floor((kind.size * look.maxWidth) / width) : kind.size;
    ctx.font = font(size);
    ctx.fillStyle = kind.colour;
    ctx.fillText(line, style.width / 2, y + size / 2);
    y += size + look.lineGap;
  });
  ctx.restore();
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
