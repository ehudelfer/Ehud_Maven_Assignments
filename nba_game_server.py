"""Serve the NBA puzzle web client and its shared local leaderboard API."""

from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
from typing import Any
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "docs"
SCORE_PATH = Path(
    os.environ.get("NBA_PUZZLE_SCORE_PATH", str(ROOT / "Ehud's_Programs" / "leaderboard.json"))
)
MAX_BODY_BYTES = 16_384
MAX_SCORES = 5
RATE_LIMIT = 30
RATE_WINDOW_SECONDS = 600
SCORE_LOCK = threading.Lock()


def _allowed_origins() -> set[str]:
    configured = os.environ.get("NBA_PUZZLE_ALLOWED_ORIGINS", "")
    origins = {origin.strip() for origin in configured.split(",") if origin.strip()}
    origins.update(
        {
            "https://ehudelfer.github.io",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        }
    )
    return origins


def _valid_metric(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100_000


def _normalize_score(score: Any) -> dict[str, int | str] | None:
    if not isinstance(score, dict):
        return None
    nickname = score.get("nickname")
    difficulty = score.get("difficulty", "advanced")
    revealed_players = score.get("revealed_players", score.get("puzzles_solved"))
    tiles_revealed = score.get("tiles_revealed", score.get("pieces"))
    guesses_made = score.get("guesses_made", score.get("guesses"))
    hints_used = score.get("hints_used", 0)
    skips_used = score.get("skips_used", 0)
    metrics = (revealed_players, tiles_revealed, guesses_made, hints_used, skips_used)
    if (
        not isinstance(nickname, str)
        or not nickname.strip()
        or len(nickname.strip()) > 24
        or difficulty not in {"starters", "advanced"}
        or not all(_valid_metric(metric) for metric in metrics)
    ):
        return None
    return {
        "nickname": nickname.strip(),
        "difficulty": difficulty,
        "revealed_players": revealed_players,
        "tiles_revealed": tiles_revealed,
        "guesses_made": guesses_made,
        "hints_used": hints_used,
        "skips_used": skips_used,
    }


def _rank(scores: list[dict[str, int | str]]) -> list[dict[str, int | str]]:
    return sorted(
        scores,
        key=lambda score: (
            -int(score["revealed_players"]),
            int(score["guesses_made"]),
            int(score["tiles_revealed"]),
            int(score["hints_used"]),
            int(score["skips_used"]),
            str(score["nickname"]).casefold(),
        ),
    )[:MAX_SCORES]


def _load_scores() -> list[dict[str, int | str]]:
    try:
        raw = json.loads(SCORE_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    normalized = [_normalize_score(item) for item in raw]
    return _rank([score for score in normalized if score is not None])


def _save_scores(scores: list[dict[str, int | str]]) -> None:
    SCORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = SCORE_PATH.with_suffix(SCORE_PATH.suffix + ".tmp")
    temporary_path.write_text(json.dumps(_rank(scores), indent=2), encoding="utf-8")
    temporary_path.replace(SCORE_PATH)


class PuzzleRequestHandler(SimpleHTTPRequestHandler):
    server_version = "NBAPuzzle/1.0"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def _send_json(self, status: int, payload: Any) -> None:
        encoded = b"" if status == 204 else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        origin = self.headers.get("Origin")
        if origin and origin in _allowed_origins():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        if status != 204:
            self.wfile.write(encoded)

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        return origin is None or origin in _allowed_origins()

    def do_OPTIONS(self) -> None:
        if not self._origin_allowed():
            self._send_json(403, {"error": "Origin not allowed."})
            return
        self._send_json(204, {})

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path.startswith("/api/") and not self._origin_allowed():
            self._send_json(403, {"error": "Origin not allowed."})
            return
        if path == "/api/leaderboard":
            with SCORE_LOCK:
                scores = _load_scores()
            self._send_json(200, {"scores": scores})
            return
        if path.startswith("/api/"):
            self._send_json(404, {"error": "API route not found."})
            return
        super().do_GET()

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/sessions":
            self._send_json(404, {"error": "API route not found."})
            return
        if not self._origin_allowed():
            self._send_json(403, {"error": "Origin not allowed."})
            return
        now = time.time()
        client = self.client_address[0]
        rate_map = self.server.rate_map
        recent = [stamp for stamp in rate_map.get(client, []) if now - stamp < RATE_WINDOW_SECONDS]
        if len(recent) >= RATE_LIMIT:
            self._send_json(429, {"error": "Too many score submissions. Try again later."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY_BYTES:
                raise ValueError("Invalid request size.")
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "Invalid JSON request."})
            return
        session = _normalize_score(body)
        if session is None:
            self._send_json(400, {"error": "Session metrics are incomplete or invalid."})
            return
        rate_map[client] = [*recent, now]
        try:
            with SCORE_LOCK:
                scores = _rank([*_load_scores(), session])
                _save_scores(scores)
        except OSError:
            self._send_json(500, {"error": "Leaderboard could not be saved."})
            return
        self._send_json(201, {"scores": scores})

    def log_message(self, format_string: str, *args: Any) -> None:
        print(f"{self.client_address[0]} - {format_string % args}")


def main() -> None:
    host = os.environ.get("NBA_PUZZLE_HOST", "127.0.0.1")
    port = int(os.environ.get("NBA_PUZZLE_PORT", os.environ.get("PORT", "8000")))
    server = ThreadingHTTPServer((host, port), PuzzleRequestHandler)
    server.rate_map = {}
    print(f"NBA puzzle server: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping NBA puzzle server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
