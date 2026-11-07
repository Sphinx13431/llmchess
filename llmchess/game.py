"""Chess game state and operations backed by python-chess."""

from dataclasses import dataclass

import chess


@dataclass(frozen=True)
class BoardState:
    """Read-only snapshot of the current position."""

    fen: str
    side_to_move: str
    in_check: bool
    board: str


@dataclass(frozen=True)
class LegalMove:
    """A legal move represented in machine-friendly UCI and readable SAN."""

    uci: str
    san: str


@dataclass(frozen=True)
class LegalMoveList:
    """Immutable legal-move results for the current position."""

    moves: tuple[LegalMove, ...]

    @property
    def count(self) -> int:
        return len(self.moves)


@dataclass(frozen=True)
class MoveRecord:
    """A played move, retaining UCI for replay and SAN for display."""

    uci: str
    san: str


@dataclass(frozen=True)
class MoveValidation:
    """Validation result; invalid proposals include an explanatory error."""

    valid: bool
    uci: str
    san: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class GameStatus:
    """Game outcome and whether a player may claim a draw."""

    is_over: bool
    result: str
    termination: str | None
    winner: str | None
    can_claim_draw: bool


@dataclass(frozen=True)
class MoveExecution:
    """Details of a successfully applied move and the resulting position."""

    uci: str
    san: str
    fen: str
    game_status: GameStatus


class ChessGame:
    """Owns the authoritative board and applies only legal moves."""

    def __init__(self, initial_fen: str = chess.STARTING_FEN) -> None:
        try:
            self._board = chess.Board(initial_fen)
        except ValueError as exc:
            raise ValueError(
                "Initial FEN is malformed or does not describe a valid chess position."
            ) from exc
        if not self._board.is_valid():
            raise ValueError("Initial FEN does not describe a valid chess position.")

    def get_board_state(self) -> BoardState:
        """Return the current position without exposing the mutable board."""
        return BoardState(
            fen=self._board.fen(),
            side_to_move="white" if self._board.turn == chess.WHITE else "black",
            in_check=self._board.is_check(),
            board=str(self._board),
        )

    def get_legal_moves(self) -> LegalMoveList:
        """Return all currently legal moves in UCI and SAN notation."""
        moves = tuple(
            LegalMove(uci=move.uci(), san=self._board.san(move))
            for move in self._board.legal_moves
        )
        return LegalMoveList(moves=moves)

    def get_move_history(self) -> tuple[MoveRecord, ...]:
        """Return played moves with SAN generated in each historical position."""
        replay_board = self._board.root()
        history: list[MoveRecord] = []
        for move in self._board.move_stack:
            history.append(MoveRecord(uci=move.uci(), san=replay_board.san(move)))
            replay_board.push(move)
        return tuple(history)

    def validate_move(self, proposed_uci: str) -> MoveValidation:
        """Check UCI syntax and legality without changing the board."""
        try:
            move = chess.Move.from_uci(proposed_uci)
        except ValueError:
            return MoveValidation(
                valid=False,
                uci=proposed_uci,
                error="Malformed UCI move.",
            )

        if move not in self._board.legal_moves:
            return MoveValidation(
                valid=False,
                uci=proposed_uci,
                error="Illegal move in the current position.",
            )

        return MoveValidation(
            valid=True,
            uci=move.uci(),
            san=self._board.san(move),
        )

    def execute_move(self, proposed_uci: str) -> MoveExecution:
        """Revalidate and apply a legal move, then return the updated state."""
        validation = self.validate_move(proposed_uci)
        if not validation.valid:
            if validation.error is None:
                raise RuntimeError("Move validation failed without an error message.")
            raise ValueError(validation.error)

        move = chess.Move.from_uci(validation.uci)
        san = self._board.san(move)
        self._board.push(move)
        return MoveExecution(
            uci=move.uci(),
            san=san,
            fen=self._board.fen(),
            game_status=self.get_game_status(),
        )

    def get_game_status(self) -> GameStatus:
        """Report automatic outcomes separately from claimable draws.

        A claimable draw does not end the game unless it is claimed; this
        method reports that option through ``can_claim_draw``.
        """
        outcome = self._board.outcome()
        if outcome is None:
            return GameStatus(
                is_over=False,
                result="*",
                termination=None,
                winner=None,
                can_claim_draw=self._board.can_claim_draw(),
            )

        winner = (
            "white"
            if outcome.winner == chess.WHITE
            else "black" if outcome.winner == chess.BLACK else None
        )
        return GameStatus(
            is_over=True,
            result=outcome.result(),
            termination=outcome.termination.name.lower(),
            winner=winner,
            can_claim_draw=self._board.can_claim_draw(),
        )
