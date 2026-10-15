import { load } from "./roll.js";

// The form the page shows when it has no run, as on GitHub Pages: an arrangement JSON and its
// audio, read in the browser and sent nowhere. It draws nothing. Once both files are picked
// and the JSON is checked, onPick(notes, audioFile) gets them; fail(message) shows an error
// that comes later, such as audio the browser can't play.
export function picker(form, style, onPick) {
  const error = form.querySelector("#error");
  form.hidden = false;
  form.style.padding = form.style.gap = `${style.picker.padding}px`;
  form.style.fontFamily = style.cards.fontFamily;
  error.style.color = style.picker.error;
  form.addEventListener("change", async () => {
    const [json] = form.elements.arrangement.files;
    const [sound] = form.elements.audio.files;
    if (!json || !sound) return;
    error.textContent = "";
    let notes;
    try {
      notes = load(JSON.parse(await json.text()));
    } catch (e) {
      error.textContent = `${json.name}: ${e.message}`;
      return;
    }
    onPick(notes, sound);
  });
  return {
    fail(message) {
      error.textContent = message;
    },
  };
}
