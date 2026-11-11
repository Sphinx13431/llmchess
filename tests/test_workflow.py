import json
import unittest

from llmchess import (
    MAX_ATTEMPTS,
    ChessGame,
    ModelInvocationError,
    run_ai_turn,
)


class StubProvider:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = iter(responses)
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


class AIWorkflowTests(unittest.TestCase):
    def test_valid_move_is_executed_and_state_is_serializable(self) -> None:
        provider = StubProvider(
            ['{"move":"e2e4","reasoning":"Control the center."}']
        )
        game = ChessGame()

        result = run_ai_turn(game, provider)

        self.assertTrue(result.success)
        self.assertTrue(result.state["completed"])
        self.assertEqual(result.move, "e2e4")
        self.assertEqual(result.attempts_used, 1)
        self.assertEqual(game.get_move_history()[0].uci, "e2e4")
        self.assertEqual(result.state["fen"], game.get_board_state().fen)
        self.assertEqual(result.state["move_history_uci"], ["e2e4"])
        execution = result.state["move_execution"]
        self.assertIsNotNone(execution)
        if execution is None:
            self.fail("Successful AI turn did not include move execution details.")
        self.assertEqual(execution["san"], "e4")
        json.dumps(result.state)

    def test_initial_prompt_contains_complete_position_context(self) -> None:
        provider = StubProvider(
            ['{"move":"e2e4","reasoning":"Control the center."}']
        )

        run_ai_turn(ChessGame(), provider)

        prompt = provider.prompts[0]
        self.assertIn("Position context:", prompt)
        self.assertIn("rnbqkbnr/pppppppp", prompt)
        self.assertIn('"uci": "e2e4"', prompt)
        self.assertIn('"material_balance": 0', prompt)
        self.assertIn('"move_history": []', prompt)

    def test_illegal_moves_use_three_total_attempts_without_mutation(self) -> None:
        provider = StubProvider(
            ['{"move":"e2e5","reasoning":"Try this."}'] * MAX_ATTEMPTS
        )
        game = ChessGame()
        original_fen = game.get_board_state().fen

        result = run_ai_turn(game, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "illegal_move")
        self.assertTrue(result.state["attempts_exhausted"])
        self.assertEqual(result.attempts_used, MAX_ATTEMPTS)
        self.assertEqual(len(provider.prompts), MAX_ATTEMPTS)
        self.assertIn("previous response was rejected", provider.prompts[1])
        self.assertIn("e2e5", provider.prompts[1])
        self.assertEqual(game.get_board_state().fen, original_fen)
        self.assertEqual(game.get_move_history(), ())

    def test_malformed_responses_share_the_three_attempt_budget(self) -> None:
        provider = StubProvider(["not json"] * MAX_ATTEMPTS)
        game = ChessGame()
        original_fen = game.get_board_state().fen

        result = run_ai_turn(game, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "malformed_response")
        self.assertTrue(result.state["attempts_exhausted"])
        self.assertEqual(result.attempts_used, MAX_ATTEMPTS)
        self.assertIn("Response is not valid JSON", result.error_message or "")
        self.assertEqual(game.get_board_state().fen, original_fen)

    def test_malformed_and_illegal_responses_share_one_budget(self) -> None:
        provider = StubProvider(
            [
                "{}",
                '{"move":"e2e5","reasoning":"Try this."}',
                '{"move":"e2e4","reasoning":"Control the center."}',
            ]
        )
        game = ChessGame()

        result = run_ai_turn(game, provider)

        self.assertTrue(result.success)
        self.assertEqual(result.attempts_used, MAX_ATTEMPTS)
        self.assertEqual(game.get_move_history()[0].uci, "e2e4")

    def test_provider_failure_is_reported_without_retry_or_mutation(self) -> None:
        provider = StubProvider([ModelInvocationError("Ollama is unavailable")])
        game = ChessGame()
        original_fen = game.get_board_state().fen

        result = run_ai_turn(game, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "model_error")
        self.assertEqual(result.attempts_used, 1)
        self.assertFalse(result.state["attempts_exhausted"])
        self.assertEqual(len(provider.prompts), 1)
        self.assertEqual(game.get_board_state().fen, original_fen)
        self.assertEqual(game.get_move_history(), ())

    def test_game_over_position_does_not_invoke_provider(self) -> None:
        provider = StubProvider([])
        game = ChessGame("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")

        result = run_ai_turn(game, provider)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "game_over")
        self.assertEqual(result.attempts_used, 0)
        self.assertEqual(provider.prompts, [])


if __name__ == "__main__":
    unittest.main()
