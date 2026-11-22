import { pressed, titleOpacity } from "./roll.js";
import { drawKeyboard } from "./keyboard.js";
import { drawNotes } from "./falling.js";
import { drawSparks, rgba } from "./sparks.js";

// The frame for video time t. data holds the notes, the key layout, the title card's lines and
// the timeline; every colour and size comes from style. The roll runs from 0 s, so the first notes
// fall in while the title card lies over it. A bare frame leaves the roll's background
// transparent, keeping only its octave lines, for the thumbnail to lay its own under it.
export function drawFrame(ctx, t, data, style, bare = false) {
  if (!bare) {
    ctx.fillStyle = style.background;
    ctx.fillRect(0, 0, style.width, style.height);
  }
  const tMusic = t - data.timeline.music_start;
  drawRoll(ctx, data.layout, style, data.background, bare);
  // The keys go over the notes, which slide under them, and the light where they meet goes
  // over both.
  drawNotes(ctx, data.notes, tMusic, data.layout, style);
  drawKeyboard(ctx, data.layout, pressed(data.notes, tMusic), style);
  drawSparks(ctx, data.notes, tMusic, data.layout, style);
  // The home page has no cards, and its music starts at 0 s.
  const opacity = titleOpacity(t, data.timeline, style.cards.fadeSeconds);
  if (opacity > 0 && data.cards) {
    ctx.save();
    ctx.globalAlpha = opacity;
    // Over the falling notes, the shadow keeps the lines readable.
    ctx.shadowColor = style.cards.shadow;
    ctx.shadowBlur = style.cards.shadowBlur;
    drawCard(ctx, data.cards.title, style, data.layout[0].y);
    ctx.restore();
  }
}

// The thumbnail, drawn at the frame's size for ffmpeg to scale down: the frame at its moment,
// zoomed in on the keys and centred on the notes, a dark band over its top, and the title card's
// lines on the band. The first line is the title, the last a tag in the right hand's light, and
// any between them a subtitle; a line too wide for the band shrinks to fit. A background picture
// is not zoomed with the frame: it spans the thumbnail's width from just under the lines, its top
// kept and its bottom cut at the keys, so the subject at its top is not hidden behind the title.
export function drawThumbnail(ctx, data, style) {
  const look = style.thumbnail;
  const { music_seconds, pitch } = data.thumbnail;
  const lines = thumbnailLines(ctx, data.cards.title, style);
  const w = style.width / look.zoom;
  const h = style.height / look.zoom;
  const key = data.layout.find((k) => k.pitch === pitch);
  const x = Math.min(Math.max(key.x + key.w / 2 - w / 2, 0), style.width - w);
  const bare = Boolean(data.background);
  const frame = document.createElement("canvas");
  frame.width = style.width;
  frame.height = style.height;
  const fctx = frame.getContext("2d");
  if (bare) {
    // The picture goes into the frame before the notes, so their glow adds light to it as in
    // the video; drawn in the thumbnail's own coordinates, which the zoom below maps back.
    fctx.fillStyle = style.background;
    fctx.fillRect(0, 0, style.width, style.height);
    fctx.setTransform(1 / look.zoom, 0, 0, 1 / look.zoom, x, style.height - h);
    const rollHeight = (data.layout[0].y - (style.height - h)) * look.zoom;
    drawThumbnailPicture(fctx, data.background.image, style, lines, rollHeight);
    fctx.setTransform(1, 0, 0, 1, 0, 0);
  }
  drawFrame(fctx, data.timeline.music_start + music_seconds, data, style, bare);
  ctx.drawImage(frame, x, style.height - h, w, h, 0, 0, style.width, style.height);

  const band = ctx.createLinearGradient(0, 0, 0, look.band.height);
  band.addColorStop(0, look.band.top);
  band.addColorStop(0.7, look.band.middle);
  band.addColorStop(1, look.band.end);
  ctx.fillStyle = band;
  ctx.fillRect(0, 0, style.width, look.band.height);

  ctx.save();
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.shadowColor = look.shadow;
  ctx.shadowBlur = look.shadowBlur;
  for (const line of lines) {
    ctx.font = line.font;
    ctx.fillStyle = line.colour;
    ctx.fillText(line.text, style.width / 2, line.y + line.size / 2);
  }
  ctx.restore();
}

// The background picture on the thumbnail, in its coordinates: the thumbnail's width from just
// under the title card's lines down to the keys, its top kept and faded in from the dark, under
// the roll's light.
function drawThumbnailPicture(ctx, picture, style, lines, rollHeight) {
  const look = style.thumbnail;
  const top = lines.at(-1).y + lines.at(-1).size;
  if (top >= rollHeight) return; // the lines reach the keys: no room for it
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, top, style.width, rollHeight - top);
  ctx.clip();
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(picture, 0, top, style.width, (picture.height * style.width) / picture.width);
  const fade = ctx.createLinearGradient(0, top, 0, top + look.pictureFade);
  fade.addColorStop(0, style.background);
  fade.addColorStop(1, rgba(style.background, 0));
  ctx.fillStyle = fade;
  ctx.fillRect(0, top, style.width, look.pictureFade);
  ctx.restore();
  drawLight(ctx, style.roll.over, style.width, rollHeight);
}

// The title card's lines as the thumbnail sets them: each one's text, font, colour, size and top.
function thumbnailLines(ctx, lines, style) {
  const look = style.thumbnail;
  let y = look.top;
  return lines.map((text, i) => {
    const kind = i === 0 ? look.title : i === lines.length - 1 ? look.tag : look.subtitle;
    const font = (size) => `${kind.weight} ${size}px ${style.cards.fontFamily}`;
    ctx.font = font(kind.size);
    const width = ctx.measureText(text).width;
    const size = width > look.maxWidth ? Math.floor((kind.size * look.maxWidth) / width) : kind.size;
    const line = { text, font: font(size), colour: kind.colour, size, y };
    y += size + look.lineGap;
    return line;
  });
}

// The roll's background above the keys: its light, over the run's picture if it has one, and a
// line up from each C. A bare roll has only the lines.
function drawRoll(ctx, layout, style, background, bare) {
  const keyboardTop = layout[0].y;
  if (!bare) {
    if (background) drawPicture(ctx, background.roll, style, style.width, keyboardTop);
    else drawLight(ctx, style.roll, style.width, keyboardTop);
  }
  ctx.fillStyle = style.roll.octaveLine;
  const width = style.roll.octaveLineWidth;
  for (const k of layout) {
    if (k.pitch % 12 === 0) ctx.fillRect(Math.round(k.x - width / 2), 0, width, keyboardTop);
  }
}

// The background picture filling a width × height area at the top left, under the roll's light
// laid over it. The picture comes scaled to the roll, so it is drawn whole there.
function drawPicture(ctx, picture, style, width, height) {
  const { x, y, w, h } = coverCrop(picture.width, picture.height, width, height);
  ctx.drawImage(picture, x, y, w, h, 0, 0, width, height);
  drawLight(ctx, style.roll.over, width, height);
}

// The roll's light, from its top colour down to its bottom one, over a width × height area.
function drawLight(ctx, light, width, height) {
  const g = ctx.createLinearGradient(0, 0, 0, height);
  g.addColorStop(0, light.top);
  g.addColorStop(1, light.bottom);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, width, height);
}

// The lines centred as a block in the frame's top `area` pixels: the first at the title size,
// the rest at the line size.
function drawCard(ctx, lines, style, area) {
  const { cards } = style;
  const sizes = lines.map((_, i) => (i === 0 ? cards.titleSize : cards.lineSize));
  const height = sizes.reduce((sum, size) => sum + size, 0) + cards.lineGap * (lines.length - 1);
  let y = (area - height) / 2;
  ctx.fillStyle = cards.colour;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  lines.forEach((line, i) => {
    ctx.font = `${sizes[i]}px ${cards.fontFamily}`;
    ctx.fillText(line, style.width / 2, y + sizes[i] / 2);
    y += sizes[i] + cards.lineGap;
  });
}

// The part of a width × height picture that fills an area of areaWidth × areaHeight without
// stretching: all of it one way, the middle of it the other.
export function coverCrop(width, height, areaWidth, areaHeight) {
  const scale = Math.max(areaWidth / width, areaHeight / height);
  const w = areaWidth / scale;
  const h = areaHeight / scale;
  return { x: (width - w) / 2, y: (height - h) / 2, w, h };
}
