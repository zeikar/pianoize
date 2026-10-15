// The player's controls over the audio element, which is the page's clock: play and pause, the
// time, and a seek bar. A click on the picture plays or pauses, and so does Space; the arrow
// keys seek 5 s.
const SEEK_SECONDS = 5;

export function transport(root, audio, picture) {
  const play = root.querySelector(".play");
  const time = root.querySelector(".time");
  const seek = root.querySelector(".seek");

  const toggle = () => {
    if (!audio.paused) return audio.pause();
    // A rejected play is audio the browser can't decode, which the audio's error event
    // reports.
    audio.play().catch(() => {});
  };
  play.addEventListener("click", toggle);
  picture.addEventListener("click", () => {
    if (!play.disabled) toggle();
  });
  seek.addEventListener("input", () => {
    audio.currentTime = Number(seek.value);
  });
  document.addEventListener("keydown", (e) => {
    if (play.disabled || e.metaKey || e.ctrlKey || e.altKey) return;
    // Another field's keys stay its own, and so does Space on a button or a link, so Play's
    // click is the toggle there. The seek bar's keys are the player's.
    const field = e.target.closest("input, select, textarea");
    if (field && field !== seek) return;
    if (e.key === " " && e.target.closest("button, a")) return;
    if (e.key === " ") toggle();
    else if (e.key === "ArrowLeft") audio.currentTime -= SEEK_SECONDS;
    else if (e.key === "ArrowRight") audio.currentTime += SEEK_SECONDS;
    else return;
    e.preventDefault();
  });

  const playing = () => {
    play.toggleAttribute("data-playing", !audio.paused);
    play.setAttribute("aria-label", audio.paused ? "Play" : "Pause");
  };
  // On the audio's events, so Play is enabled before any later listener for the same event.
  const ready = () => {
    const known = Number.isFinite(audio.duration);
    play.disabled = seek.disabled = !known;
    seek.max = known ? audio.duration : 0;
    playing();
  };
  for (const name of ["play", "pause", "loadedmetadata", "durationchange", "emptied"]) {
    audio.addEventListener(name, ready);
  }
  ready();

  // The time and the seek bar follow the audio on every animation frame, so the bar moves
  // smoothly while it plays. A drag sets currentTime at once, so the thumb stays under it.
  const frame = () => {
    const duration = Number(seek.max);
    const now = Math.min(audio.currentTime, duration);
    seek.value = now;
    seek.style.setProperty("--progress", `${duration ? (now / duration) * 100 : 0}%`);
    const text = `${clock(now)} / ${clock(duration)}`;
    if (time.textContent !== text) time.textContent = text;
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}

function clock(seconds) {
  const s = Math.floor(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
