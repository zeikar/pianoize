import { load } from "./roll.js";

const AUDIO = /\.(wav|mp3|m4a|aac|ogg|oga|opus|flac)$/i;
const MIDI = /\.midi?$/i;

// The files the home page plays: an arrangement JSON and its audio, chosen with a button or
// dropped anywhere on the page, read in the browser and sent nowhere. It draws nothing. A pick
// replaces the files of the kinds it holds, so new audio keeps the arrangement; a file that
// fails its check replaces nothing. Once both are there, onPick(notes, audioFile) gets them;
// fail(message) drops audio that failed later, while playing.
export function picker({ form, stage, loaded }, onPick) {
  const input = form.elements.files;
  let json = null;
  let notes = null;
  let sound = null;
  let message = "";

  const show = () => {
    for (const [need, file] of [
      ["arrangement", json],
      ["audio", sound],
    ]) {
      const row = form.querySelector(`[data-need="${need}"]`);
      row.toggleAttribute("data-chosen", Boolean(file));
      row.querySelector("dd").textContent = file ? file.name : "Not chosen yet";
    }
    const ready = Boolean(notes && sound);
    form.hidden = ready;
    loaded.hidden = !ready;
    if (ready) loaded.querySelector(".names").textContent = `${json.name} and ${sound.name}`;
    // Where the user is looking: in the card while a file is missing, under the player once
    // both play.
    form.querySelector(".error").textContent = ready ? "" : message;
    loaded.querySelector(".error").textContent = ready ? message : "";
  };

  const take = async (files) => {
    const problems = [];
    let changed = false;
    for (const file of files) {
      if (/\.json$/i.test(file.name) || file.type === "application/json") {
        try {
          notes = load(JSON.parse(await file.text()));
          json = file;
          changed = true;
        } catch (e) {
          problems.push(`${file.name}: ${e instanceof SyntaxError ? "not valid JSON" : e.message}`);
        }
      } else if (MIDI.test(file.name) || file.type.includes("midi")) {
        problems.push(
          `${file.name} is the MIDI; pick the JSON pianoize export-arrangement writes from it`,
        );
      } else if (file.type.startsWith("audio/") || AUDIO.test(file.name)) {
        if (await playable(file)) {
          sound = file;
          changed = true;
        } else {
          problems.push(`${file.name}: this browser can't play this audio`);
        }
      } else {
        problems.push(`${file.name} is neither an arrangement JSON nor audio`);
      }
    }
    message = problems.join("\n");
    show();
    if (changed && notes && sound) onPick(notes, sound);
  };

  for (const button of document.querySelectorAll(".choose")) {
    button.addEventListener("click", () => input.click());
  }
  input.addEventListener("change", () => {
    take([...input.files]);
    // So picking the same file again is a change too.
    input.value = "";
  });

  // A file dropped anywhere is taken; without this the browser would open it in place of the
  // page. While one is dragged over the page, the picker shows, ready for it.
  const files = (e) => e.dataTransfer?.types.includes("Files");
  document.addEventListener("dragover", (e) => {
    if (!files(e)) return;
    e.preventDefault();
    stage.classList.add("over");
  });
  document.addEventListener("dragleave", (e) => {
    if (!e.relatedTarget) stage.classList.remove("over");
  });
  document.addEventListener("drop", (e) => {
    if (!files(e)) return;
    e.preventDefault();
    stage.classList.remove("over");
    take([...e.dataTransfer.files]);
  });

  show();
  return {
    fail(text) {
      sound = null;
      message = text;
      show();
    },
  };
}

// Whether the browser can play the file, found by loading its metadata in a scratch element,
// so audio that can't play never replaces audio that can.
function playable(file) {
  return new Promise((resolve) => {
    const probe = new Audio();
    const url = URL.createObjectURL(file);
    const done = (ok) => {
      URL.revokeObjectURL(url);
      probe.removeAttribute("src");
      resolve(ok);
    };
    probe.addEventListener("loadedmetadata", () => done(true), { once: true });
    probe.addEventListener("error", () => done(false), { once: true });
    probe.preload = "metadata";
    probe.src = url;
  });
}
