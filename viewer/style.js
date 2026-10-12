// Everything visual lives here; no other module holds a colour or a size.
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
  },

  // A key is filled with its hand's colour while pressed, and the falling notes use the same.
  hands: {
    right: "#4aa3ff",
    left: "#3ddc97",
  },

  notes: {
    cornerRadius: 6,
    // Shaved off a note's end so two strikes of one key do not merge into one bar.
    endGap: 4,
    // Pixels kept free on each side of a note inside its key's lane.
    inset: 2,
  },

  fall: {
    // How long a note takes to fall from the top of the roll to the keyboard.
    seconds: 3,
  },

  cards: {
    fontFamily: "Helvetica Neue, Arial, sans-serif",
    titleSize: 72,
    lineSize: 40,
    lineSpacing: 64,
    colour: "#e8e8e8",
  },
};
