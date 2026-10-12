import { noteRects, phase, pressed } from "./roll.js";

// The frame for video time t. data holds the notes, the key layout, the cards' lines and the
// timeline; every colour and size comes from style.
export function drawFrame(ctx, t, data, style) {
  ctx.fillStyle = style.background;
  ctx.fillRect(0, 0, style.width, style.height);
  const now = phase(t, data.timeline, style.fall.seconds);
  if (now === "roll") {
    drawRoll(ctx, t - data.timeline.music_start, data, style);
  } else {
    drawCard(ctx, data.cards[now], style);
  }
}

function drawRoll(ctx, tMusic, { notes, layout }, style) {
  const keys = new Map(layout.map((k) => [k.pitch, k]));
  const keyboardTop = layout[0].y;
  const rects = noteRects(notes, tMusic, layout, 0, keyboardTop, style.fall.seconds, style.notes);
  const radius = style.notes.cornerRadius;
  // Stroked before the fill, so only the stroke's outer half shows: a rim that keeps a note
  // apart from one it overlaps.
  ctx.strokeStyle = style.background;
  ctx.lineWidth = 2 * style.notes.outline;
  // A black key's lane overlaps its white neighbours', so its notes go on top, as its key does.
  const black = (r) => keys.get(r.pitch).black;
  for (const r of rects.toSorted((a, b) => black(a) - black(b))) {
    // A sounding note meets its key square, as if sliding under the keyboard, and one still
    // entering is cut square by the frame's top. Rounded, since its bottom is a float sum that
    // can miss the keyboard's edge by a hair.
    const sounding = Math.round(r.y + r.h) >= Math.round(keyboardTop);
    const top = r.y > 0 ? radius : 0;
    const bottom = sounding ? 0 : radius;
    ctx.fillStyle = style.hands[r.hand];
    ctx.beginPath();
    ctx.roundRect(r.x, r.y, r.w, r.h, [top, top, bottom, bottom]);
    ctx.stroke();
    ctx.fill();
  }

  const down = pressed(notes, tMusic);
  const { gap } = style.keyboard;
  for (const k of layout.toSorted((a, b) => a.black - b.black)) {
    const idle = k.black ? style.keyboard.blackKey : style.keyboard.whiteKey;
    const fill = down.has(k.pitch) ? style.hands[down.get(k.pitch)] : idle;
    if (k.black) {
      // A rim the width of the white keys' gap, so a lit black key stands out on a lit white
      // one.
      ctx.fillStyle = style.background;
      ctx.fillRect(k.x, k.y, k.w, k.h);
      ctx.fillStyle = fill;
      ctx.fillRect(k.x + gap, k.y, k.w - 2 * gap, k.h - gap);
    } else {
      ctx.fillStyle = fill;
      ctx.fillRect(k.x, k.y, k.w, k.h);
    }
  }
  ctx.fillStyle = style.keyboard.edge;
  ctx.fillRect(0, keyboardTop, style.width, style.keyboard.edgeHeight);
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
