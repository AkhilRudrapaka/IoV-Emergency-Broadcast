"""Serve only the project's 12-section documentation website.

Run: python documentation_portal.py
Open: http://127.0.0.1:9000
Use --port 9000 to choose another port. No third-party packages are needed.
Content, diagrams, saved comparisons and downloads come from portal/.
This folder is a standalone documentation copy for project presentation.
"""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PORTAL = Path(__file__).resolve().parent / "portal"


class DocumentationHandler(SimpleHTTPRequestHandler):
    """Expose portal files only, without directory listings or backend routes."""

    def send_head(self):
        target = Path(self.translate_path(self.path)).resolve()
        if not target.is_relative_to(PORTAL.resolve()):
            self.send_error(403, "Outside documentation directory")
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404, "Documentation page not found")
        return None

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9000,
                        help="Documentation port (default: 9000)")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    for name in ("index.html", "styles.css", "app.js", "data.js"):
        if not (PORTAL / name).is_file():
            parser.error(f"Missing {PORTAL / name}. Keep this file beside the portal folder.")

    handler = partial(DocumentationHandler, directory=str(PORTAL))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    except OSError as exc:
        parser.exit(1, f"Cannot start documentation server: {exc}\n"
                       "Try: python documentation_portal.py --port 9000\n")
    with server:
        print("Project Website / Documentation Portal", flush=True)
        print(f"Open http://127.0.0.1:{args.port}/", flush=True)
        print("12 sections: background, design, algorithms, workflow, results, source, and future work.", flush=True)
        print("Press Ctrl+C to stop.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nDocumentation server stopped.")


if __name__ == "__main__":
    main()
