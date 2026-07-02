"""Regression test: lrag ask must produce a valid JSON request body for any question.

Reproduces the bug fixed in PR "fix(lrag): safely encode question into JSON request body".

The original `ask)` case in the lrag shell script built the JSON payload with shell
string interpolation:

    -d "{\"question\": \"$question\", \"top_k\": 5}"

Any question containing a double quote, backslash, or newline produced invalid JSON
(the pipeline to `python3 -m json.tool` would fail with "Expecting ',' delimiter" or
similar). These tests verify the payload bytes that lrag sends to the API are valid
JSON and contain the original question verbatim, regardless of special characters.
"""

from __future__ import annotations

import http.server
import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LRAG_BIN = REPO_ROOT / "lrag"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _RecordingHandler(http.server.BaseHTTPRequestHandler):
    # Test fixtures populate these on the handler class before serving.
    received_body: bytes = b""
    received_path: str = ""
    response_body: bytes = b'{"answer": "stub", "sources": []}'

    def log_message(self, *_args):  # silence stdout noise
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        _RecordingHandler.received_body = self.rfile.read(length)
        _RecordingHandler.received_path = self.path
        body = _RecordingHandler.response_body
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _run_lrag_ask(port: int, question: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["LRAG_API_URL"] = f"http://127.0.0.1:{port}"
    return subprocess.run(
        [str(LRAG_BIN), "ask", question],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )


def _serve():
    server = http.server.HTTPServer(("127.0.0.1", 0), _RecordingHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def test_plain_question_round_trips():
    server, port = _serve()
    try:
        _RecordingHandler.received_body = b""
        _RecordingHandler.received_path = ""
        result = _run_lrag_ask(port, "how does auth work")
        assert result.returncode == 0, f"lrag ask failed: {result.stderr}"
        body = json.loads(_RecordingHandler.received_body)
        assert body == {"question": "how does auth work", "top_k": 5}
        assert _RecordingHandler.received_path == "/ask"
    finally:
        server.shutdown()


def test_question_with_double_quotes():
    server, port = _serve()
    try:
        _RecordingHandler.received_body = b""
        result = _run_lrag_ask(port, 'What is the "purpose" of this code?')
        assert result.returncode == 0, f"lrag ask failed: {result.stderr}"
        # The body must be parseable JSON and contain the literal question.
        body = json.loads(_RecordingHandler.received_body)
        assert body == {"question": 'What is the "purpose" of this code?', "top_k": 5}
    finally:
        server.shutdown()


def test_question_with_backslashes():
    server, port = _serve()
    try:
        _RecordingHandler.received_body = b""
        result = _run_lrag_ask(port, r"C:\Users\chris\note.txt path?")
        assert result.returncode == 0, f"lrag ask failed: {result.stderr}"
        body = json.loads(_RecordingHandler.received_body)
        assert body == {
            "question": r"C:\Users\chris\note.txt path?",
            "top_k": 5,
        }
    finally:
        server.shutdown()


def test_question_with_newlines_and_unicode():
    server, port = _serve()
    try:
        _RecordingHandler.received_body = b""
        result = _run_lrag_ask(port, "line one\nline two\n你好世界")
        assert result.returncode == 0, f"lrag ask failed: {result.stderr}"
        body = json.loads(_RecordingHandler.received_body)
        assert body == {
            "question": "line one\nline two\n你好世界",
            "top_k": 5,
        }
    finally:
        server.shutdown()


def test_empty_question_rejected():
    """Empty question should print a usage message and exit non-zero."""
    result = subprocess.run(
        [str(LRAG_BIN), "ask"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode != 0
    assert "Usage" in result.stdout or "Usage" in result.stderr


if __name__ == "__main__":
    # Manual invocation: run each test, print PASS/FAIL, exit non-zero on any failure.
    tests = [
        test_plain_question_round_trips,
        test_question_with_double_quotes,
        test_question_with_backslashes,
        test_question_with_newlines_and_unicode,
        test_empty_question_rejected,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
        else:
            print(f"PASS  {t.__name__}")
    if failed:
        sys.exit(1)
