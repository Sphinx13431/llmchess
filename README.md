# LLM Chess

A Python chess application managed with `uv`. The CLI currently supports
human-vs-human play. The library includes position analysis, an Ollama provider,
and a one-turn AI workflow; AI play is not wired into the CLI yet.

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

## Ollama provider

Install and start [Ollama](https://ollama.com/), then download the default model:

```bash
ollama pull gemma4:e2b
```

With the Ollama service running, the provider can be used independently:

```python
from llmchess import OllamaProvider

provider = OllamaProvider()
response = provider.generate("Return one legal chess move in UCI notation.")
print(response)
```

The default model is `gemma4:e2b` with temperature `0.2`. Model invocation
failures raise `ModelInvocationError`; non-text responses raise
`ModelResponseError`.

## AI-turn workflow

The workflow can generate and apply a single AI move independently of the CLI:

```python
from llmchess import ChessGame, OllamaProvider, run_ai_turn

game = ChessGame()
result = run_ai_turn(game, OllamaProvider())
if result.success:
    print(f"AI played {result.move}")
else:
    print(f"AI turn failed: {result.error_message}")
```

The workflow provides the model with the observed position, complete legal
moves, history, and objective analysis. It parses the required JSON response,
validates every proposed UCI move, and allows at most three total attempts for
malformed or illegal proposals. Provider failures are reported separately.
Only a validated move is executed. Human-vs-AI CLI integration is a later step.

## Run tests

```bash
uv run python -m unittest discover -s tests -v
```
