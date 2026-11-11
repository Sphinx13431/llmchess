"""LangGraph workflow for generating and applying one AI chess move."""

import json
from dataclasses import asdict, dataclass
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from .game import BoardState, ChessGame, GameStatus
from .position import analyze_position, observe_position
from .provider import LLMProvider, ModelProviderError

MAX_ATTEMPTS = 3


class AIWorkflowState(TypedDict):
    """Serializable state for one AI move, without a live chess.Board."""

    fen: str
    move_history_uci: list[str]
    game_status: dict[str, Any]
    position_snapshot: dict[str, Any] | None
    position_analysis: dict[str, Any] | None
    attempt_count: int
    raw_response: str | None
    proposed_move: str | None
    reasoning: str | None
    validation_valid: bool | None
    retry_feedback: dict[str, str] | None
    failure_kind: str | None
    error_message: str | None
    attempts_exhausted: bool
    move_execution: dict[str, Any] | None
    completed: bool
    success: bool


@dataclass(frozen=True)
class AIWorkflowResult:
    """Result of running an AI turn, including its serializable final state."""

    state: AIWorkflowState

    @property
    def success(self) -> bool:
        return self.state["success"]

    @property
    def attempts_used(self) -> int:
        return self.state["attempt_count"]

    @property
    def move(self) -> str | None:
        execution = self.state["move_execution"]
        if execution is None:
            return None
        return str(execution["uci"])

    @property
    def failure_kind(self) -> str | None:
        return self.state["failure_kind"]

    @property
    def error_message(self) -> str | None:
        return self.state["error_message"]


def _json_value(value: Any) -> Any:
    """Convert dataclasses and tuples into JSON-compatible state values."""
    return json.loads(json.dumps(asdict(value)))


def _serialize_game_status(status: GameStatus) -> dict[str, Any]:
    return asdict(status)


def _current_history_uci(game: ChessGame) -> list[str]:
    return [move.uci for move in game.get_move_history()]


def _assert_game_matches_state(game: ChessGame, state: AIWorkflowState) -> None:
    if game.get_board_state().fen != state["fen"]:
        raise RuntimeError("The live chess position changed during the AI turn.")
    if _current_history_uci(game) != state["move_history_uci"]:
        raise RuntimeError("The live move history changed during the AI turn.")


def _build_prompt(state: AIWorkflowState) -> str:
    snapshot = state["position_snapshot"]
    analysis = state["position_analysis"]
    if snapshot is None or analysis is None:
        raise RuntimeError("Position context is missing before move generation.")

    position_context = {
        "snapshot": snapshot,
        "analysis": analysis,
    }
    prompt = (
        "You are playing chess. Choose exactly one legal move for the side to "
        "move. Return only a JSON object with a UCI move and a concise "
        'explanation, for example {"move":"e2e4","reasoning":"Controls '
        'the center."}. The move must be selected from the supplied legal '
        "moves. Do not include markdown or text outside the JSON object.\n\n"
        "Position context:\n"
        f"{json.dumps(position_context, ensure_ascii=True)}"
    )
    feedback = state["retry_feedback"]
    if feedback is not None:
        prompt += (
            "\n\nYour previous response was rejected. Propose a different "
            "legal move. Return the required JSON format.\n"
            f"Previous response: {feedback['previous_response']}\n"
            f"Validation feedback: {feedback['error']}"
        )
    return prompt


def _parse_move_response(raw_response: str) -> tuple[str, str]:
    try:
        response: object = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise ValueError("Response is not valid JSON.") from exc

    if not isinstance(response, dict):
        raise ValueError("Response must be a JSON object.")

    move = response.get("move")
    reasoning = response.get("reasoning")
    if not isinstance(move, str) or not move.strip():
        raise ValueError("Response must contain a non-empty UCI move string.")
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise ValueError("Response must contain a non-empty reasoning string.")
    return move.strip(), reasoning.strip()


def _initial_state(game: ChessGame) -> AIWorkflowState:
    status = game.get_game_status()
    return {
        "fen": game.get_board_state().fen,
        "move_history_uci": _current_history_uci(game),
        "game_status": _serialize_game_status(status),
        "position_snapshot": None,
        "position_analysis": None,
        "attempt_count": 0,
        "raw_response": None,
        "proposed_move": None,
        "reasoning": None,
        "validation_valid": None,
        "retry_feedback": None,
        "failure_kind": None,
        "error_message": None,
        "attempts_exhausted": False,
        "move_execution": None,
        "completed": False,
        "success": False,
    }


def run_ai_turn(game: ChessGame, provider: LLMProvider) -> AIWorkflowResult:
    """Run one bounded AI turn and mutate the game only after legal validation."""

    def observe_node(state: AIWorkflowState) -> dict[str, Any]:
        _assert_game_matches_state(game, state)
        if state["game_status"]["is_over"]:
            return {
                "failure_kind": "game_over",
                "error_message": "Cannot generate a move because the game is over.",
            }
        snapshot = observe_position(game)
        return {"position_snapshot": _json_value(snapshot)}

    def analyze_node(state: AIWorkflowState) -> dict[str, Any]:
        snapshot = state["position_snapshot"]
        if snapshot is None:
            raise RuntimeError("Position snapshot is missing before analysis.")
        board_data = snapshot["board_state"]
        board_state = _board_state_from_dict(board_data)
        return {"position_analysis": _json_value(analyze_position(board_state))}

    def generate_node(state: AIWorkflowState) -> dict[str, Any]:
        attempt_count = state["attempt_count"] + 1
        try:
            raw_response = provider.generate(_build_prompt(state))
        except ModelProviderError as exc:
            return {
                "attempt_count": attempt_count,
                "failure_kind": "model_error",
                "error_message": str(exc),
                "raw_response": None,
            }
        return {
            "attempt_count": attempt_count,
            "raw_response": raw_response,
            "proposed_move": None,
            "reasoning": None,
            "validation_valid": None,
            "failure_kind": None,
            "error_message": None,
        }

    def validate_node(state: AIWorkflowState) -> dict[str, Any]:
        _assert_game_matches_state(game, state)
        raw_response = state["raw_response"]
        if raw_response is None:
            raise RuntimeError("Model response is missing before validation.")
        try:
            proposed_move, reasoning = _parse_move_response(raw_response)
        except ValueError as exc:
            message = f"Malformed model response: {exc}"
            return {
                "proposed_move": None,
                "reasoning": None,
                "validation_valid": False,
                "failure_kind": "malformed_response",
                "error_message": message,
                "retry_feedback": {
                    "previous_response": raw_response,
                    "error": message,
                },
            }

        validation = game.validate_move(proposed_move)
        if not validation.valid:
            message = validation.error or "Move validation failed."
            return {
                "proposed_move": proposed_move,
                "reasoning": reasoning,
                "validation_valid": False,
                "failure_kind": "illegal_move",
                "error_message": message,
                "retry_feedback": {
                    "previous_response": raw_response,
                    "error": message,
                },
            }

        return {
            "proposed_move": validation.uci,
            "reasoning": reasoning,
            "validation_valid": True,
            "failure_kind": None,
            "error_message": None,
            "retry_feedback": None,
        }

    def execute_node(state: AIWorkflowState) -> dict[str, Any]:
        _assert_game_matches_state(game, state)
        if not state["validation_valid"] or state["proposed_move"] is None:
            raise RuntimeError("Cannot execute a move that has not passed validation.")
        execution = game.execute_move(state["proposed_move"])
        return {
            "move_execution": _json_value(execution),
            "fen": game.get_board_state().fen,
            "move_history_uci": _current_history_uci(game),
        }

    def check_status_node(_: AIWorkflowState) -> dict[str, Any]:
        return {
            "game_status": _serialize_game_status(game.get_game_status()),
            "completed": True,
            "success": True,
        }

    def failure_node(state: AIWorkflowState) -> dict[str, Any]:
        return {
            "attempts_exhausted": state["failure_kind"]
            in {"illegal_move", "malformed_response"}
            and state["attempt_count"] >= MAX_ATTEMPTS,
            "completed": True,
            "success": False,
        }

    def route_after_observe(
        state: AIWorkflowState,
    ) -> Literal["analyze_position", "handle_failure"]:
        if state["failure_kind"] is not None:
            return "handle_failure"
        return "analyze_position"

    def route_after_generate(
        state: AIWorkflowState,
    ) -> Literal["validate_move", "handle_failure"]:
        if state["failure_kind"] == "model_error":
            return "handle_failure"
        return "validate_move"

    def route_after_validate(
        state: AIWorkflowState,
    ) -> Literal["execute_move", "generate_move", "handle_failure"]:
        if state["validation_valid"]:
            return "execute_move"
        if state["attempt_count"] < MAX_ATTEMPTS:
            return "generate_move"
        return "handle_failure"

    graph = StateGraph(AIWorkflowState)
    graph.add_node("observe_position", observe_node)
    graph.add_node("analyze_position", analyze_node)
    graph.add_node("generate_move", generate_node)
    graph.add_node("validate_move", validate_node)
    graph.add_node("execute_move", execute_node)
    graph.add_node("check_game_status", check_status_node)
    graph.add_node("handle_failure", failure_node)
    graph.set_entry_point("observe_position")
    graph.add_conditional_edges(
        "observe_position",
        route_after_observe,
        {
            "analyze_position": "analyze_position",
            "handle_failure": "handle_failure",
        },
    )
    graph.add_edge("analyze_position", "generate_move")
    graph.add_conditional_edges(
        "generate_move",
        route_after_generate,
        {
            "validate_move": "validate_move",
            "handle_failure": "handle_failure",
        },
    )
    graph.add_conditional_edges(
        "validate_move",
        route_after_validate,
        {
            "execute_move": "execute_move",
            "generate_move": "generate_move",
            "handle_failure": "handle_failure",
        },
    )
    graph.add_edge("execute_move", "check_game_status")
    graph.add_edge("check_game_status", END)
    graph.add_edge("handle_failure", END)

    final_state = graph.compile().invoke(_initial_state(game))
    return AIWorkflowResult(state=final_state)


def _board_state_from_dict(data: dict[str, Any]) -> BoardState:
    return BoardState(
        fen=str(data["fen"]),
        side_to_move=str(data["side_to_move"]),
        in_check=bool(data["in_check"]),
        board=str(data["board"]),
    )
