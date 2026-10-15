import { noteRects } from "./roll.js";

// The notes falling onto the keyboard at music time tMusic, from the top of the frame to the
// keys' top edge: a glow under them all, then each note with a light edge.
export function drawNotes(ctx, notes, tMusic, layout, style) {
  const keys = new Map(layout.map((k) => [k.pitch, k]));
  const keyboardTop = layout[0].y;
  const look = style.notes;
  const rects = noteRects(notes, tMusic, layout, 0, keyboardTop, style.fall.seconds, look);
  // A black key's lane overlaps its white neighbours', so its notes go on top, as its key does.
  const black = (r) => keys.get(r.pitch).black;
  const ordered = rects.toSorted((a, b) => black(a) - black(b));
  const outline = (r) => {
    // A sounding note meets its key square, as if sliding under the keyboard, and one still
    // entering is cut square by the frame's top. Rounded, since its bottom is a float sum that
    // can miss the keyboard's edge by a hair.
    const sounding = Math.round(r.y + r.h) >= Math.round(keyboardTop);
    const top = r.y > 0 ? look.cornerRadius : 0;
    const bottom = sounding ? 0 : look.cornerRadius;
    ctx.beginPath();
    ctx.roundRect(r.x, r.y, r.w, r.h, [top, top, bottom, bottom]);
  };

  // Every note's glow first, so no glow lies over another note.
  ctx.save();
  ctx.globalCompositeOperation = "lighter";
  for (const r of ordered) {
    ctx.strokeStyle = style.hands[r.hand];
    outline(r);
    for (const [width, opacity] of look.glow) {
      ctx.globalAlpha = opacity;
      ctx.lineWidth = width;
      ctx.stroke();
    }
  }
  ctx.restore();

  for (const r of ordered) {
    outline(r);
    // Stroked before the fill, so only the stroke's outer half shows: a rim that keeps a note
    // apart from one it overlaps.
    ctx.strokeStyle = style.background;
    ctx.lineWidth = 2 * look.outline;
    ctx.stroke();
    ctx.fillStyle = style.hands[r.hand];
    ctx.fill();
    // The edge inside the note: clipped to it, a stroke on its outline shows its inner half.
    ctx.save();
    ctx.clip();
    ctx.globalAlpha = look.edgeOpacity;
    ctx.strokeStyle = style.light[r.hand];
    ctx.lineWidth = 2 * look.edgeWidth;
    ctx.stroke();
    ctx.restore();
  }
}
