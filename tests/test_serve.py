import urllib.error
import urllib.request

import numpy as np
import pytest
from typer.testing import CliRunner

from pianoize import serve, video
from pianoize.cli import app


@pytest.fixture
def server(tmp_path):
    viewer = tmp_path / "viewer"
    run = tmp_path / "run"
    viewer.mkdir()
    run.mkdir()
    (viewer / "index.html").write_text("<p>hi</p>")
    (viewer / "main.js").write_text("export {};")
    (run / "manifest.json").write_text("{}")
    (tmp_path / "secret").write_text("no")
    (viewer / "secret").write_text("no")
    started = serve.start(viewer, run)
    yield started
    serve.stop(started)


def get(server, path):
    with urllib.request.urlopen(serve.url(server).rstrip("/") + path) as response:
        return response.status, response.headers.get_content_type(), response.read()


def test_serves_the_viewer_and_the_run_directory(server):
    assert get(server, "/")[:2] == (200, "text/html")
    assert get(server, "/main.js")[:2] == (200, "text/javascript")
    assert get(server, "/run/manifest.json")[:2] == (200, "application/json")


def test_the_queue_takes_every_file_the_page_asks_for_at_once(server):
    # A queue shorter than the page's files reset some of their connections, and the page never
    # started; twice the files leaves room for the page to grow.
    page = [*video.VIEWER.glob("*.js"), *video.VIEWER.glob("*.css"), video.VIEWER / "index.html"]
    assert server.request_queue_size >= 2 * len(page)


def test_sends_no_store(server):
    with urllib.request.urlopen(serve.url(server) + "run/manifest.json") as response:
        assert response.headers["Cache-Control"] == "no-store"


def _get_with_host(server, host):
    request = urllib.request.Request(
        serve.url(server) + "run/manifest.json", headers={"Host": host}
    )
    return urllib.request.urlopen(request)


def test_refuses_a_foreign_host(server):
    with pytest.raises(urllib.error.HTTPError) as caught:
        _get_with_host(server, f"evil.example:{server.server_address[1]}")

    assert caught.value.code == 403


@pytest.mark.parametrize("name", ["127.0.0.1", "localhost"])
def test_accepts_the_loopback_host(server, name):
    assert _get_with_host(server, f"{name}:{server.server_address[1]}").status == 200


def test_serves_the_real_viewer_page(tmp_path):
    started = serve.start(video.VIEWER, tmp_path)
    try:
        status, kind, body = get(started, "/")
    finally:
        serve.stop(started)

    assert (status, kind) == (200, "text/html")
    assert body == (video.VIEWER / "index.html").read_bytes()


@pytest.mark.parametrize("path", ["/run/../secret", "/run/%2e%2e/secret", "/../secret"])
def test_a_traversal_is_a_404(server, path):
    with pytest.raises(urllib.error.HTTPError) as caught:
        get(server, path)

    assert caught.value.code == 404


def test_binds_to_loopback_and_stops(server):
    assert server.server_address[0] == "127.0.0.1"
    serve.stop(server)

    with pytest.raises(urllib.error.URLError):
        get(server, "/")


@pytest.fixture
def preview(tmp_path, monkeypatch, fake_fluidsynth, hands_midi):
    midi = tmp_path / "arranged.mid"
    hands_midi([(0, 480, 72, 80)], [(0, 480, 48, 80)]).save(midi)
    cards = tmp_path / "cards.txt"
    cards.write_text("Title\n---\nCredits\n", encoding="utf-8")
    font = tmp_path / "font.sf2"
    font.write_bytes(b"")
    monkeypatch.setattr(serve, "wait", lambda server: serve.stop(server))

    def run(*extra):
        args = ["preview-video", str(midi), "--cards", str(cards), "--soundfont", str(font)]
        return CliRunner().invoke(app, [*args, *extra])

    run.tmp = tmp_path
    run.cards = cards
    return run


def test_preview_video_serves_and_cleans_up(preview, fake_fluidsynth):
    result = preview("--gain", "0.3")

    assert result.exit_code == 0, result.output
    assert "http://127.0.0.1:" in result.output
    assert fake_fluidsynth.calls[0]["gain"] == 0.3
    assert not list(preview.tmp.glob(".preview-*"))


def test_preview_video_warns_on_clipping(preview, fake_fluidsynth):
    fake_fluidsynth.clip = np.clip(fake_fluidsynth.clip * 2, -1, 1)

    result = preview()

    assert result.exit_code == 0, result.output
    assert "may clip" in result.output


def test_preview_video_refuses_an_empty_title_card(preview, fake_fluidsynth):
    preview.cards.write_text("\n---\nCredits\n", encoding="utf-8")

    result = preview()

    assert result.exit_code == 1
    assert "error:" in result.output
    assert fake_fluidsynth.calls == []
    assert not list(preview.tmp.glob(".preview-*"))
