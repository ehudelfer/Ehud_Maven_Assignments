# Generating an NBA puzzle game

This guide walks you through creating a Python program that serves as an NBA player puzzle game with Copilot in VS Code.

---

## Step 1: Create a structured, explained prompt.

On Gemini, I explained the outcome game I would like to generate via Copilot and asked for an optimized prompt:
Result:
**`< Create a complete Python puzzle game program under Ehud's Programs Folder (e.g., Day03/nba_puzzle_game.py). The game challenges users to identify present and past NBA players from partial face images.
Requirements & Architecture:
	User Identification:
	At start, prompt the player to enter a nickname.
	Game Core Mechanics:
	Load an NBA player's image and reveal only a portion of the face initially (e.g., start with 1 out of Ngrid tiles/pieces revealed).
	Include an input area for the user to type their guess for the player's full name (case-insensitive and tolerant of basic spelling/formatting).
	Give the user options on each turn:
	Submit a guess.
	Reveal another piece of the player's face (increments the revealed pieces counter).
	Skip / switch to a different NBA player.
	Feedback & Scoring:
	Display a congratulatory message upon a correct guess, or an encouraging message if incorrect.
	Track and display stats upon winning a round:
	Total number of guesses made.
	Total number of puzzle pieces revealed prior to guessing correctly.
	Support consecutive rounds: prompt the user to play again and track the total number of successfully solved puzzles in the current session.
	Leaderboard & Persistence:
	Maintain a persistent top-5 high scores table saved to a local file (e.g., leaderboard.json).
	Leaderboard metric: Rank players primarily by total puzzles solved (and secondarily by fewest guesses/pieces used).
	Display the formatted top-5 leaderboard table at the end of each game session.
	UI & Implementation Details:
	Use standard Python libraries (tkinter + Pillow/PIL for GUI rendering, or colorama/Pillow for terminal-based display).
	Modularize the code into clean functions/classes (Player, GameEngine, LeaderboardManager).
	Add error handling for missing image assets or corrupted JSON data.>`**

---

## Step 2: Run the prompt and give Copilot feedback

1. Run the prompt on Copilot Chat; allow it to create and run the terminal command.
2. Back-and-forth feedback for the game: test the game results and ask Copilot to improve the code. For example, setting facial zoom, creating difficulty levels.

---
## Step 3: Making a Browser version of the game

1. After finishing the local version, I asked the chat to create a browser web version of the game.
2. Follow some Copilot instructions, such as changing page settings on GitHub.

1. Under **`<Source Control>`** press the **`<+>`** icon on the changes created, name the commit and press the commit icon.
2. Go back to GitHub and check that the new folder and file have been added to the Repository.
