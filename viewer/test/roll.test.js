import test from "node:test";
import assert from "node:assert/strict";
import { FORMAT_VERSION, load, phase, pressed, noteRects } from "../roll.js";
import { keyLayout } from "../keyboard.js";
import { style } from "../style.js";

const FALL = 3;
const TOP = 0;
const BOTTOM = 880;
const layout = keyLayout(1920, BOTTOM, 200, style.keyboard);
const rects = (notes, t) => noteRects(notes, t, layout, TOP, BOTTOM, FALL, style.notes);

test("load accepts version 1 and returns the notes", () => {
  const notes = [{ pitch: 60, hand: "right", on: 0, off: 1 }];
  assert.deepEqual(load({ format_version: FORMAT_VERSION, notes }), notes);
});

test("load rejects version 2 naming both versions", () => {
  assert.throws(() => load({ format_version: 2, notes: [] }), /2.*1/);
});

test("phase at each boundary", () => {
  const tl = { music_start: 6, music_end: 20, end: 26 };
  assert.equal(phase(0, tl, FALL), "title");
  assert.equal(phase(2.99, tl, FALL), "title");
  assert.equal(phase(3, tl, FALL), "roll");
  assert.equal(phase(19.99, tl, FALL), "roll");
  assert.equal(phase(20, tl, FALL), "credits");
});

test("pressed with one note and after its end", () => {
  const notes = [{ pitch: 60, hand: "right", on: 1, off: 2 }];
  assert.deepEqual([...pressed(notes, 1.5)], [[60, "right"]]);
  assert.equal(pressed(notes, 0.5).size, 0);
  assert.equal(pressed(notes, 2).size, 0);
});

test("pressed: the latest onset wins an overlap of both hands", () => {
  const notes = [
    { pitch: 60, hand: "right", on: 1, off: 3 },
    { pitch: 60, hand: "left", on: 2, off: 4 },
  ];
  assert.equal(pressed(notes, 1.5).get(60), "right");
  assert.equal(pressed(notes, 2.5).get(60), "left");
  assert.equal(pressed(notes.toReversed(), 2.5).get(60), "left");
});

test("a note due in half the fall time sits halfway down", () => {
  const [r] = rects([{ pitch: 60, hand: "right", on: FALL / 2, off: FALL / 2 + 100 }], 0);
  assert.equal(r.y, TOP);
  assert.equal(r.y + r.h, BOTTOM / 2);
});

test("a note's bottom is at the keyboard at its onset", () => {
  const [r] = rects([{ pitch: 60, hand: "right", on: 1, off: 2 }], 1);
  assert.equal(r.y + r.h, BOTTOM);
});

test("a note is clamped and shrinking between on and off, and gone at off", () => {
  const n = [{ pitch: 60, hand: "right", on: 1, off: 2 }];
  const early = rects(n, 1.2)[0];
  const late = rects(n, 1.8)[0];
  assert.equal(early.y + early.h, BOTTOM);
  assert.equal(late.y + late.h, BOTTOM);
  assert.ok(late.h < early.h);
  assert.equal(rects(n, 2).length, 0);
});

test("a note more than the fall time away is not returned", () => {
  const n = [{ pitch: 60, hand: "right", on: FALL, off: FALL + 1 }];
  assert.equal(rects(n, 0).length, 0);
  assert.equal(rects(n, 0.1).length, 1);
});

test("a black-key note takes the black key's lane", () => {
  const [r] = rects([{ pitch: 61, hand: "left", on: 1, off: 2 }], 0);
  const key = layout.find((k) => k.pitch === 61);
  assert.equal(r.x, key.x + style.notes.inset);
  assert.equal(r.w, key.w - 2 * style.notes.inset);
});
