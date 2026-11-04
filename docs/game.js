"use strict";

let PLAYERS = [];

const LEADERBOARD_KEY = "full-court-faceoff-leaderboard-v1";
const elements = Object.fromEntries(
  [
    "board", "photo-message", "round-label", "tile-count", "status", "guess-form",
    "guess-input", "submit-button", "reveal-button", "skip-button", "reveal-answer-button",
    "photo-credit", "welcome-title", "round-actions",
    "next-button", "finish-button", "nickname-display", "solved-count", "guess-count",
    "pieces-count", "leaderboard-rows", "name-overlay", "name-form", "nickname-input",
    "final-score", "final-leaderboard", "session-finished", "new-session-button",
  ].map((id) => [id, document.getElementById(id)]),
);

const game = {
  nickname: "",
  player: null,
  usedPlayers: new Set(),
  revealed: new Set(),
  round: 0,
  roundGuesses: 0,
  sessionGuesses: 0,
  solved: 0,
  pieces: 0,
  imageUrl: "",
  photoReady: false,
  roundToken: 0,
  finished: false,
  lost: false,
  sessionRecorded: false,
};

function normalize(value) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

function editDistance(left, right) {
  const previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let row = 1; row <= left.length; row += 1) {
    let diagonal = previous[0];
    previous[0] = row;
    for (let column = 1; column <= right.length; column += 1) {
      const old = previous[column];
      previous[column] = Math.min(
        previous[column] + 1,
        previous[column - 1] + 1,
        diagonal + (left[row - 1] === right[column - 1] ? 0 : 1),
      );
      diagonal = old;
    }
  }
  return previous[right.length];
}

function matchesPlayer(guess, player) {
  const cleanedGuess = normalize(guess);
  if (!cleanedGuess) return false;
  const guessWords = guess.toLocaleLowerCase().match(/[a-z0-9]+/g)?.sort().join(" ") || "";
  return [player.name, ...player.aliases].some((answer) => {
    const cleanedAnswer = normalize(answer);
    if (cleanedGuess === cleanedAnswer) return true;
    const answerWords = answer.toLocaleLowerCase().match(/[a-z0-9]+/g)?.sort().join(" ") || "";
    if (guessWords === answerWords) return true;
    const length = Math.max(cleanedGuess.length, cleanedAnswer.length);
    return length >= 5 && editDistance(cleanedGuess, cleanedAnswer) / length <= 0.12;
  });
}

function imageUrl(player) {
  return player.image_url || `https://cdn.nba.com/headshots/nba/latest/1040x760/${player.id}.png`;
}

function renderPhotoCredit(player) {
  elements["photo-credit"].replaceChildren();
  if (!player?.attribution) {
    elements["photo-credit"].textContent = "PLAYER PHOTOS: NBA.COM";
    return;
  }
  const creditLink = document.createElement("a");
  creditLink.href = player.attribution.source_url;
  creditLink.target = "_blank";
  creditLink.rel = "noreferrer";
  creditLink.textContent = player.attribution.credit;
  const licenseLink = document.createElement("a");
  licenseLink.href = player.attribution.license_url;
  licenseLink.target = "_blank";
  licenseLink.rel = "noreferrer";
  licenseLink.textContent = player.attribution.license;
  elements["photo-credit"].append("PHOTO: ", creditLink, " · ", licenseLink, " · cropped");
}

function setStatus(message, kind = "") {
  elements.status.textContent = message;
  elements.status.classList.toggle("is-correct", kind === "correct");
  elements.status.classList.toggle("is-wrong", kind === "wrong");
}

function renderTiles() {
  elements.board.replaceChildren();
  for (let index = 0; index < 9; index += 1) {
    const tile = document.createElement("div");
    const row = Math.floor(index / 3);
    const column = index % 3;
    tile.className = `tile ${game.revealed.has(index) ? "is-revealed" : "is-hidden"}`;
    tile.setAttribute("aria-hidden", "true");
    if (game.imageUrl) {
      tile.style.backgroundImage = `url("${game.imageUrl}")`;
      tile.style.backgroundSize = "300% 300%";
      tile.style.backgroundPosition = `${column * 50}% ${row * 50}%`;
    }
    elements.board.append(tile);
  }
  elements.board.setAttribute(
    "aria-label",
    `${game.revealed.size} of 9 face tiles revealed`,
  );
  elements["tile-count"].textContent = `${String(game.revealed.size).padStart(2, "0")} / 09 TILES`;
}

function renderStats() {
  elements["solved-count"].textContent = game.solved;
  elements["guess-count"].textContent = game.sessionGuesses;
  elements["pieces-count"].textContent = game.pieces;
  elements["round-label"].textContent = `ROUND ${String(game.round).padStart(2, "0")}`;
}

function rankScores(scores) {
  return scores
    .sort((left, right) => right.puzzles_solved - left.puzzles_solved
      || left.guesses - right.guesses
      || left.pieces - right.pieces
      || left.nickname.localeCompare(right.nickname))
    .slice(0, 5);
}

function loadScores() {
  try {
    const parsed = JSON.parse(localStorage.getItem(LEADERBOARD_KEY) || "[]");
    if (!Array.isArray(parsed)) return [];
    return rankScores(parsed.filter((score) =>
      score && typeof score.nickname === "string"
      && Number.isInteger(score.puzzles_solved) && score.puzzles_solved >= 0
      && Number.isInteger(score.guesses) && score.guesses >= 0
      && Number.isInteger(score.pieces) && score.pieces >= 0));
  } catch {
    return [];
  }
}

function renderLeaderboard(target = elements["leaderboard-rows"]) {
  const scores = loadScores();
  target.replaceChildren();
  if (scores.length === 0) {
    const empty = document.createElement("p");
    empty.className = "leader-empty";
    empty.textContent = "No finished sessions yet.";
    target.append(empty);
    return;
  }
  scores.forEach((score, index) => {
    const row = document.createElement("div");
    row.className = "leader-row";
    const rank = document.createElement("span");
    rank.className = "leader-rank";
    rank.textContent = String(index + 1).padStart(2, "0");
    const name = document.createElement("span");
    name.className = "leader-name";
    name.textContent = score.nickname;
    const solved = document.createElement("span");
    solved.className = "leader-score";
    solved.textContent = score.puzzles_solved;
    row.append(rank, name, solved);
    target.append(row);
  });
}

function beginRound() {
  game.finished = false;
  if (game.usedPlayers.size >= PLAYERS.length) game.usedPlayers.clear();
  const options = PLAYERS.filter((player) => !game.usedPlayers.has(player.id));
  game.player = options[Math.floor(Math.random() * options.length)];
  game.usedPlayers.add(game.player.id);
  game.round += 1;
  game.roundGuesses = 0;
  game.revealed = new Set([Math.floor(Math.random() * 9)]);
  game.imageUrl = "";
  game.photoReady = false;
  game.roundToken += 1;
  const token = game.roundToken;
  elements["photo-message"].hidden = true;
  elements["photo-message"].textContent = "";
  elements["guess-input"].value = "";
  elements["guess-input"].disabled = true;
  elements["submit-button"].disabled = true;
  elements["reveal-button"].disabled = true;
  elements["reveal-answer-button"].disabled = true;
  elements["skip-button"].disabled = false;
  elements["round-actions"].hidden = true;
  setStatus("Loading player photo...");
  renderStats();
  renderTiles();

  const photo = new Image();
  renderPhotoCredit(game.player);
  photo.onload = () => {
    if (token !== game.roundToken) return;
    game.imageUrl = photo.src;
    game.photoReady = true;
    elements["guess-input"].disabled = false;
    elements["submit-button"].disabled = false;
    elements["reveal-button"].disabled = false;
    elements["reveal-answer-button"].disabled = false;
    setStatus("Your move.");
    renderTiles();
    elements["guess-input"].focus();
  };
  photo.onerror = () => {
    if (token !== game.roundToken) return;
    elements["photo-message"].textContent = "This photo could not load. Check your connection or skip to another player.";
    elements["photo-message"].hidden = false;
    setStatus("Photo unavailable. Skip this player to continue.", "wrong");
  };
  photo.src = imageUrl(game.player);
}

function startSession(nickname) {
  game.nickname = nickname.trim().slice(0, 24) || "Player";
  game.usedPlayers.clear();
  game.round = 0;
  game.roundGuesses = 0;
  game.sessionGuesses = 0;
  game.solved = 0;
  game.pieces = 0;
  game.finished = false;
  game.lost = false;
  game.sessionRecorded = false;
  elements["nickname-display"].textContent = game.nickname;
  elements["name-overlay"].hidden = true;
  elements["session-finished"].hidden = true;
  renderStats();
  beginRound();
}

function revealTile() {
  if (!game.photoReady || game.revealed.size >= 9 || game.finished) return;
  const hidden = Array.from({ length: 9 }, (_, index) => index).filter((index) => !game.revealed.has(index));
  game.revealed.add(hidden[Math.floor(Math.random() * hidden.length)]);
  renderTiles();
  if (game.revealed.size === 9) elements["reveal-button"].disabled = true;
}

function submitGuess(event) {
  event.preventDefault();
  if (!game.photoReady || !game.player || game.finished) return;
  const guess = elements["guess-input"].value.trim();
  if (!guess) {
    setStatus("Type a name to submit a guess.", "wrong");
    elements["guess-input"].focus();
    return;
  }
  game.roundGuesses += 1;
  game.sessionGuesses += 1;
  if (!matchesPlayer(guess, game.player)) {
    setStatus("Not this time. Try again or reveal another tile.", "wrong");
    elements["guess-input"].select();
    renderStats();
    return;
  }
  game.solved += 1;
  game.pieces += game.revealed.size;
  game.finished = true;
  setStatus(`That's ${game.player.name}. ${game.roundGuesses} guesses, ${game.revealed.size} tiles.`, "correct");
  elements["guess-input"].disabled = true;
  elements["submit-button"].disabled = true;
  elements["reveal-button"].disabled = true;
  elements["skip-button"].disabled = true;
  elements["reveal-answer-button"].disabled = true;
  elements["round-actions"].hidden = false;
  renderStats();
}

function skipPlayer() {
  if (game.finished) return;
  game.pieces += game.revealed.size;
  beginRound();
}

function revealAnswer() {
  if (!game.photoReady || !game.player || game.finished) return;
  game.finished = true;
  game.lost = true;
  game.pieces += game.revealed.size;
  setStatus(`Answer: ${game.player.name}. You lost this puzzle.`, "wrong");
  elements["guess-input"].disabled = true;
  elements["submit-button"].disabled = true;
  elements["reveal-button"].disabled = true;
  elements["skip-button"].disabled = true;
  elements["reveal-answer-button"].disabled = true;
  renderStats();
  finishSession();
}

function finishSession() {
  if (game.finished !== true || !game.nickname || game.sessionRecorded) return;
  game.sessionRecorded = true;
  const scores = loadScores();
  scores.push({
    nickname: game.nickname,
    puzzles_solved: game.solved,
    guesses: game.sessionGuesses,
    pieces: game.pieces,
  });
  try {
    localStorage.setItem(LEADERBOARD_KEY, JSON.stringify(rankScores(scores)));
  } catch {
    setStatus("Session finished, but browser storage is unavailable.", "wrong");
  }
  game.roundToken += 1;
  elements["final-score"].textContent = game.lost
    ? `${game.nickname} revealed ${game.player.name} and lost. Session score: ${game.solved} solved, ${game.sessionGuesses} guesses, ${game.pieces} tiles.`
    : `${game.nickname} solved ${game.solved} ${game.solved === 1 ? "puzzle" : "puzzles"} in ${game.sessionGuesses} guesses, using ${game.pieces} tiles.`;
  elements["session-finished"].hidden = false;
  renderLeaderboard(elements["final-leaderboard"]);
  renderLeaderboard();
}

elements["name-form"].addEventListener("submit", (event) => {
  event.preventDefault();
  startSession(elements["nickname-input"].value);
});
elements["guess-form"].addEventListener("submit", submitGuess);
elements["reveal-button"].addEventListener("click", revealTile);
elements["skip-button"].addEventListener("click", skipPlayer);
elements["reveal-answer-button"].addEventListener("click", revealAnswer);
elements["next-button"].addEventListener("click", beginRound);
elements["finish-button"].addEventListener("click", finishSession);
elements["new-session-button"].addEventListener("click", () => {
  elements["session-finished"].hidden = true;
  elements["nickname-input"].value = game.nickname;
  elements["name-overlay"].hidden = false;
  elements["nickname-input"].focus();
});

async function initializeGame() {
  const startButton = elements["name-form"].querySelector("button[type='submit']");
  startButton.disabled = true;
  elements["welcome-title"].textContent = "Loading player roster...";
  try {
    const response = await fetch("players.json");
    if (!response.ok) throw new Error(`Roster request failed (${response.status}).`);
    const roster = await response.json();
    if (!Array.isArray(roster) || roster.length < 100) {
      throw new Error("Roster must contain at least 100 players.");
    }
    if (new Set(roster.map((player) => player.id)).size !== roster.length) {
      throw new Error("Roster contains duplicate player IDs.");
    }
    PLAYERS = roster;
    elements["welcome-title"].textContent = "Who's playing?";
    startButton.disabled = false;
    renderLeaderboard();
    elements["nickname-input"].focus();
  } catch (error) {
    elements["welcome-title"].textContent = "Roster unavailable";
    elements["name-form"].querySelector("label").textContent = error.message;
    elements["nickname-input"].disabled = true;
  }
}

initializeGame();