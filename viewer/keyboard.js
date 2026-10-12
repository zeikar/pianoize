const FIRST_PITCH = 21; // A0
const LAST_PITCH = 108; // C8
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
