import unittest

from llmchess import ChessGame
from llmchess.cli import play_game


class ChessCliTests(unittest.TestCase):
    def run_cli(
        self, moves: list[str], game: ChessGame | None = None
    ) -> tuple[list[str], ChessGame]:
        output: list[str] = []
        inputs = iter(moves)
        current_game = game if game is not None else ChessGame()

        def read_input(_: str) -> str:
            try:
                return next(inputs)
            except StopIteration:
                raise EOFError from None

        play_game(current_game, read_input, output.append)
        return output, current_game

    def test_valid_uci_moves_are_played_and_quit_is_handled(self) -> None:
        output, game = self.run_cli(["e2e4", "e7e5", "quit"])

        self.assertEqual([move.uci for move in game.get_move_history()], ["e2e4", "e7e5"])
        self.assertIn("White played e4.", output)
        self.assertIn("Black played e5.", output)
        self.assertIn("Moves: 1. e4 e5", output)
        self.assertEqual(output[-1], "Game abandoned.")

    def test_invalid_moves_are_reported_without_changing_position(self) -> None:
        game = ChessGame()
        initial_fen = game.get_board_state().fen

        output, _ = self.run_cli(["e4", "e2e5", "quit"], game)

        self.assertIn("Malformed UCI move.", output)
        self.assertIn("Illegal move in the current position.", output)
        self.assertEqual(game.get_board_state().fen, initial_fen)
        self.assertEqual(game.get_move_history(), ())

    def test_game_ends_after_checkmate(self) -> None:
        output, game = self.run_cli(["f2f3", "e7e5", "g2g4", "d8h4", "e2e4"])

        self.assertEqual(len(game.get_move_history()), 4)
        self.assertIn("Black wins by checkmate (0-1).", output)
        result_index = output.index("Black wins by checkmate (0-1).")
        self.assertFalse(any(" to move " in line for line in output[result_index + 1 :]))

    def test_eof_abandons_game(self) -> None:
        output, game = self.run_cli([])

        self.assertEqual(game.get_move_history(), ())
        self.assertEqual(output[-1], "Input ended; game abandoned.")


if __name__ == "__main__":
    unittest.main()
