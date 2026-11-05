"use strict";

let PLAYERS = [];

const LEADERBOARD_KEY = "full-court-faceoff-leaderboard-v1";
let apiBaseUrl = "";
let remoteScores = null;
const elements = Object.fromEntries(
  [
    "board", "photo-message", "round-label", "tile-count", "status", "guess-form",
    "guess-input", "submit-button", "reveal-button", "skip-button", "reveal-answer-button", "hint-button",
    "photo-credit", "welcome-title", "round-actions",
    "next-button", "finish-button", "nickname-display", "solved-count", "guess-count",
    "pieces-count", "hints-count", "skips-count", "leaderboard-rows", "leaderboard-scope", "name-overlay",
    "name-form", "nickname-input", "difficulty-input", "hint-overlay", "hint-options",
    "close-hint-button",
    "final-score", "final-leaderboard", "session-finished", "new-session-button",
  ].map((id) => [id, document.getElementById(id)]),
);

const game = {
  nickname: "",
  difficulty: "advanced",
  player: null,
  usedPlayers: new Set(),
  revealed: new Set(),
  round: 0,
  roundGuesses: 0,
  guessesMade: 0,
  revealedPlayers: 0,
  tilesRevealed: 0,
  hintsUsed: 0,
  skipsUsed: 0,
  imageUrl: "",
  imageZoomed: false,
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

function zoomPhotoAroundContent(photo) {
  try {
    const sourceWidth = photo.naturalWidth;
    const sourceHeight = photo.naturalHeight;
    const output = document.createElement("canvas");
    output.width = 450;
    output.height = 330;
    const context = output.getContext("2d");
    const cropWidth = sourceWidth / 1.25;
    const cropHeight = sourceHeight / 1.25;
    const cropX = (sourceWidth - cropWidth) / 2;
    const cropY = (sourceHeight - cropHeight) / 2;
    context.drawImage(photo, cropX, cropY, cropWidth, cropHeight, 0, 0, output.width, output.height);
    return output.toDataURL("image/jpeg", 0.9);
  } catch {
    return null;
  }
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
      tile.style.backgroundSize = game.imageZoomed ? "300% 300%" : "375% 375%";
      const positionStep = game.imageZoomed ? 50 : 45.454545;
      tile.style.backgroundPosition = `${column * positionStep}% ${row * positionStep}%`;
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
  elements["solved-count"].textContent = game.revealedPlayers;
  elements["pieces-count"].textContent = game.tilesRevealed;
  elements["guess-count"].textContent = game.guessesMade;
  elements["hints-count"].textContent = game.hintsUsed;
  elements["skips-count"].textContent = game.skipsUsed;
  elements["round-label"].textContent = `ROUND ${String(game.round).padStart(2, "0")}`;
}

function rankScores(scores) {
  return scores
    .sort((left, right) => right.revealed_players - left.revealed_players
      || left.guesses_made - right.guesses_made
      || left.tiles_revealed - right.tiles_revealed
      || left.hints_used - right.hints_used
      || left.skips_used - right.skips_used
      || left.nickname.localeCompare(right.nickname))
    .slice(0, 5);
}

function loadScores() {
  if (remoteScores !== null) return rankScores([...remoteScores]);
  try {
    const parsed = JSON.parse(localStorage.getItem(LEADERBOARD_KEY) || "[]");
    if (!Array.isArray(parsed)) return [];
    return rankScores(parsed.filter((score) => score && typeof score.nickname === "string").map((score) => ({
      nickname: score.nickname,
      difficulty: score.difficulty === "starters" ? "starters" : "advanced",
      revealed_players: score.revealed_players ?? score.puzzles_solved ?? 0,
      tiles_revealed: score.tiles_revealed ?? score.pieces ?? 0,
      guesses_made: score.guesses_made ?? score.guesses ?? 0,
      hints_used: score.hints_used ?? 0,
      skips_used: score.skips_used ?? 0,
    })).filter((score) => Object.values(score).slice(2).every((value) => Number.isInteger(value) && value >= 0)));
  } catch {
    return [];
  }
}

function renderLeaderboard(target = elements["leaderboard-rows"]) {
  const scores = loadScores();
  target.replaceChildren();
  const header = document.createElement("div");
  header.className = "leader-row leader-header";
  ["#", "PLAYER", "P", "T", "G", "H", "S"].forEach((label) => {
    const cell = document.createElement("span");
    cell.textContent = label;
    header.append(cell);
  });
  target.append(header);
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
    row.append(rank, name);
    for (const value of [
      score.revealed_players,
      score.tiles_revealed,
      score.guesses_made,
      score.hints_used,
      score.skips_used,
    ]) {
      const metric = document.createElement("span");
      metric.className = "leader-score";
      metric.textContent = value;
      row.append(metric);
    }
    target.append(row);
  });
}

async function loadSharedLeaderboard() {
  if (!apiBaseUrl) return;
  try {
    const response = await fetch(`${apiBaseUrl}/api/leaderboard`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Shared score service returned ${response.status}.`);
    const result = await response.json();
    if (!Array.isArray(result.scores)) throw new Error("Shared score response was invalid.");
    remoteScores = result.scores;
  } catch {
    remoteScores = null;
  }
}

function beginRound() {
  game.finished = false;
  const playerPool = game.difficulty === "starters"
    ? PLAYERS.filter((player) => Number.isFinite(player.career_ppg) && player.career_ppg >= 15)
    : PLAYERS;
  if (game.usedPlayers.size >= playerPool.length) game.usedPlayers.clear();
  const options = playerPool.filter((player) => !game.usedPlayers.has(player.id));
  game.player = options[Math.floor(Math.random() * options.length)];
  game.usedPlayers.add(game.player.id);
  game.round += 1;
  game.roundGuesses = 0;
  game.revealed = new Set([Math.floor(Math.random() * 9)]);
  game.imageUrl = "";
  game.imageZoomed = false;
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
  elements["hint-button"].disabled = true;
  elements["skip-button"].disabled = false;
  elements["round-actions"].hidden = true;
  setStatus("Loading player photo...");
  renderStats();
  renderTiles();

  const photo = new Image();
  renderPhotoCredit(game.player);
  photo.onload = () => {
    if (token !== game.roundToken) return;
    const zoomedPhoto = zoomPhotoAroundContent(photo);
    game.imageUrl = zoomedPhoto || photo.src;
    game.imageZoomed = Boolean(zoomedPhoto);
    game.photoReady = true;
    elements["guess-input"].disabled = false;
    elements["submit-button"].disabled = false;
    elements["reveal-button"].disabled = false;
    elements["reveal-answer-button"].disabled = false;
    elements["hint-button"].disabled = false;
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
  if (game.player.image_url) photo.crossOrigin = "anonymous";
  photo.src = imageUrl(game.player);
}

function startSession(nickname) {
  game.nickname = nickname.trim().slice(0, 24) || "Player";
  game.difficulty = elements["difficulty-input"].value;
  game.usedPlayers.clear();
  game.round = 0;
  game.roundGuesses = 0;
  game.guessesMade = 0;
  game.revealedPlayers = 0;
  game.tilesRevealed = 0;
  game.hintsUsed = 0;
  game.skipsUsed = 0;
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
  game.tilesRevealed += 1;
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
  game.guessesMade += 1;
  if (!matchesPlayer(guess, game.player)) {
    setStatus("Not this time. Try again or reveal another tile.", "wrong");
    elements["guess-input"].select();
    renderStats();
    return;
  }
  game.revealedPlayers += 1;
  game.finished = true;
  setStatus(`That's ${game.player.name}. ${game.roundGuesses} guesses, ${game.revealed.size} tiles.`, "correct");
  elements["guess-input"].disabled = true;
  elements["submit-button"].disabled = true;
  elements["reveal-button"].disabled = true;
  elements["skip-button"].disabled = true;
  elements["reveal-answer-button"].disabled = true;
  elements["hint-button"].disabled = true;
  elements["round-actions"].hidden = false;
  renderStats();
}

function skipPlayer() {
  if (game.finished) return;
  game.skipsUsed += 1;
  beginRound();
}

function requestHint() {
  if (!game.photoReady || !game.player || game.finished) return;
  const playerPool = game.difficulty === "starters"
    ? PLAYERS.filter((player) => Number.isFinite(player.career_ppg) && player.career_ppg >= 15)
    : PLAYERS;
  const distractors = playerPool.filter((player) => player.id !== game.player.id);
  if (distractors.length < 2) return;
  game.hintsUsed += 1;
  renderStats();
  const choices = [
    ...distractors.sort(() => Math.random() - 0.5).slice(0, 2),
    game.player,
  ].sort(() => Math.random() - 0.5);
  elements["hint-options"].replaceChildren();
  choices.forEach((player, index) => {
    const option = document.createElement("button");
    option.type = "button";
    option.className = "button hint-option";
    option.textContent = `${index + 1}. ${player.name}`;
    option.addEventListener("click", () => {
      elements["hint-overlay"].hidden = true;
      elements["guess-input"].value = player.name;
      elements["guess-form"].requestSubmit();
    });
    elements["hint-options"].append(option);
  });
  elements["hint-overlay"].hidden = false;
}

function revealAnswer() {
  if (!game.photoReady || !game.player || game.finished) return;
  game.finished = true;
  game.lost = true;
  setStatus(`Answer: ${game.player.name}. You lost this puzzle.`, "wrong");
  elements["guess-input"].disabled = true;
  elements["submit-button"].disabled = true;
  elements["reveal-button"].disabled = true;
  elements["skip-button"].disabled = true;
  elements["reveal-answer-button"].disabled = true;
  elements["hint-button"].disabled = true;
  renderStats();
  finishSession();
}

async function finishSession() {
  if (game.finished !== true || !game.nickname || game.sessionRecorded) return;
  game.sessionRecorded = true;
  const session = {
    nickname: game.nickname,
    difficulty: game.difficulty,
    revealed_players: game.revealedPlayers,
    tiles_revealed: game.tilesRevealed,
    guesses_made: game.guessesMade,
    hints_used: game.hintsUsed,
    skips_used: game.skipsUsed,
  };
  let saveError = "";
  try {
    if (apiBaseUrl) {
      const response = await fetch(`${apiBaseUrl}/api/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(session),
      });
      if (!response.ok) throw new Error(`Shared score service returned ${response.status}.`);
      const result = await response.json();
      if (!Array.isArray(result.scores)) throw new Error("Shared score response was invalid.");
      remoteScores = result.scores;
      localStorage.setItem(LEADERBOARD_KEY, JSON.stringify(remoteScores));
    } else {
      const scores = loadScores();
      scores.push(session);
      localStorage.setItem(LEADERBOARD_KEY, JSON.stringify(rankScores(scores)));
    }
  } catch {
    saveError = "Score sync failed; this result is only saved in this browser.";
    remoteScores = null;
    try {
      const scores = loadScores();
      scores.push(session);
      localStorage.setItem(LEADERBOARD_KEY, JSON.stringify(rankScores(scores)));
    } catch {
      saveError = "Browser storage is unavailable; this result could not be saved.";
    }
  }
  game.roundToken += 1;
  elements["final-score"].textContent = game.lost
    ? `${game.nickname} revealed ${game.player.name} and lost. ${game.revealedPlayers} players, ${game.tilesRevealed} tiles, ${game.guessesMade} guesses, ${game.hintsUsed} hints, ${game.skipsUsed} skips.`
    : `${game.nickname}: ${game.revealedPlayers} players, ${game.tilesRevealed} tiles, ${game.guessesMade} guesses, ${game.hintsUsed} hints, ${game.skipsUsed} skips.`;
  elements["session-finished"].hidden = false;
  if (saveError) elements["final-score"].textContent += ` ${saveError}`;
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
elements["hint-button"].addEventListener("click", requestHint);
elements["close-hint-button"].addEventListener("click", () => {
  elements["hint-overlay"].hidden = true;
});
elements["reveal-answer-button"].addEventListener("click", revealAnswer);
elements["next-button"].addEventListener("click", beginRound);
elements["finish-button"].addEventListener("click", () => { void finishSession(); });
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
    const configResponse = await fetch("api-config.json");
    if (configResponse.ok) {
      const config = await configResponse.json();
      apiBaseUrl = typeof config.apiBaseUrl === "string" ? config.apiBaseUrl.trim().replace(/\/$/, "") : "";
    }
    if (!apiBaseUrl && ["localhost", "127.0.0.1"].includes(location.hostname)) {
      apiBaseUrl = location.origin;
    }
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
    await loadSharedLeaderboard();
    elements["leaderboard-scope"].textContent = apiBaseUrl && remoteScores !== null
      ? "SHARED"
      : "THIS BROWSER";
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