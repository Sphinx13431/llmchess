"""Command-line interface for human-vs-human chess."""

from collections.abc import Callable

from .game import ChessGame, GameStatus

InputFunction = Callable[[str], str]
OutputFunction = Callable[[str], None]


def _format_board(board: str) -> str:
    ranks = board.splitlines()
    labeled_ranks = (f"{8 - index}  {rank}" for index, rank in enumerate(ranks))
    return "\n".join(("   a b c d e f g h", *labeled_ranks, "   a b c d e f g h"))


def _format_history(game: ChessGame) -> str:
    history = game.get_move_history()
    if not history:
        return "Moves: (none)"

    formatted_plies: list[str] = []
    for index in range(0, len(history), 2):
        move_number = index // 2 + 1
        white_move = history[index].san
        if index + 1 < len(history):
            formatted_plies.append(f"{move_number}. {white_move} {history[index + 1].san}")
        else:
            formatted_plies.append(f"{move_number}. {white_move}")
    return f"Moves: {' '.join(formatted_plies)}"


def _display_status(status: GameStatus, output: OutputFunction) -> None:
    if status.termination is None:
        return

    if status.winner is None:
        output(f"Draw by {status.termination.replace('_', ' ')} ({status.result}).")
    else:
        output(
            f"{status.winner.capitalize()} wins by "
            f"{status.termination.replace('_', ' ')} ({status.result})."
        )


def play_game(
    game: ChessGame | None = None,
    input_fn: InputFunction | None = None,
    output_fn: OutputFunction | None = None,
) -> None:
    """Run a human-vs-human game, accepting UCI moves until game end or quit."""
    current_game = game if game is not None else ChessGame()
    read_input = input if input_fn is None else input_fn
    write_output = print if output_fn is None else output_fn

    write_output("Chess - human vs. human")
    write_output("Enter moves in UCI format (for example, e2e4). Type 'quit' to exit.")

    while True:
        status = current_game.get_game_status()
        state = current_game.get_board_state()
        write_output(_format_board(state.board))
        write_output(_format_history(current_game))

        if state.in_check and not status.is_over:
            write_output(f"{state.side_to_move.capitalize()} is in check.")
        if status.can_claim_draw and not status.is_over:
            write_output("A draw can be claimed.")

        if status.is_over:
            _display_status(status, write_output)
            return

        try:
            proposed_move = read_input(
                f"{state.side_to_move.capitalize()} to move (UCI or 'quit'): "
            ).strip()
        except EOFError:
            write_output("Input ended; game abandoned.")
            return

        if proposed_move.lower() == "quit":
            write_output("Game abandoned.")
            return

        validation = current_game.validate_move(proposed_move)
        if not validation.valid:
            write_output(validation.error or "Move is invalid.")
            continue

        execution = current_game.execute_move(validation.uci)
        write_output(f"{state.side_to_move.capitalize()} played {execution.san}.")


def main() -> None:
    """Start the command-line chess game."""
    play_game()
