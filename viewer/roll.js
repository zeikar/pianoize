import { FIRST_PITCH, LAST_PITCH } from "./keyboard.js";

export const FORMAT_VERSION = 1;

export function load(json) {
  if (json.format_version !== FORMAT_VERSION) {
    throw new Error(
      `arrangement format_version ${json.format_version}, this viewer reads ${FORMAT_VERSION}`,
    );
  }
  // export-arrangement never writes these, but a file picked on GitHub Pages can hold them, and
  // a pitch off the keys has no lane to fall in.
  if (!Array.isArray(json.notes)) throw new Error("the arrangement has no notes array");
  for (const n of json.notes) {
    if (!Number.isInteger(n?.pitch) || n.pitch < FIRST_PITCH || n.pitch > LAST_PITCH) {
      throw new Error(
        `a note's pitch ${n?.pitch} is off the 88 keys (${FIRST_PITCH} to ${LAST_PITCH})`,
      );
    }
  }
  return json.notes;
}

// t is video time. The title card gives way one fall time before the music starts, so the
// first notes enter at the top of an empty keyboard.
export function phase(t, timeline, fallSeconds) {
  if (t < timeline.music_start - fallSeconds) return "title";
  if (t >= timeline.music_end) return "credits";
  return "roll";
}

// Pitch -> hand for the notes sounding at tMusic; the latest onset wins an overlap.
export function pressed(notes, tMusic) {
  const result = new Map();
  const onsets = new Map();
  for (const n of notes) {
    if (n.on <= tMusic && tMusic < n.off && n.on >= (onsets.get(n.pitch) ?? -Infinity)) {
      result.set(n.pitch, n.hand);
      onsets.set(n.pitch, n.on);
    }
  }
  return result;
}

// Rects for the notes visible at tMusic. A note's bottom reaches the keyboard at its onset
// and then stays there, shrinking until its end passes.
export function noteRects(notes, tMusic, layout, rollTop, rollBottom, fallSeconds, noteStyle) {
  const lanes = new Map(layout.map((k) => [k.pitch, k]));
  const pxPerSecond = (rollBottom - rollTop) / fallSeconds;
  const yAt = (time) => rollBottom - (time - tMusic) * pxPerSecond;
  const rects = [];
  for (const n of notes) {
    if (n.off <= tMusic || n.on >= tMusic + fallSeconds) continue;
    const key = lanes.get(n.pitch);
    const bottom = Math.min(yAt(n.on), rollBottom);
    const top = Math.max(yAt(n.off) + noteStyle.endGap, rollTop);
    if (bottom <= top) continue;
    rects.push({
      pitch: n.pitch,
      hand: n.hand,
      x: key.x + noteStyle.inset,
      y: top,
      w: key.w - 2 * noteStyle.inset,
      h: bottom - top,
    });
  }
  return rects;
}
