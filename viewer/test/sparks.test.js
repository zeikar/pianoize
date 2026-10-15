import test from "node:test";
import assert from "node:assert/strict";
import { sparks, flareScale } from "../sparks.js";
import { keyLayout } from "../keyboard.js";
import { style } from "../style.js";

const TOP = 880;
const layout = keyLayout(1920, TOP, 200, style.keyboard);
const p = style.sparks;
const note = { pitch: 60, hand: "right", on: 1, off: 2 };
const at = (t, notes = [note]) => sparks(notes, t, layout, TOP, p);

test("no sparks before the note-on", () => {
  assert.deepEqual(at(0.999), []);
});

test("the burst is there at the note-on, at the key's top", () => {
  const born = at(1);
  assert.equal(born.length, p.burst + 1);
  const key = layout.find((k) => k.pitch === 60);
  for (const s of born) {
    assert.ok(s.x >= key.x && s.x <= key.x + key.w, s.x);
    assert.equal(s.y, TOP);
    assert.equal(s.opacity, 1);
  }
});

test("the same time gives the same sparks, in any order", () => {
  const later = at(1.5);
  at(1.2);
  assert.deepEqual(at(1.5), later);
});

test("sparks fly up and fade", () => {
  for (const s of at(1.3)) {
    assert.ok(s.y < TOP, s.y);
    assert.ok(s.opacity > 0 && s.opacity < 1, s.opacity);
  }
});

test("the stream stops at the note-off and the last sparks die within a life", () => {
  assert.ok(at(2 + p.life / 2).length > 0);
  assert.deepEqual(at(2 + p.life), []);
});

test("the notes of a chord spark differently, and each as it does alone", () => {
  const other = { ...note, pitch: 64 };
  const both = at(1.3, [note, other]);
  const alone = at(1.3, [note]);
  assert.deepEqual(both.slice(0, alone.length), alone);
  const ys = (sparks) => sparks.map((s) => s.y);
  assert.notDeepEqual(ys(both.slice(alone.length)), ys(alone));
});

test("the flare flashes at the note-on and settles", () => {
  assert.equal(flareScale(note, 1, style.flare), 1 + style.flare.flash);
  assert.ok(flareScale(note, 1.9, style.flare) < 1.01);
});
