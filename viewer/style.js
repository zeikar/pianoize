// Every colour and every size of the frame lives here; no other module holds one. The page
// around the frame takes its colours from here too, and keeps only its layout sizes in its CSS.
// Timing (frame rate, title and credits length) lives in Python, not here.
export const style = {
  width: 1920,
  height: 1080,
  background: "#14161a",

  // The roll's light: darker at the top of the frame, so the notes come out of the dark, and
  // lighter near the keys, where they land.
  roll: {
    top: "#0c0e11",
    bottom: "#1c1f27",
    // A faint line up from each C, so the eye finds the octaves.
    octaveLine: "rgba(255, 255, 255, 0.05)",
    octaveLineWidth: 1,
  },

  keyboard: {
    height: 200,
    whiteKey: "#f2f2f0",
    // The shadow the felt casts on the white keys' tops, fading out over shadowHeight pixels.
    whiteShadow: "rgba(0, 0, 0, 0.4)",
    shadowHeight: 26,
    blackKey: "#15171b",
    // A black key lightens towards its front, where a bevel catches the light.
    blackKeyFront: "#2c2f37",
    bevel: "#4a4e58",
    bevelHeight: 7,
    // Visible space between neighbouring white keys, in pixels.
    gap: 2,
    // A black key's size as a fraction of a white key's width and the keyboard's height.
    blackWidthRatio: 0.6,
    blackHeightRatio: 0.62,
    // A strip across the top of the keys, like a piano's felt, marking where notes land.
    edge: "#3a3e47",
    edgeHeight: 4,
  },

  // A key is filled with its hand's colour while pressed, and the falling notes use the same.
  // Green for the right hand and blue for the left, as Synthesia does.
  hands: {
    right: "#3ddc97",
    left: "#4aa3ff",
  },

  // The hands' colours near white: a pressed key's top, a note's edge, the flare's and the
  // sparks' hot cores.
  light: {
    right: "#c6fbe3",
    left: "#d0e7ff",
  },

  notes: {
    cornerRadius: 6,
    // Shaved off a note's end so two strikes of one key do not merge into one bar.
    endGap: 4,
    // Pixels kept free on each side of a note inside its key's lane.
    inset: 2,
    // A rim of the background's colour around a note, so a black-key note shows where it
    // overlaps a white-key note of the same hand.
    outline: 2,
    // A glow around each note, added to what lies under it: strokes of [width, opacity] in
    // the hand's colour, from the outside in.
    glow: [
      [22, 0.06],
      [12, 0.1],
      [6, 0.16],
    ],
    // A line of the hand's light colour just inside a note's edge.
    edgeWidth: 1.5,
    edgeOpacity: 0.6,
  },

  // Where a sounding note meets its key, a light on the keys' top edge: it flashes at the
  // note-on and glows while the note sounds. Its size is width × height at rest, flash times
  // more at the note-on, the extra fading with a time constant of decay seconds.
  flare: {
    width: 120,
    height: 76,
    flash: 1.3,
    decay: 0.12,
    opacity: 0.95,
  },

  // A column of the hand's light up from a sounding note's key, fading out at height pixels
  // and width times the key's width.
  beam: {
    height: 300,
    width: 2.6,
    opacity: 0.38,
  },

  // Sparks from where a note meets its key: a burst at the note-on, then a stream while it
  // sounds. They fly up and out by up to spread radians from straight up, slow down at drag
  // per second, drift up at rise pixels a second like embers, and fade over at most life
  // seconds. Speeds are pixels a second; size is a spark's diameter in pixels.
  sparks: {
    burst: 24,
    burstSpeed: 1150,
    rate: 32,
    speed: 520,
    spread: 0.8,
    drag: 3.2,
    rise: 90,
    life: 1.1,
    size: 16,
  },

  fall: {
    // How long a note takes to fall from the top of the roll to the keyboard.
    seconds: 3,
  },

  // The page around the frame takes its other colours, its font and its corner radius from
  // the frame's (main.js's theme()); this one is its own.
  page: {
    error: "#ff8a80",
  },

  cards: {
    fontFamily: "Helvetica Neue, Arial, sans-serif",
    titleSize: 72,
    lineSize: 40,
    // Space between one line's em box and the next's, so the title keeps its own room.
    lineGap: 24,
    colour: "#e8e8e8",
  },
};
