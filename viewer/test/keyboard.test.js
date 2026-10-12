import test from "node:test";
import assert from "node:assert/strict";
import { keyLayout } from "../keyboard.js";
import { style } from "../style.js";

const W = 1040;
const keys = keyLayout(W, 800, 200, style.keyboard);
const at = (pitch) => keys.find((k) => k.pitch === pitch);
const whites = keys.filter((k) => !k.black);
const blacks = keys.filter((k) => k.black);

test("88 keys, 52 white and 36 black", () => {
  assert.equal(keys.length, 88);
  assert.equal(whites.length, 52);
  assert.equal(blacks.length, 36);
});

test("A0 starts at 0 and C8 ends at the width", () => {
  assert.equal(at(21).x, 0);
  assert.ok(Math.abs(at(108).x + at(108).w - W) < 1e-9);
});

test("white keys abut with the gap", () => {
  for (let i = 1; i < whites.length; i++) {
    const gap = whites[i].x - (whites[i - 1].x + whites[i - 1].w);
    assert.ok(Math.abs(gap - style.keyboard.gap) < 1e-9);
  }
});

test("black keys are narrower and shorter and sit inside the width", () => {
  for (const b of blacks) {
    assert.ok(b.w < whites[0].w);
    assert.ok(b.h < whites[0].h);
    assert.ok(b.x >= 0 && b.x + b.w <= W);
  }
});

test("60 is white, 61 is black", () => {
  assert.equal(at(60).black, false);
  assert.equal(at(61).black, true);
});

test("no black key right of E4 or B4", () => {
  // A black key is centred on a white boundary; E4-F4 and B4-C5 boundaries stay bare.
  const centres = blacks.map((b) => b.x + b.w / 2);
  for (const pitch of [65, 72]) {
    const boundary = at(pitch).x - style.keyboard.gap / 2;
    assert.ok(centres.every((c) => Math.abs(c - boundary) > 1e-6));
  }
});
