export const FIRST_PITCH = 21; // A0
export const LAST_PITCH = 108; // C8
const WHITE_KEYS = 52;
// Pitch classes C#, D#, F#, G#, A#.
const BLACK_CLASSES = new Set([1, 3, 6, 8, 10]);

export function keyLayout(width, top, height, keyboard) {
  const whiteW = width / WHITE_KEYS;
  const keys = [];
  let white = 0;
  for (let pitch = FIRST_PITCH; pitch <= LAST_PITCH; pitch++) {
    if (BLACK_CLASSES.has(pitch % 12)) {
      // Centred on the boundary with the next white key; none exists between E-F and B-C
      // because those pitches are both white.
      const w = whiteW * keyboard.blackWidthRatio;
      keys.push({
        pitch,
        black: true,
        x: white * whiteW - w / 2,
        y: top,
        w,
        h: height * keyboard.blackHeightRatio,
      });
    } else {
      // The gap is split between neighbours, so the outer edges meet 0 and width.
      const left = white === 0 ? 0 : keyboard.gap / 2;
      const right = white === WHITE_KEYS - 1 ? 0 : keyboard.gap / 2;
      keys.push({
        pitch,
        black: false,
        x: white * whiteW + left,
        y: top,
        w: whiteW - left - right,
        h: height,
      });
      white++;
    }
  }
  return keys;
}

// The keys at the bottom of the frame: down maps a pitch to the hand pressing it, whose colour
// fills the key. A strip like a piano's felt runs across their top.
export function drawKeyboard(ctx, layout, down, style) {
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
  ctx.fillRect(0, layout[0].y, style.width, style.keyboard.edgeHeight);
}
