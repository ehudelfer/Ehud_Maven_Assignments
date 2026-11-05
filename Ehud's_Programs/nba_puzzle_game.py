"""Guess NBA players from partially revealed face photos."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import io
import json
import math
import os
import random
import re
import threading
import unicodedata
import webbrowser
from pathlib import Path
from queue import Empty, Queue
from tkinter import Button, Canvas, Entry, Frame, Label, StringVar, Tk, messagebox, simpledialog
from urllib.error import URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageOps, ImageTk


WINDOW_WIDTH = 560
WINDOW_HEIGHT = 670
GRID_WIDTH = 450
GRID_HEIGHT = 330
TILE_COUNT = 9
NBA_HEADSHOT_URL = "https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"
IMAGE_CACHE = Path.home() / ".nba_puzzle_game" / "images"
LOCAL_IMAGE_DIR = Path(__file__).with_name("nba_player_images")
LEADERBOARD_PATH = Path(__file__).with_name("leaderboard.json")
PLAYER_DATA_PATH = Path(__file__).parents[1] / "docs" / "players.json"


@dataclass(frozen=True)
class Player:
    name: str
    player_id: int
    aliases: tuple[str, ...] = ()
    image_url_override: str | None = None
    attribution: dict[str, str] | None = None
    career_ppg: float | None = None

    @property
    def image_url(self) -> str:
        return self.image_url_override or NBA_HEADSHOT_URL.format(player_id=self.player_id)

    @property
    def image_filename(self) -> str:
        return f"{self.player_id}.png"


def load_player_roster(path: Path = PLAYER_DATA_PATH) -> tuple[Player, ...]:
    """Load the shared roster used by the desktop and browser games."""
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not load player data from {path}: {error}") from error
    if not isinstance(records, list):
        raise ValueError("Player data must be a JSON list.")

    players = []
    for record in records:
        if not isinstance(record, dict):
            continue
        name = record.get("name")
        player_id = record.get("id")
        aliases = record.get("aliases", [])
        if (
            isinstance(name, str)
            and name.strip()
            and isinstance(player_id, int)
            and not isinstance(player_id, bool)
            and isinstance(aliases, list)
        ):
            players.append(
                Player(
                    name=name.strip(),
                    player_id=player_id,
                    aliases=tuple(alias for alias in aliases if isinstance(alias, str)),
                    image_url_override=record.get("image_url"),
                    attribution=record.get("attribution"),
                    career_ppg=(
                        float(record["career_ppg"])
                        if isinstance(record.get("career_ppg"), (int, float))
                        and not isinstance(record.get("career_ppg"), bool)
                        and math.isfinite(record["career_ppg"])
                        else None
                    ),
                )
            )
    if len(players) < 100:
        raise ValueError(f"Player data must contain at least 100 valid players; found {len(players)}.")
    if len({player.player_id for player in players}) != len(players):
        raise ValueError("Player data contains duplicate player IDs.")
    return tuple(players)


PLAYER_ROSTER = load_player_roster()


def normalize_name(name: str) -> str:
    """Normalize accents, punctuation, and spacing for answer comparison."""
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", without_accents)


def names_match(guess: str, player: Player) -> bool:
    normalized_guess = normalize_name(guess)
    if not normalized_guess:
        return False
    accepted_names = (player.name, *player.aliases)
    for accepted_name in accepted_names:
        normalized_answer = normalize_name(accepted_name)
        if normalized_guess == normalized_answer:
            return True
        if len(normalized_guess) >= 5 and SequenceMatcher(
            None, normalized_guess, normalized_answer
        ).ratio() >= 0.88:
            return True
        guess_words = sorted(re.findall(r"[a-z0-9]+", guess.casefold()))
        answer_words = sorted(re.findall(r"[a-z0-9]+", accepted_name.casefold()))
        if guess_words == answer_words:
            return True
    return False


class GameEngine:
    """Track puzzle rounds, guesses, reveals, and session totals."""

    def __init__(
        self,
        players: tuple[Player, ...] = PLAYER_ROSTER,
        difficulty: str = "advanced",
    ) -> None:
        if not players:
            raise ValueError("The game needs at least one player.")
        if difficulty not in {"starters", "advanced"}:
            raise ValueError("Difficulty must be 'starters' or 'advanced'.")
        self.difficulty = difficulty
        self.players = (
            tuple(player for player in players if player.career_ppg is not None and player.career_ppg >= 15.0)
            if difficulty == "starters"
            else players
        )
        if not self.players:
            raise ValueError("No players meet the Starters mode scoring threshold.")
        self._random = random.Random()
        self._available_players = list(self.players)
        self.current_player: Player | None = None
        self.revealed_tiles: set[int] = set()
        self.round_guesses = 0
        self.revealed_players = 0
        self.tiles_revealed = 0
        self.guesses_made = 0
        self.hints_used = 0
        self.skips_used = 0
        self.lost = False
        self.round_finished = False
        self.start_round()

    @property
    def solved_count(self) -> int:
        return self.revealed_players

    @property
    def session_guesses(self) -> int:
        return self.guesses_made

    @property
    def session_pieces(self) -> int:
        return self.tiles_revealed

    @property
    def revealed_count(self) -> int:
        return len(self.revealed_tiles)

    def start_round(self) -> Player:
        if not self._available_players:
            self._available_players = list(self.players)
        self.current_player = self._random.choice(self._available_players)
        self._available_players.remove(self.current_player)
        self.revealed_tiles = {self._random.randrange(TILE_COUNT)}
        self.round_guesses = 0
        self.round_finished = False
        return self.current_player

    def reveal_piece(self) -> bool:
        if self.round_finished or self.revealed_count >= TILE_COUNT:
            return False
        hidden_tiles = set(range(TILE_COUNT)) - self.revealed_tiles
        self.revealed_tiles.add(self._random.choice(tuple(hidden_tiles)))
        self.tiles_revealed += 1
        return True

    def request_hint(self) -> tuple[Player, Player, Player]:
        if self.round_finished or self.current_player is None:
            raise ValueError("Hints are only available during an active round.")
        distractors = [player for player in self.players if player != self.current_player]
        if len(distractors) < 2:
            raise ValueError("The player pool needs at least three players for hints.")
        self.hints_used += 1
        choices = self._random.sample(distractors, 2) + [self.current_player]
        self._random.shuffle(choices)
        return tuple(choices)  # type: ignore[return-value]

    def submit_guess(self, guess: str) -> bool:
        if self.round_finished or self.current_player is None or not guess.strip():
            return False
        self.round_guesses += 1
        self.guesses_made += 1
        if not names_match(guess, self.current_player):
            return False
        self.revealed_players += 1
        self.round_finished = True
        return True

    def reveal_answer(self) -> Player | None:
        if self.round_finished:
            return None
        self.lost = True
        self.round_finished = True
        return self.current_player

    def skip_player(self) -> Player:
        if not self.round_finished:
            self.skips_used += 1
        return self.start_round()

    def session_record(self, nickname: str) -> dict[str, int | str]:
        return {
            "nickname": nickname.strip() or "Player",
            "difficulty": self.difficulty,
            "revealed_players": self.revealed_players,
            "tiles_revealed": self.tiles_revealed,
            "guesses_made": self.guesses_made,
            "hints_used": self.hints_used,
            "skips_used": self.skips_used,
        }


class LeaderboardManager:
    """Read and update the persistent top-five session scores."""

    def __init__(self, path: Path = LEADERBOARD_PATH, api_url: str | None = None) -> None:
        self.path = path
        self.api_url = (api_url if api_url is not None else os.environ.get("NBA_PUZZLE_API_URL", "")).rstrip("/")
        self.load_error: str | None = None
        self.scores = self._load()

    @classmethod
    def _normalize_scores(cls, data: object) -> list[dict[str, int | str]]:
        if not isinstance(data, list):
            return []
        scores = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            name = entry.get("nickname")
            revealed = entry.get("revealed_players", entry.get("puzzles_solved"))
            tiles = entry.get("tiles_revealed", entry.get("pieces"))
            guesses = entry.get("guesses_made", entry.get("guesses"))
            hints = entry.get("hints_used", 0)
            skips = entry.get("skips_used", 0)
            difficulty = entry.get("difficulty", "advanced")
            if (
                isinstance(name, str)
                and name.strip()
                and difficulty in {"starters", "advanced"}
                and all(
                    isinstance(value, int) and not isinstance(value, bool) and value >= 0
                    for value in (revealed, tiles, guesses, hints, skips)
                )
            ):
                scores.append(
                    {
                        "nickname": name.strip(),
                        "difficulty": difficulty,
                        "revealed_players": revealed,
                        "tiles_revealed": tiles,
                        "guesses_made": guesses,
                        "hints_used": hints,
                        "skips_used": skips,
                    }
                )
        return cls._rank(scores)[:5]

    def _load(self) -> list[dict[str, int | str]]:
        if self.api_url:
            try:
                request = Request(f"{self.api_url}/api/leaderboard")
                with urlopen(request, timeout=3) as response:
                    data = json.loads(response.read().decode("utf-8"))
                return self._normalize_scores(data.get("scores") if isinstance(data, dict) else None)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
                self.load_error = f"Shared leaderboard unavailable ({error}); using this computer's file."
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return self._normalize_scores(data)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            self.load_error = f"The saved leaderboard could not be read ({error}). A new one will be created."
            return []

    @staticmethod
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
        )

    def record(self, session: dict[str, int | str]) -> None:
        normalized_session = self._normalize_scores([session])
        if not normalized_session:
            raise ValueError("Session score is incomplete or invalid.")
        if self.api_url:
            try:
                body = json.dumps(normalized_session[0]).encode("utf-8")
                request = Request(
                    f"{self.api_url}/api/sessions",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=3) as response:
                    data = json.loads(response.read().decode("utf-8"))
                if isinstance(data, dict):
                    self.scores = self._normalize_scores(data.get("scores"))
                    return
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
                self.load_error = f"Shared leaderboard save failed ({error}); saved locally instead."
        self.scores = self._rank([*self.scores, normalized_session[0]])[:5]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary_path.write_text(json.dumps(self.scores, indent=2), encoding="utf-8")
        temporary_path.replace(self.path)

    def formatted_table(self) -> str:
        if not self.scores:
            return "No scores recorded yet."
        rows = ["Rank  Player             Mode      Solved  Tiles  Guesses  Hints  Skips", "-" * 73]
        for rank, score in enumerate(self.scores, start=1):
            rows.append(
            f"{rank:<5} {str(score['nickname'])[:18]:<18} {str(score['difficulty']):<9} "
            f"{int(score['revealed_players']):>6} {int(score['tiles_revealed']):>6} "
            f"{int(score['guesses_made']):>7} {int(score['hints_used']):>6} "
            f"{int(score['skips_used']):>6}"
            )
        return "\n".join(rows)


def _read_image_bytes(player: Player) -> bytes:
    """Load a local override or cached/downloaded NBA headshot."""
    for suffix in (".jpg", ".jpeg", ".png", ".webp"):
        local_path = LOCAL_IMAGE_DIR / f"{normalize_name(player.name)}{suffix}"
        if local_path.is_file():
            return local_path.read_bytes()

    IMAGE_CACHE.mkdir(parents=True, exist_ok=True)
    cached_path = IMAGE_CACHE / player.image_filename
    if cached_path.is_file():
        try:
            with Image.open(cached_path) as image:
                image.verify()
            return cached_path.read_bytes()
        except (OSError, ValueError):
            cached_path.unlink(missing_ok=True)

    request = Request(player.image_url, headers={"User-Agent": "NBA-Puzzle-Game/1.0"})
    with urlopen(request, timeout=12) as response:
        image_bytes = response.read()
    with Image.open(io.BytesIO(image_bytes)) as image:
        image.verify()
    cached_path.write_bytes(image_bytes)
    return image_bytes


def zoom_face_image(image: Image.Image, output_size: tuple[int, int], zoom: float = 1.25) -> Image.Image:
    """Crop a centered 1/zoom region, then resize it to the full tile board."""
    if zoom < 1:
        raise ValueError("Zoom must be at least 1.0.")
    rgb_image = ImageOps.exif_transpose(image).convert("RGB")
    crop_width = rgb_image.width / zoom
    crop_height = rgb_image.height / zoom
    left = (rgb_image.width - crop_width) / 2
    top = (rgb_image.height - crop_height) / 2
    crop = rgb_image.crop((
        round(left),
        round(top),
        round(left + crop_width),
        round(top + crop_height),
    ))
    return crop.resize(output_size, Image.Resampling.LANCZOS)


class NBAPuzzleGame:
    """Tkinter interface for the NBA face-tile guessing game."""

    def __init__(self, root: Tk, nickname: str, difficulty: str = "advanced") -> None:
        self.root = root
        self.nickname = nickname
        self.engine = GameEngine(difficulty=difficulty)
        self.leaderboard = LeaderboardManager()
        self.image_queue: Queue[tuple[Player, bytes | None, str | None]] = Queue()
        self.current_image: Image.Image | None = None
        self.photo_tiles: list[object] = []
        self.closed = False

        self.root.title("NBA Face Puzzle")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(500, 620)
        self.root.configure(bg="#f1f3f5")
        self.root.protocol("WM_DELETE_WINDOW", self._finish_session)

        self._build_ui()
        self._begin_round()
        self.root.after(120, self._poll_image_queue)

    def _build_ui(self) -> None:
        heading = Label(
            self.root,
            text="NBA FACE PUZZLE",
            font=("Segoe UI", 21, "bold"),
            fg="#111827",
            bg="#f1f3f5",
        )
        heading.pack(pady=(18, 2))
        self.player_label = Label(
            self.root,
            text=f"Playing as {self.nickname}",
            font=("Segoe UI", 10),
            fg="#52606d",
            bg="#f1f3f5",
        )
        self.player_label.pack(pady=(0, 10))

        self.canvas = Canvas(
            self.root,
            width=GRID_WIDTH,
            height=GRID_HEIGHT,
            bg="#17212b",
            highlightthickness=0,
        )
        self.canvas.pack(pady=5)
        self.canvas.bind("<Configure>", lambda _event: self._draw_grid())

        self.progress = StringVar()
        Label(
            self.root,
            textvariable=self.progress,
            font=("Segoe UI", 10, "bold"),
            fg="#334155",
            bg="#f1f3f5",
        ).pack(pady=(7, 12))

        guess_row = Frame(self.root, bg="#f1f3f5")
        guess_row.pack(fill="x", padx=48)
        self.guess_entry = Entry(guess_row, font=("Segoe UI", 12), relief="solid", bd=1)
        self.guess_entry.pack(side="left", fill="x", expand=True, ipady=7)
        self.guess_entry.bind("<Return>", lambda _event: self._submit_guess())
        self.submit_button = Button(
            guess_row,
            text="Submit",
            command=self._submit_guess,
            font=("Segoe UI", 10, "bold"),
            bg="#167c5a",
            fg="white",
            activebackground="#126448",
            activeforeground="white",
            relief="flat",
            padx=14,
            pady=8,
        )
        self.submit_button.pack(side="left", padx=(8, 0))

        action_row = Frame(self.root, bg="#f1f3f5")
        action_row.pack(pady=12)
        self.reveal_button = Button(
            action_row,
            text="Reveal a piece",
            command=self._reveal_piece,
            font=("Segoe UI", 10),
            relief="solid",
            bd=1,
            padx=14,
            pady=8,
        )
        self.reveal_button.pack(side="left", padx=5)
        self.skip_button = Button(
            action_row,
            text="Skip player",
            command=self._skip_player,
            font=("Segoe UI", 10),
            relief="solid",
            bd=1,
            padx=14,
            pady=8,
        )
        self.skip_button.pack(side="left", padx=5)
        self.reveal_answer_button = Button(
            action_row,
            text="Reveal answer",
            command=self._reveal_answer,
            font=("Segoe UI", 10),
            relief="solid",
            bd=1,
            padx=14,
            pady=8,
        )
        self.reveal_answer_button.pack(side="left", padx=5)
        self.hint_button = Button(
            action_row,
            text="Get hint",
            command=self._get_hint,
            font=("Segoe UI", 10),
            relief="solid",
            bd=1,
            padx=14,
            pady=8,
        )
        self.hint_button.pack(side="left", padx=5)

        self.status = StringVar(value="Loading player photo...")
        Label(
            self.root,
            textvariable=self.status,
            font=("Segoe UI", 10),
            fg="#334155",
            bg="#f1f3f5",
            wraplength=480,
            justify="center",
        ).pack(pady=(3, 5))
        self.score = StringVar()
        Label(
            self.root,
            textvariable=self.score,
            font=("Segoe UI", 9),
            fg="#64748b",
            bg="#f1f3f5",
        ).pack(pady=5)
        self.photo_credit = StringVar()
        self.photo_credit_label = Label(
            self.root,
            textvariable=self.photo_credit,
            font=("Segoe UI", 8),
            fg="#64748b",
            bg="#f1f3f5",
            wraplength=480,
        )
        self.photo_credit_label.pack(pady=(0, 7))
        self.photo_credit_label.bind("<Button-1>", self._open_photo_source)

    def _begin_round(self) -> None:
        player = self.engine.current_player
        if player is None:
            return
        self.current_image = None
        self.guess_entry.delete(0, "end")
        self.guess_entry.config(state="normal")
        self.submit_button.config(state="normal")
        self.reveal_button.config(state="disabled")
        self.reveal_answer_button.config(state="disabled")
        self.hint_button.config(state="disabled")
        self.skip_button.config(state="normal")
        self.root.title(f"NBA Face Puzzle - {self.engine.difficulty.title()} mode")
        self.photo_credit.set("PLAYER PHOTOS: NBA.COM")
        if player.attribution:
            credit = player.attribution.get("credit", "Wikimedia Commons")
            license_name = player.attribution.get("license", "")
            self.photo_credit.set(f"PHOTO: {credit} ({license_name}) · click for source/license")
            self.photo_credit_label.config(cursor="hand2")
        else:
            self.photo_credit_label.config(cursor="")
        self.status.set("Loading player photo...")
        self._draw_grid()
        self._update_progress()
        threading.Thread(target=self._load_image, args=(player,), daemon=True).start()

    def _load_image(self, player: Player) -> None:
        try:
            self.image_queue.put((player, _read_image_bytes(player), None))
        except (OSError, URLError, ValueError) as error:
            self.image_queue.put((player, None, str(error)))

    def _poll_image_queue(self) -> None:
        if self.closed:
            return
        try:
            player, image_bytes, error = self.image_queue.get_nowait()
        except Empty:
            self.root.after(120, self._poll_image_queue)
            return
        if player == self.engine.current_player and not self.engine.round_finished:
            if image_bytes is not None:
                try:
                    with Image.open(io.BytesIO(image_bytes)) as image:
                        self.current_image = zoom_face_image(image, (GRID_WIDTH, GRID_HEIGHT))
                    self.status.set("Guess the player, reveal a piece, or skip.")
                    self.reveal_button.config(state="normal")
                    self.reveal_answer_button.config(state="normal")
                    self.hint_button.config(state="normal")
                    self._draw_grid()
                except (OSError, ValueError) as image_error:
                    self._image_error(str(image_error))
            else:
                self._image_error(error or "Unknown image error")
        self.root.after(120, self._poll_image_queue)

    def _image_error(self, error: str) -> None:
        self.status.set(
            "Photo unavailable. Check your connection or add a local image, then skip this player."
        )
        self.reveal_button.config(state="disabled")
        self.hint_button.config(state="disabled")
        self.canvas.delete("all")
        self.canvas.create_text(
            GRID_WIDTH // 2,
            GRID_HEIGHT // 2,
            text="PLAYER PHOTO UNAVAILABLE",
            fill="#f1f5f9",
            font=("Segoe UI", 13, "bold"),
        )
        self.root.title(f"NBA Face Puzzle | Photo error: {error[:80]}")

    def _open_photo_source(self, _event: object) -> None:
        player = self.engine.current_player
        if player is not None and player.attribution:
            source_url = player.attribution.get("source_url")
            if source_url:
                webbrowser.open(source_url)

    def _draw_grid(self) -> None:
        if not hasattr(self, "canvas"):
            return
        width = max(self.canvas.winfo_width(), GRID_WIDTH)
        height = max(self.canvas.winfo_height(), GRID_HEIGHT)
        tile_width = width / 3
        tile_height = height / 3
        self.canvas.delete("all")
        self.photo_tiles = []
        for index in range(TILE_COUNT):
            row, column = divmod(index, 3)
            x0, y0 = column * tile_width, row * tile_height
            x1, y1 = x0 + tile_width, y0 + tile_height
            if self.current_image is not None and index in self.engine.revealed_tiles:
                crop = self.current_image.crop(
                    (
                        round(column * GRID_WIDTH / 3),
                        round(row * GRID_HEIGHT / 3),
                        round((column + 1) * GRID_WIDTH / 3),
                        round((row + 1) * GRID_HEIGHT / 3),
                    )
                )
                tile = ImageTk.PhotoImage(crop)
                self.photo_tiles.append(tile)
                self.canvas.create_image(x0, y0, image=tile, anchor="nw")
            else:
                self.canvas.create_rectangle(
                    x0,
                    y0,
                    x1,
                    y1,
                    fill="#263746",
                    outline="#90a4ae",
                    width=2,
                )
                self.canvas.create_text(
                    (x0 + x1) / 2,
                    (y0 + y1) / 2,
                    text="?",
                    fill="#d5e0e7",
                    font=("Segoe UI", 24, "bold"),
                )

    def _update_progress(self) -> None:
        self.progress.set(
            f"{self.engine.difficulty.title()} mode  |  Round {self.engine.revealed_players + 1}  |  "
            f"{self.engine.revealed_count} of {TILE_COUNT} pieces revealed"
        )
        self.score.set(
            f"Players: {self.engine.revealed_players}  |  Tiles: {self.engine.tiles_revealed}  |  "
            f"Guesses: {self.engine.guesses_made}  |  Hints: {self.engine.hints_used}  |  "
            f"Skips: {self.engine.skips_used}"
        )

    def _submit_guess(self) -> None:
        guess = self.guess_entry.get().strip()
        if not guess:
            self.status.set("Type a player name before submitting.")
            self.guess_entry.focus_set()
            return
        if self.current_image is None:
            self.status.set("Wait for the player photo to load, or skip this player.")
            return
        was_correct = self.engine.submit_guess(guess)
        self._update_progress()
        if was_correct:
            player = self.engine.current_player
            self.status.set(
                f"Correct! It was {player.name}. You solved it in "
                f"{self.engine.round_guesses} guesses with "
                f"{self.engine.revealed_count} piece(s) revealed."
            )
            self.guess_entry.config(state="disabled")
            self.submit_button.config(state="disabled")
            self.reveal_button.config(state="disabled")
            self.reveal_answer_button.config(state="disabled")
            self.hint_button.config(state="disabled")
            self.skip_button.config(state="disabled")
            self.root.after(300, self._ask_play_again)
        else:
            self.status.set("Not quite. Try another spelling, reveal a piece, or skip.")

    def _reveal_piece(self) -> None:
        if self.engine.reveal_piece():
            self._draw_grid()
            self._update_progress()
        if self.engine.revealed_count >= TILE_COUNT:
            self.reveal_button.config(state="disabled")

    def _get_hint(self) -> None:
        try:
            choices = self.engine.request_hint()
        except ValueError as error:
            self.status.set(str(error))
            return
        options = "\n".join(f"{index}. {player.name}" for index, player in enumerate(choices, start=1))
        self._update_progress()
        selection = simpledialog.askinteger(
            "Three-choice hint",
            f"One answer is correct. Choose a number:\n\n{options}",
            minvalue=1,
            maxvalue=3,
            parent=self.root,
        )
        if selection is None:
            return
        self.guess_entry.delete(0, "end")
        self.guess_entry.insert(0, choices[selection - 1].name)
        self._submit_guess()

    def _reveal_answer(self) -> None:
        player = self.engine.reveal_answer()
        if player is None:
            return
        self.status.set(f"Answer revealed: {player.name}. You lost this puzzle.")
        self.guess_entry.config(state="disabled")
        self.submit_button.config(state="disabled")
        self.reveal_button.config(state="disabled")
        self.reveal_answer_button.config(state="disabled")
        self.hint_button.config(state="disabled")
        self.skip_button.config(state="disabled")
        self._update_progress()
        self.root.after(150, self._finish_session)

    def _skip_player(self) -> None:
        self.engine.skip_player()
        self.root.title("NBA Face Puzzle")
        self._begin_round()

    def _ask_play_again(self) -> None:
        if messagebox.askyesno(
            "Puzzle solved",
            f"You have solved {self.engine.solved_count} puzzle(s). Play another round?",
            parent=self.root,
        ):
            self.engine.start_round()
            self._begin_round()
        else:
            self._finish_session()

    def _finish_session(self) -> None:
        try:
            self.leaderboard.record(self.engine.session_record(self.nickname))
            save_message = (
                f"\n\n{self.leaderboard.load_error}"
                if self.leaderboard.load_error
                else ""
            )
        except OSError as error:
            save_message = f"\n\nCould not save leaderboard: {error}"
        table = self.leaderboard.formatted_table()
        messagebox.showinfo(
            "Session leaderboard",
            f"Session complete. Puzzles solved: {self.engine.solved_count}\n\n"
            f"TOP 5\n{table}{save_message}",
            parent=self.root,
        )
        self.close()

    def close(self) -> None:
        self.closed = True
        self.root.destroy()


def main() -> None:
    root = Tk()
    root.withdraw()
    nickname = simpledialog.askstring(
        "NBA Face Puzzle", "Enter your nickname:", parent=root
    )
    if nickname is None:
        root.destroy()
        return
    nickname = nickname.strip() or "Player"
    while True:
        difficulty = simpledialog.askstring(
            "Choose difficulty",
            "Enter Starters (15+ career PPG) or Advanced (all players):",
            initialvalue="advanced",
            parent=root,
        )
        if difficulty is None:
            root.destroy()
            return
        difficulty = difficulty.strip().casefold()
        if difficulty in {"starters", "advanced"}:
            break
        messagebox.showerror("Choose difficulty", "Enter either Starters or Advanced.", parent=root)
    root.deiconify()
    NBAPuzzleGame(root, nickname, difficulty)
    root.mainloop()


if __name__ == "__main__":
    main()