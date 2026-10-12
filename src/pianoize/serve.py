"""A local HTTP server for the viewer page: Chrome refuses ES modules from file://."""

import functools
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

_RUN = "/run/"


class _Handler(SimpleHTTPRequestHandler):
    # Fixed here so the types do not depend on the system's mime.types.
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".json": "application/json",
    }

    def __init__(self, *args, viewer_dir: Path, run_dir: Path, **kwargs) -> None:
        self._viewer = viewer_dir.resolve()
        self._run = run_dir.resolve()
        super().__init__(*args, **kwargs)

    def translate_path(self, path: str) -> str:
        path = unquote(urlsplit(path).path)
        if path.startswith(_RUN):
            root, relative = self._run, path[len(_RUN) :]
        else:
            root, relative = self._viewer, path.lstrip("/")
        target = (root / relative).resolve()
        if not target.is_relative_to(root):
            return str(root / ".not-found")  # a path that is not there, so the handler says 404
        return str(target)

    def end_headers(self) -> None:
        # The song's notes and audio must not be left in a browser's disk cache.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_head(self):
        # A page on another origin can reach 127.0.0.1 by DNS rebinding; its Host is not ours.
        port = self.server.server_address[1]
        if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            self.send_error(403)
            return None
        return super().send_head()

    def log_message(self, format: str, *args) -> None:
        pass


def start(viewer_dir: Path, run_dir: Path, port: int = 0) -> ThreadingHTTPServer:
    """Serve `viewer_dir` at / and `run_dir` at /run/ on 127.0.0.1; port 0 picks a free one."""
    handler = functools.partial(_Handler, viewer_dir=viewer_dir, run_dir=run_dir)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def url(server: ThreadingHTTPServer) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}/"


def stop(server: ThreadingHTTPServer) -> None:
    server.shutdown()
    server.server_close()


def wait(server: ThreadingHTTPServer) -> None:
    """Sleep until Ctrl-C, then stop the server."""
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        stop(server)
