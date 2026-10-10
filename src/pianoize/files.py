"""Writing outputs so that a failed run leaves every existing file as it was."""

import tempfile
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path


def write_all(outputs: dict[Path, Callable[[Path], None]]) -> None:
    """Save each output with its function to a scratch file beside it, then replace them in turn.
    A save that fails leaves every output as it was. Each scratch directory sits beside its
    destination, on the same filesystem, so each replace is atomic."""
    with ExitStack() as stack:
        partials = []
        for out, save in outputs.items():
            scratch = stack.enter_context(
                tempfile.TemporaryDirectory(dir=out.parent, prefix=".pianoize-")
            )
            partial = Path(scratch) / out.name
            save(partial)
            partials.append((partial, out))
        for partial, out in partials:
            partial.replace(out)
