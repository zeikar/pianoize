import { test } from "node:test";
import assert from "node:assert/strict";
import { coverCrop } from "../draw.js";

test("a picture wider than the area loses its sides equally", () => {
  const crop = coverCrop(3000, 1000, 2000, 1000);
  assert.deepEqual(crop, { x: 500, y: 0, w: 2000, h: 1000 });
});

test("a picture taller than the area loses its top and bottom equally", () => {
  const crop = coverCrop(1000, 1000, 2000, 1000);
  assert.deepEqual(crop, { x: 0, y: 250, w: 1000, h: 500 });
});

test("a picture of the area's shape is used whole, at any size", () => {
  assert.deepEqual(coverCrop(960, 440, 1920, 880), { x: 0, y: 0, w: 960, h: 440 });
});
