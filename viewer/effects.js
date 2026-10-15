// The effects' strengths, for trying them on the page: a level of 1 is style.js's own value,
// 0 turns the effect off and 2 doubles it. The video draws style.js as it is; a level worth
// keeping goes into style.js.
export const EFFECTS = ["glow", "flare", "beam", "sparks"];

// style with each effect at its level. Every level at 1 gives style's own values.
export function tune(style, levels) {
  const { glow, flare, beam, sparks } = levels;
  return {
    ...style,
    notes: {
      ...style.notes,
      glow: style.notes.glow.map(([width, opacity]) => [width, opacity * glow]),
    },
    // Brighter up to full, then bigger: the square root keeps the area in step with the level.
    flare: {
      ...style.flare,
      opacity: Math.min(1, style.flare.opacity * flare),
      width: style.flare.width * Math.sqrt(Math.max(1, flare)),
      height: style.flare.height * Math.sqrt(Math.max(1, flare)),
    },
    beam: { ...style.beam, opacity: style.beam.opacity * beam },
    sparks: {
      ...style.sparks,
      burst: Math.round(style.sparks.burst * sparks),
      rate: style.sparks.rate * sparks,
    },
  };
}

// The sliders in panel, one an effect, with a percentage beside each and a reset; toggle shows
// and hides it. onChange gets the levels whenever one moves.
export function effectsPanel(panel, toggle, onChange) {
  toggle.addEventListener("click", () => {
    panel.hidden = !panel.hidden;
    toggle.setAttribute("aria-expanded", String(!panel.hidden));
  });
  const sliders = Object.fromEntries(EFFECTS.map((name) => [name, panel.elements[name]]));
  const changed = () => {
    const levels = {};
    for (const [name, slider] of Object.entries(sliders)) {
      levels[name] = Number(slider.value) / 100;
      panel.querySelector(`output[for="${slider.id}"]`).textContent = `${slider.value}%`;
    }
    onChange(levels);
  };
  panel.addEventListener("input", changed);
  // After the reset event, which comes before the sliders are back at their defaults.
  panel.addEventListener("reset", () => setTimeout(changed));
  changed();
}
