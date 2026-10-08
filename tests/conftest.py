import json
from collections.abc import Callable
from pathlib import Path

import mido
import pytest

from pianoize import synthetic
from pianoize.synthetic import Progression


@pytest.fixture
def make_timeline() -> Callable[..., dict]:
    return synthetic.timeline


@pytest.fixture
def make_midi() -> Callable[..., mido.MidiFile]:
    return synthetic.midi


@pytest.fixture
def write_timeline(tmp_path: Path) -> Callable[..., Path]:
    def write(progression: Progression, name: str = "timeline.json", **kwargs) -> Path:
        path = tmp_path / name
        path.write_text(json.dumps(synthetic.timeline(progression, **kwargs)), encoding="utf-8")
        return path

    return write
