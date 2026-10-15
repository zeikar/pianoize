// Every colour and every size of the frame lives here; no other module holds one. The page
// around the frame takes its colours from here too, and keeps only its layout sizes in its CSS.
// Timing (frame rate, title and credits length) lives in Python, not here.
export const style = {
  width: 1920,
  height: 1080,
  background: "#14161a",

  keyboard: {
    height: 200,
    whiteKey: "#f2f2f0",
    blackKey: "#1b1d22",
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

  notes: {
    cornerRadius: 6,
    // Shaved off a note's end so two strikes of one key do not merge into one bar.
    endGap: 4,
    // Pixels kept free on each side of a note inside its key's lane.
    inset: 2,
    // A rim of the background's colour around a note, so a black-key note shows where it
    // overlaps a white-key note of the same hand.
    outline: 2,
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
