import test from "node:test";
import assert from "node:assert/strict";
import { EFFECTS, tune } from "../effects.js";
import { style } from "../style.js";

const at = (level) => Object.fromEntries(EFFECTS.map((name) => [name, level]));

test("every level at 1 is style.js's own values", () => {
  assert.deepEqual(tune(style, at(1)), style);
});

test("a level of 0 turns each effect off", () => {
  const off = tune(style, at(0));
  assert.ok(off.notes.glow.every(([, opacity]) => opacity === 0));
  assert.equal(off.flare.opacity, 0);
  assert.equal(off.beam.opacity, 0);
  assert.equal(off.sparks.burst, 0);
  assert.equal(off.sparks.rate, 0);
});

test("a level of 2 doubles each, the flare growing once it is at full opacity", () => {
  const twice = tune(style, at(2));
  assert.deepEqual(
    twice.notes.glow.map(([, opacity]) => opacity),
    style.notes.glow.map(([, opacity]) => 2 * opacity),
  );
  assert.equal(twice.flare.opacity, 1);
  assert.equal(twice.flare.width, style.flare.width * Math.SQRT2);
  assert.equal(twice.beam.opacity, 2 * style.beam.opacity);
  assert.equal(twice.sparks.burst, 2 * style.sparks.burst);
});

test("one effect's level leaves the others as they are", () => {
  const tuned = tune(style, { ...at(1), sparks: 0 });
  assert.deepEqual({ ...tuned, sparks: style.sparks }, style);
});
