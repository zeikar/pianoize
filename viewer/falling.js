import { noteRects } from "./roll.js";

// The notes falling onto the keyboard at music time tMusic, from the top of the frame to the
// keys' top edge.
export function drawNotes(ctx, notes, tMusic, layout, style) {
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
}
