"""Explicit local media preview; never started by McPet's MCP service."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8769)
    parser.add_argument("--frying-video", type=Path, required=True)
    parser.add_argument("--outfit-video", type=Path, required=True)
    args = parser.parse_args()
    routes = {
        "/": (ROOT / "docs/demos/actions.html", "text/html; charset=utf-8"),
        "/assets/maimai-actions/frying.gif": (ROOT / "assets/maimai-actions/frying.gif", "image/gif"),
        "/assets/maimai-actions/outfit.gif": (ROOT / "assets/maimai-actions/outfit.gif", "image/gif"),
        "/source/frying.mp4": (args.frying_video.resolve(), "video/mp4"),
        "/source/outfit.mp4": (args.outfit_video.resolve(), "video/mp4"),
    }
    for path, _ in routes.values():
        if not path.is_file():
            parser.error(f"素材不存在: {path.name}")

    class Preview(BaseHTTPRequestHandler):
        def do_GET(self):
            route = routes.get(urlsplit(self.path).path)
            if route is None:
                self.send_error(404)
                return
            path, mime = route
            # Five exact routes only: no filesystem traversal or directory listing.
            with path.open("rb") as stream:
                size = path.stat().st_size
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(size))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                try:
                    shutil.copyfileobj(stream, self.wfile)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # Browser stopped/reloaded the preview.

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Preview)
    print(f"http://127.0.0.1:{server.server_port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
