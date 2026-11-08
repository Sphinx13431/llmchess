# LLM Chess

A Python chess application managed with `uv`. The CLI supports human-vs-human
play, and the library exposes position observation and objective analysis for
future agent integration. Ollama and AI play are not wired into the application
yet.

## Requirements

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/)

## Install

Clone the repository and enter its directory:

```bash
git clone git@github.com:Sphinx13431/llmchess.git
cd llmchess
```

Sync the project dependencies:

```bash
uv sync --locked
```

`uv` creates a virtual environment and installs the dependencies from
`uv.lock`. It can install the required Python version if it is not already
available.

## Run

Start a new game with:

```bash
uv run python -m llmchess
```

Enter moves in UCI notation, such as `e2e4` or `g8f6`. The CLI displays the
board and move history after each turn, rejects malformed or illegal moves,
and reports check, claimable draws, and game-ending results. Type `quit` to
leave the game.

## Position context API

The package provides `observe_position(game)` for a snapshot containing the
board state, legal moves, move history, and game status. Use
`analyze_position(snapshot.board_state)` to get material balance, attacked and
undefended pieces, and legal checks and captures. `build_position_context(game)`
combines these results. These facts describe the position; they are not a
chess-engine evaluation.

## Run tests

```bash
uv run python -m unittest discover -s tests -v
```
