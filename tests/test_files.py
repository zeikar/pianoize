import pytest

from pianoize import files


def test_a_directory_destination_leaves_every_output_as_it_was(tmp_path):
    first = tmp_path / "first.txt"
    first.write_text("old", encoding="utf-8")
    directory = tmp_path / "report"
    directory.mkdir()

    def save(text):
        return lambda path: path.write_text(text, encoding="utf-8")

    with pytest.raises(IsADirectoryError):
        files.write_all({first: save("new"), directory: save("new")})
    assert first.read_text(encoding="utf-8") == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["first.txt", "report"]
