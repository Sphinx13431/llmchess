import unittest

from llmchess import (
    ChessGame,
    analyze_position,
    build_position_context,
    observe_position,
)


class PositionObservationTests(unittest.TestCase):
    def test_observe_position_collects_snapshot_and_legal_moves(self) -> None:
        game = ChessGame()

        snapshot = observe_position(game)

        self.assertEqual(snapshot.board_state.side_to_move, "white")
        self.assertFalse(snapshot.board_state.in_check)
        self.assertEqual(snapshot.legal_moves.count, 20)
        self.assertIn("e2e4", {move.uci for move in snapshot.legal_moves.moves})
        self.assertEqual(snapshot.move_history, ())
        self.assertFalse(snapshot.game_status.is_over)

    def test_observation_preserves_uci_history_and_san_display(self) -> None:
        game = ChessGame()
        game.execute_move("e2e4")
        game.execute_move("e7e5")

        snapshot = observe_position(game)

        self.assertEqual(
            [(move.uci, move.san) for move in snapshot.move_history],
            [("e2e4", "e4"), ("e7e5", "e5")],
        )
        self.assertEqual(snapshot.board_state.side_to_move, "white")


class PositionAnalysisTests(unittest.TestCase):
    def test_material_balance_is_white_positive_in_pawn_units(self) -> None:
        white_ahead = analyze_position(
            ChessGame("7k/8/8/8/8/8/8/KQ6 w - - 0 1").get_board_state()
        )
        black_ahead = analyze_position(
            ChessGame("7k/8/8/8/8/8/8/Kq6 w - - 0 1").get_board_state()
        )

        self.assertEqual(white_ahead.material_balance, 9)
        self.assertEqual(black_ahead.material_balance, -9)

    def test_reports_attacked_and_undefended_pieces_separately(self) -> None:
        analysis = analyze_position(
            ChessGame("k7/8/8/1b6/8/8/4R3/7K w - - 0 1").get_board_state()
        )

        attacked_rook = next(
            piece for piece in analysis.attacked_pieces if piece.square == "e2"
        )
        undefended_rook = next(
            piece for piece in analysis.undefended_pieces if piece.square == "e2"
        )
        self.assertEqual(attacked_rook.piece, "rook")
        self.assertEqual(attacked_rook.color, "white")
        self.assertEqual(attacked_rook.attacked_by, ("b5",))
        self.assertEqual(attacked_rook.defended_by, ())
        self.assertEqual(undefended_rook.square, "e2")

    def test_reports_legal_checks_and_captures(self) -> None:
        analysis = analyze_position(
            ChessGame("7k/6p1/8/8/8/8/8/K5R1 w - - 0 1").get_board_state()
        )

        self.assertIn("g1h1", {move.uci for move in analysis.available_checks})
        self.assertIn("g1g7", {move.uci for move in analysis.available_captures})

    def test_analysis_and_context_building_do_not_mutate_the_game(self) -> None:
        game = ChessGame()
        game.execute_move("e2e4")
        original_fen = game.get_board_state().fen
        original_history = game.get_move_history()

        analysis = analyze_position(game.get_board_state())
        context = build_position_context(game)

        self.assertEqual(analysis.material_balance, 0)
        self.assertEqual(context.snapshot.board_state.fen, original_fen)
        self.assertEqual(context.snapshot.move_history, original_history)
        self.assertEqual(game.get_board_state().fen, original_fen)
        self.assertEqual(game.get_move_history(), original_history)


if __name__ == "__main__":
    unittest.main()
