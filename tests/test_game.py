import unittest

import chess

from llmchess import ChessGame


class ChessGameTests(unittest.TestCase):
    def test_initial_state_and_legal_moves(self) -> None:
        game = ChessGame()

        state = game.get_board_state()
        legal_moves = game.get_legal_moves()

        self.assertEqual(state.fen, chess.STARTING_FEN)
        self.assertEqual(state.side_to_move, "white")
        self.assertFalse(state.in_check)
        self.assertIn("r n b q k b n r", state.board)
        self.assertEqual(legal_moves.count, 20)
        self.assertIn(("e2e4", "e4"), {(move.uci, move.san) for move in legal_moves.moves})

    def test_valid_move_validation_does_not_mutate_board(self) -> None:
        game = ChessGame()
        initial_fen = game.get_board_state().fen

        result = game.validate_move("e2e4")

        self.assertTrue(result.valid)
        self.assertEqual(result.uci, "e2e4")
        self.assertEqual(result.san, "e4")
        self.assertIsNone(result.error)
        self.assertEqual(game.get_board_state().fen, initial_fen)
        self.assertEqual(game.get_move_history(), ())

    def test_invalid_moves_do_not_mutate_board(self) -> None:
        game = ChessGame()
        initial_fen = game.get_board_state().fen

        for proposed_uci, expected_error in (
            ("not-a-move", "Malformed UCI move."),
            ("e2e5", "Illegal move in the current position."),
        ):
            with self.subTest(proposed_uci=proposed_uci):
                result = game.validate_move(proposed_uci)

                self.assertFalse(result.valid)
                self.assertEqual(result.error, expected_error)
                self.assertEqual(game.get_board_state().fen, initial_fen)
                self.assertEqual(game.get_move_history(), ())

    def test_execution_updates_board_and_history(self) -> None:
        game = ChessGame()

        execution = game.execute_move("e2e4")

        self.assertEqual(execution.uci, "e2e4")
        self.assertEqual(execution.san, "e4")
        self.assertEqual(execution.fen, game.get_board_state().fen)
        self.assertEqual(game.get_board_state().side_to_move, "black")
        self.assertEqual(game.get_move_history()[0].uci, "e2e4")
        self.assertEqual(game.get_move_history()[0].san, "e4")
        self.assertFalse(execution.game_status.is_over)

    def test_execution_revalidates_against_current_position(self) -> None:
        game = ChessGame()
        game.execute_move("e2e4")
        position_after_move = game.get_board_state().fen

        with self.assertRaisesRegex(ValueError, "Illegal move in the current position"):
            game.execute_move("e2e4")

        self.assertEqual(game.get_board_state().fen, position_after_move)
        self.assertEqual(len(game.get_move_history()), 1)

    def test_checkmate_status(self) -> None:
        game = ChessGame()
        for move in ("f2f3", "e7e5", "g2g4", "d8h4"):
            execution = game.execute_move(move)

        self.assertTrue(execution.game_status.is_over)
        self.assertEqual(execution.game_status.result, "0-1")
        self.assertEqual(execution.game_status.termination, "checkmate")
        self.assertEqual(execution.game_status.winner, "black")
        self.assertTrue(game.get_board_state().in_check)

    def test_stalemate_status(self) -> None:
        game = ChessGame("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")

        status = game.get_game_status()

        self.assertTrue(status.is_over)
        self.assertEqual(status.result, "1/2-1/2")
        self.assertEqual(status.termination, "stalemate")
        self.assertIsNone(status.winner)

    def test_insufficient_material_draw_status(self) -> None:
        game = ChessGame("k7/8/8/8/8/8/8/1K6 w - - 0 1")

        status = game.get_game_status()

        self.assertTrue(status.is_over)
        self.assertEqual(status.result, "1/2-1/2")
        self.assertEqual(status.termination, "insufficient_material")

    def test_threefold_repetition_is_claimable_but_not_automatically_over(self) -> None:
        game = ChessGame()
        moves = ("g1f3", "g8f6", "f3g1", "f6g8") * 2
        for move in moves:
            game.execute_move(move)

        status = game.get_game_status()

        self.assertFalse(status.is_over)
        self.assertEqual(status.result, "*")
        self.assertIsNone(status.termination)
        self.assertTrue(status.can_claim_draw)

    def test_invalid_initial_fen_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "valid chess position"):
            ChessGame("invalid FEN")


if __name__ == "__main__":
    unittest.main()
