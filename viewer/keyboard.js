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
// fills the key, near white at its top where the note lands. The felt casts a shadow on the
// white keys, the black keys lighten towards a bevel at their front, and a strip like the felt
// runs across their top.
export function drawKeyboard(ctx, layout, down, style) {
  const kb = style.keyboard;
  const top = layout[0].y;
  const lit = (k, hand) => {
    const g = ctx.createLinearGradient(0, k.y, 0, k.y + k.h);
    g.addColorStop(0, style.light[hand]);
    g.addColorStop(0.45, style.hands[hand]);
    return g;
  };
  const shadow = ctx.createLinearGradient(0, top, 0, top + kb.shadowHeight);
  shadow.addColorStop(0, kb.whiteShadow);
  shadow.addColorStop(1, "rgba(0, 0, 0, 0)");
  const blackFill = ctx.createLinearGradient(0, top, 0, top + kb.height * kb.blackHeightRatio);
  blackFill.addColorStop(0, kb.blackKey);
  blackFill.addColorStop(1, kb.blackKeyFront);

  for (const k of layout.filter((k) => !k.black)) {
    const hand = down.get(k.pitch);
    ctx.fillStyle = hand ? lit(k, hand) : kb.whiteKey;
    ctx.fillRect(k.x, k.y, k.w, k.h);
  }
  ctx.fillStyle = shadow;
  ctx.fillRect(0, top, style.width, kb.shadowHeight);

  const { gap } = kb;
  for (const k of layout.filter((k) => k.black)) {
    const hand = down.get(k.pitch);
    // A rim the width of the white keys' gap, so a lit black key stands out on a lit white one.
    ctx.fillStyle = style.background;
    ctx.fillRect(k.x, k.y, k.w, k.h);
    const [x, w, h] = [k.x + gap, k.w - 2 * gap, k.h - gap];
    ctx.fillStyle = hand ? lit(k, hand) : blackFill;
    ctx.fillRect(x, k.y, w, h);
    if (!hand) {
      ctx.fillStyle = kb.bevel;
      ctx.fillRect(x, k.y + h - kb.bevelHeight, w, kb.bevelHeight);
    }
  }
  ctx.fillStyle = kb.edge;
  ctx.fillRect(0, top, style.width, kb.edgeHeight);
}
