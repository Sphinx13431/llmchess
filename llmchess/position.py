"""Position snapshots and objective facts derived from a chess position."""

from dataclasses import dataclass

import chess

from .game import (
    BoardState,
    ChessGame,
    GameStatus,
    LegalMove,
    LegalMoveList,
    MoveRecord,
)

_PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}


@dataclass(frozen=True)
class PositionSnapshot:
    """Observed game data for the current position, without derived analysis."""

    board_state: BoardState
    legal_moves: LegalMoveList
    move_history: tuple[MoveRecord, ...]
    game_status: GameStatus


@dataclass(frozen=True)
class PieceFacts:
    """Attack-map facts for one piece, expressed as board-square names."""

    square: str
    piece: str
    color: str
    attacked_by: tuple[str, ...]
    defended_by: tuple[str, ...]


@dataclass(frozen=True)
class PositionAnalysis:
    """Objective material and legal-move facts for the current position.

    Attacked pieces have at least one opponent attack-map attacker.
    Undefended pieces are non-kings with no friendly attack-map defenders.
    Available checks and captures are legal moves for the side to move.
    """

    material_balance: int
    attacked_pieces: tuple[PieceFacts, ...]
    undefended_pieces: tuple[PieceFacts, ...]
    available_checks: tuple[LegalMove, ...]
    available_captures: tuple[LegalMove, ...]


@dataclass(frozen=True)
class PositionContext:
    """Combined observation and analysis suitable for an agent prompt."""

    snapshot: PositionSnapshot
    analysis: PositionAnalysis


def observe_position(game: ChessGame) -> PositionSnapshot:
    """Collect the current board, legal moves, history, and game status."""
    return PositionSnapshot(
        board_state=game.get_board_state(),
        legal_moves=game.get_legal_moves(),
        move_history=game.get_move_history(),
        game_status=game.get_game_status(),
    )


def analyze_position(board_state: BoardState) -> PositionAnalysis:
    """Derive objective facts from a board snapshot without mutating the game.

    Material balance uses pawn units, positive for White and negative for
    Black. Attack and defense mean square control according to python-chess;
    they do not imply that a piece is tactically safe or lost. Kings may be
    reported as attacked, but are excluded from undefended pieces.
    """
    board = chess.Board(board_state.fen)
    material_balance = sum(
        _PIECE_VALUES.get(piece.piece_type, 0)
        * (1 if piece.color == chess.WHITE else -1)
        for piece in board.piece_map().values()
    )

    attacked_pieces: list[PieceFacts] = []
    undefended_pieces: list[PieceFacts] = []
    for square, piece in sorted(board.piece_map().items()):
        attackers = tuple(
            sorted(
                chess.square_name(attacker)
                for attacker in board.attackers(not piece.color, square)
            )
        )
        defenders = tuple(
            sorted(
                chess.square_name(defender)
                for defender in board.attackers(piece.color, square)
            )
        )
        facts = PieceFacts(
            square=chess.square_name(square),
            piece=chess.piece_name(piece.piece_type),
            color="white" if piece.color == chess.WHITE else "black",
            attacked_by=attackers,
            defended_by=defenders,
        )
        if attackers:
            attacked_pieces.append(facts)
        if piece.piece_type != chess.KING and not defenders:
            undefended_pieces.append(facts)

    checks: list[LegalMove] = []
    captures: list[LegalMove] = []
    for move in sorted(board.legal_moves, key=lambda legal_move: legal_move.uci()):
        legal_move = LegalMove(uci=move.uci(), san=board.san(move))
        if board.gives_check(move):
            checks.append(legal_move)
        if board.is_capture(move):
            captures.append(legal_move)

    return PositionAnalysis(
        material_balance=material_balance,
        attacked_pieces=tuple(attacked_pieces),
        undefended_pieces=tuple(undefended_pieces),
        available_checks=tuple(checks),
        available_captures=tuple(captures),
    )


def build_position_context(game: ChessGame) -> PositionContext:
    """Assemble observed game state and separately derived position facts."""
    snapshot = observe_position(game)
    return PositionContext(
        snapshot=snapshot,
        analysis=analyze_position(snapshot.board_state),
    )
