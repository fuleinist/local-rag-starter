"""Directory watcher — auto-ingests files dropped into a mounted directory."""

import os
import time
from pathlib import Path

from ingest import Ingestor

WATCH_DIR = Path(os.environ.get("WATCH_DIR", "/documents"))
POLL_INTERVAL = int(os.environ.get("WATCH_POLL_SECONDS", "10"))


class DirWatcher:
    """Polls a directory for new files and auto-ingests them."""

    def __init__(self, ingestor: Ingestor):
        self.ingestor = ingestor
        self.seen: set[str] = set()

    def scan(self) -> list[dict]:
        """Scan watch directory for new files and ingest them."""
        if not WATCH_DIR.exists():
            return []

        results = []
        for f in sorted(WATCH_DIR.rglob("*")):
            if not f.is_file():
                continue
            key = str(f.resolve())
            if key in self.seen:
                continue
            self.seen.add(key)

            suffix = f.suffix.lower()
            if suffix not in {".md", ".txt", ".py", ".js", ".rs", ".go", ".pdf",
                              ".csv", ".json", ".yaml", ".yml", ".toml",
                              ".ini", ".cfg", ".sh", ".bat", ".ps1", ".html", ".css"}:
                continue

            try:
                chunks = self.ingestor.ingest_file(str(f))
                results.append({"path": str(f), "chunks": len(chunks)})
                print(f"Auto-ingested: {f.name} ({len(chunks)} chunks)")
            except Exception as e:
                print(f"Error ingesting {f.name}: {e}")

        return results

    def run_forever(self):
        """Run the watcher loop."""
        print(f"Watching {WATCH_DIR} for new files (every {POLL_INTERVAL}s)...")
        while True:
            try:
                self.scan()
            except Exception as e:
                print(f"Watcher error: {e}")
            time.sleep(POLL_INTERVAL)
