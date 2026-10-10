"""Correction specs: an agent's verdicts and edits on a cover, validated and applied
deterministically. The format is in docs/polishing.md."""

import copy
import hashlib
import json
import math
import re
import tempfile
from dataclasses import dataclass
from itertools import accumulate, pairwise
from pathlib import Path
from typing import NamedTuple

import mido

from . import notes
from .melody import _DRUM_CHANNEL

SPEC_VERSION = 1

_FIELDS = ("on_tick", "off_tick", "pitch", "velocity")
_TAKES = {"delete": ("note",), "modify": ("note", *_FIELDS), "add": ("id", *_FIELDS)}
_NEEDS = {"delete": ("note",), "modify": ("note",), "add": ("id", *_FIELDS)}
_BOUNDS = {"on_tick": (0, None), "off_tick": (0, None), "pitch": (0, 127), "velocity": (1, 127)}
_ADD_ID = re.compile(r"[A-Za-z0-9_-]+")
_KEYS = {"spec_version", "inputs", "verdicts", "edits"}

# Sort slots within one tick: see _rebuild.
_KEPT_BEFORE_ON, _EDITED_OFF, _KEPT_FROM_ON, _EDITED_ON = range(4)


class CorrectionError(ValueError):
    pass


@dataclass(frozen=True)
class Verdict:
    candidate: str
    time: float  # seconds, the candidate's time as the finder gave it
    action: str  # fix | keep
    reason: str


@dataclass(frozen=True)
class Edit:
    op: str  # delete | modify | add
    candidate: str
    reason: str
    note: str | None = None  # the cover note a delete or modify changes
    id: str | None = None  # an add's: later finder runs call its note add-{id}
    on_tick: int | None = None  # a modify keeps the note's value where these are None
    off_tick: int | None = None
    pitch: int | None = None
    velocity: int | None = None


@dataclass(frozen=True)
class Spec:
    verdicts: list[Verdict]
    edits: list[Edit]


class _Sounding(NamedTuple):
    on_tick: int
    off_tick: int
    pitch: int
    origin: str  # the cover note's id, or add-{id}
    edit: int | None  # the index of the edit that placed it


def sha256(path: str | Path) -> str:
    with open(path, "rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def _object(value, where: str) -> dict:
    if not isinstance(value, dict):
        raise CorrectionError(f"{where} must be an object")
    return value


def _require(item: dict, keys: tuple[str, ...], where: str) -> None:
    for key in keys:
        if key not in item:
            raise CorrectionError(f"{where} is missing {key!r}")


def _text(item: dict, key: str, where: str) -> str:
    value = item[key]
    if not isinstance(value, str) or not value.strip():
        raise CorrectionError(f"{where}: {key} must be a non-empty string")
    return value


def _integer(item: dict, key: str, where: str) -> int | None:
    if key not in item:
        return None
    value = item[key]
    low, high = _BOUNDS[key]
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < low
        or (high is not None and value > high)
    ):
        bounds = f"{low} or more" if high is None else f"{low}-{high}"
        raise CorrectionError(f"{where}: {key} must be an integer {bounds}, not {value!r}")
    return value


def _verdict(item, where: str) -> Verdict:
    item = _object(item, where)
    _require(item, ("candidate", "time", "action", "reason"), where)
    time = item["time"]
    if isinstance(time, bool) or not isinstance(time, int | float) or not math.isfinite(time):
        raise CorrectionError(f"{where}: time must be a finite number of seconds, not {time!r}")
    if item["action"] not in ("fix", "keep"):
        raise CorrectionError(f"{where}: action must be fix or keep")
    return Verdict(
        _text(item, "candidate", where), float(time), item["action"], _text(item, "reason", where)
    )


def _edit(item, where: str) -> Edit:
    item = _object(item, where)
    _require(item, ("op",), where)
    op = item["op"]
    if not isinstance(op, str) or op not in _TAKES:
        raise CorrectionError(f"{where}: op must be delete, modify or add")
    extra = sorted(set(item) - {"op", "candidate", "reason", *_TAKES[op]})
    if extra:
        raise CorrectionError(f"{where}: {op} does not take {', '.join(extra)}")
    _require(item, ("candidate", "reason", *_NEEDS[op]), where)
    added = _text(item, "id", where) if op == "add" else None
    if added is not None and not _ADD_ID.fullmatch(added):
        raise CorrectionError(f"{where}: id must match {_ADD_ID.pattern}")
    return Edit(
        op,
        _text(item, "candidate", where),
        _text(item, "reason", where),
        note=None if op == "add" else _text(item, "note", where),
        id=added,
        **{key: _integer(item, key, where) for key in _FIELDS},
    )


def _list(data: dict, key: str) -> list:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise CorrectionError(f"{key} must be a list")
    return value


def _read_midi(path: str | Path) -> mido.MidiFile:
    try:
        return mido.MidiFile(path)
    except (OSError, EOFError, ValueError) as exc:
        raise CorrectionError(f"{path}: cannot read MIDI: {exc}") from exc


def _after(edit: Edit, note: notes.Note | None) -> tuple[int, int, int, int]:
    """(on_tick, off_tick, pitch, velocity) of the note an add or modify leaves."""
    return tuple(
        getattr(note, key) if getattr(edit, key) is None else getattr(edit, key) for key in _FIELDS
    )


def _sounding(cover_notes: list[notes.Note], edits: list[Edit]) -> list[_Sounding]:
    """Every note once the edits are made."""
    by_id = {note.id: note for note in cover_notes}
    edited = {edit.note for edit in edits}
    found = [
        _Sounding(n.on_tick, n.off_tick, n.pitch, n.id, None)
        for n in cover_notes
        if n.id not in edited
    ]
    for index, edit in enumerate(edits):
        if edit.op != "delete":
            on_tick, off_tick, pitch, _ = _after(edit, by_id.get(edit.note))
            origin = edit.note if edit.op == "modify" else f"add-{edit.id}"
            found.append(_Sounding(on_tick, off_tick, pitch, origin, index))
    return found


def _check_overlaps(sounding: list[_Sounding]) -> None:
    # Sorted by pitch and onset, any overlap or shared id shows between neighbours. The cover's own
    # notes never overlap and have unique ids, so an edit placed at least one of the two.
    ordered = sorted(sounding, key=lambda n: (n.pitch, n.on_tick, n.off_tick))
    for previous, note in pairwise(ordered):
        if previous.pitch != note.pitch:
            continue
        if note.on_tick == previous.on_tick:  # also a zero-length note: the ids would collide
            clash = "start"
        elif note.on_tick < previous.off_tick:
            clash = "sound"
        else:
            continue
        index = max(i for i in (previous.edit, note.edit) if i is not None)
        raise CorrectionError(
            f"edits[{index}]: {previous.origin} and {note.origin} would both {clash} pitch "
            f"{note.pitch} at tick {note.on_tick}"
        )


def _check(
    verdicts: list[Verdict], edits: list[Edit], cover_notes: list[notes.Note], guarded: set[str]
) -> None:
    judged: dict[str, int] = {}
    for index, verdict in enumerate(verdicts):
        if verdict.candidate in judged:
            raise CorrectionError(
                f"verdicts[{index}]: candidate {verdict.candidate} already has a verdict "
                f"(verdicts[{judged[verdict.candidate]}])"
            )
        judged[verdict.candidate] = index
    fixes = {verdict.candidate for verdict in verdicts if verdict.action == "fix"}
    by_id = {note.id: note for note in cover_notes}
    edited: dict[str, int] = {}
    added: dict[str, int] = {}
    for index, edit in enumerate(edits):
        where = f"edits[{index}]"
        if edit.candidate not in fixes:
            raise CorrectionError(f"{where}: candidate {edit.candidate} has no fix verdict")
        note = None
        if edit.op == "add":
            if edit.id in added:
                raise CorrectionError(f"{where}: id {edit.id} is taken by edits[{added[edit.id]}]")
            added[edit.id] = index
        else:
            note = by_id.get(edit.note)
            if note is None:
                raise CorrectionError(f"{where}: unknown note {edit.note}")
            if edit.note in edited:
                raise CorrectionError(
                    f"{where}: note {edit.note} already has an edit (edits[{edited[edit.note]}])"
                )
            edited[edit.note] = index
        if edit.op == "delete":
            continue
        on_tick, off_tick, pitch, _ = after = _after(edit, note)
        if note is not None and after == tuple(getattr(note, key) for key in _FIELDS):
            raise CorrectionError(f"{where}: modify changes nothing on {edit.note}")
        if off_tick <= on_tick:
            raise CorrectionError(f"{where}: off_tick {off_tick} must be after on_tick {on_tick}")
        if note is not None and pitch != note.pitch and note.id in guarded:
            raise CorrectionError(
                f"{where}: note {note.id} carries the melody, so its pitch stays {note.pitch}"
            )
    _check_overlaps(_sounding(cover_notes, edits))


def load(path: str | Path, cover_path: str | Path, melody_path: str | Path) -> Spec:
    """Read and validate a correction spec against the cover and tsumugi's melody MIDI it was
    written for; see docs/polishing.md for the rules."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:  # also undecodable bytes
        raise CorrectionError(f"{path}: not valid JSON ({exc})") from exc
    data = _object(data, str(path))
    extra = sorted(set(data) - _KEYS)
    if extra:
        raise CorrectionError(f"the spec does not take {', '.join(extra)}")
    version = data.get("spec_version")
    if isinstance(version, bool) or version != SPEC_VERSION:
        raise CorrectionError(f"spec_version must be {SPEC_VERSION}, not {version!r}")
    inputs = _object(data.get("inputs"), "inputs")
    for name, file in (("cover", cover_path), ("melody", melody_path)):
        digest = sha256(file)
        if _object(inputs.get(name), f"inputs.{name}").get("sha256") != digest:
            raise CorrectionError(f"inputs.{name}: sha256 does not match {file} ({digest})")
    verdicts = [_verdict(item, f"verdicts[{i}]") for i, item in enumerate(_list(data, "verdicts"))]
    edits = [_edit(item, f"edits[{i}]") for i, item in enumerate(_list(data, "edits"))]

    cover = _read_midi(cover_path)
    try:
        check_cover(cover)
    except CorrectionError as exc:
        raise CorrectionError(f"{cover_path}: {exc}") from exc
    cover_notes = notes.read(cover)
    guarded = notes.protected(cover_notes, notes.read(_read_midi(melody_path)))
    _check(verdicts, edits, cover_notes, guarded)
    return Spec(verdicts, edits)


def check_cover(midi: mido.MidiFile) -> None:
    """Raise CorrectionError unless the cover can be edited: its notes on one track and channel,
    no two sharing an id, and every note ended by its own note-off."""
    try:
        notes.check_editable(midi)
    except notes.NoteError as exc:
        raise CorrectionError(str(exc)) from exc
    for track in midi.tracks:
        _note_messages(track)


def _is_note_on(message: mido.Message) -> bool:
    return message.type == "note_on" and message.velocity > 0


def _note_messages(track: mido.MidiTrack) -> dict[str, tuple[int, int]]:
    """Each note's id -> the indexes of its note-on and note-off.

    A note ended by a strike of its pitch or by the end of the track is refused: an edit that
    moved that strike or the track's end would silently change the note's length.
    """
    found: dict[str, tuple[int, int]] = {}
    for on_index, off_index, on_tick, _ in notes.pairs(track):
        note_id = notes.note_id(on_tick, track[on_index].note)
        if off_index is None:
            raise CorrectionError(
                f"note {note_id} has no note-off of its own: a strike of its pitch or the end of "
                "the track ends it"
            )
        found[note_id] = (on_index, off_index)
    return found


def _rebuild(
    track: mido.MidiTrack, removed: set[int], placed: list[tuple[int, int, int, mido.Message]]
) -> mido.MidiTrack:
    """The track without the removed messages, plus the placed (tick, slot, pitch, message).

    Kept messages keep their order. At one tick an edited note-off goes before the first kept
    note-on and an edited note-on after everything kept, so a note ending where another of its
    pitch starts stays paired with its own note-on. end_of_track stays last, pushed to the last
    message if an edit now ends later.
    """
    end = track[-1] if track and track[-1].type == "end_of_track" else None
    body = len(track) - 1 if end is not None else len(track)
    ticks = list(accumulate(message.time for message in track))
    kept = [index for index in range(body) if index not in removed]
    first_on: dict[int, int] = {}
    for index in kept:
        if _is_note_on(track[index]):
            first_on.setdefault(ticks[index], index)
    events = [
        (
            ticks[index],
            _KEPT_BEFORE_ON if index < first_on.get(ticks[index], body) else _KEPT_FROM_ON,
            index,
            track[index],
        )
        for index in kept
    ]
    rebuilt = mido.MidiTrack()
    now = 0
    for tick, _, _, message in sorted(events + placed, key=lambda event: event[:3]):
        rebuilt.append(message.copy(time=tick - now))
        now = tick
    if end is not None:
        rebuilt.append(end.copy(time=max(ticks[-1] - now, 0)))
    return rebuilt


def apply(midi: mido.MidiFile, spec: Spec) -> tuple[mido.MidiFile, dict[str, str]]:
    """The cover with the spec's edits made, on a copy, and every note id of the result mapped to
    its origin: its id in the cover, or add-{id}. `midi` is the cover the spec was loaded for."""
    out = copy.deepcopy(midi)
    cover_notes = notes.read(midi)
    by_id = {note.id: note for note in cover_notes}
    channel = cover_notes[0].channel if cover_notes else 0
    index = next(
        (
            i
            for i, track in enumerate(out.tracks)
            if any(m.type == "note_on" and m.channel != _DRUM_CHANNEL for m in track)
        ),
        0,
    )
    track = out.tracks[index]
    ends = _note_messages(track)
    removed: set[int] = set()
    placed: list[tuple[int, int, int, mido.Message]] = []
    for edit in spec.edits:
        if edit.op != "add":
            on_index, off_index = ends[edit.note]
            removed |= {on_index, off_index}
        if edit.op == "delete":
            continue
        on_tick, off_tick, pitch, velocity = _after(edit, by_id.get(edit.note))
        if edit.op == "modify":
            on = track[on_index].copy(note=pitch, velocity=velocity)
            off = track[off_index].copy(note=pitch)
        else:
            on = mido.Message("note_on", channel=channel, note=pitch, velocity=velocity)
            off = mido.Message("note_off", channel=channel, note=pitch, velocity=0)
        placed += [(off_tick, _EDITED_OFF, pitch, off), (on_tick, _EDITED_ON, pitch, on)]
    out.tracks[index] = _rebuild(track, removed, placed)
    identity = {
        notes.note_id(n.on_tick, n.pitch): n.origin for n in _sounding(cover_notes, spec.edits)
    }
    return out, identity


def write(midi: mido.MidiFile, out: Path) -> None:
    # The scratch directory sits beside the destination, so the replace is atomic and a failed
    # write leaves any existing file as it was.
    with tempfile.TemporaryDirectory(dir=out.parent, prefix=".corrections-") as tmp:
        partial = Path(tmp) / "out.mid"
        midi.save(partial)
        partial.replace(out)
