#!/usr/bin/env python3
"""
Community Chess Game for GitHub Profile README.
Processes chess moves from GitHub Issues, generates an SVG board,
and updates the profile README.
"""

import chess
import chess.svg
import chess.pgn
import json
import os
import sys
import io
import urllib.parse
from collections import defaultdict
from pathlib import Path

# --- Configuration ---
REPO = os.environ.get("REPOSITORY", "Kronten28/Kronten28")
REPO_OWNER = REPO.split("/")[0]
ISSUE_NUMBER = os.environ.get("EVENT_ISSUE_NUMBER", "0")
ISSUE_USER = os.environ.get("EVENT_USER_LOGIN", "unknown")
ISSUE_TITLE = os.environ.get("ISSUE_TITLE", "")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "chess" / "data"
STATS_FILE = DATA_DIR / "stats.json"
PGN_FILE = DATA_DIR / "game.pgn"
SVG_FILE = BASE_DIR / "chess_board.svg"
README_FILE = BASE_DIR / "README.md"

# Piece symbols for move table display
PIECE_EMOJI = {
    chess.PAWN: "\u265F",
    chess.KNIGHT: "\u265E",
    chess.BISHOP: "\u265D",
    chess.ROOK: "\u265C",
    chess.QUEEN: "\u265B",
    chess.KING: "\u265A",
}

PIECE_NAME = {
    chess.PAWN: "Pawn",
    chess.KNIGHT: "Knight",
    chess.BISHOP: "Bishop",
    chess.ROOK: "Rook",
    chess.QUEEN: "Queen",
    chess.KING: "King",
}


def load_stats():
    """Load persistent game statistics."""
    if STATS_FILE.exists():
        with open(STATS_FILE) as f:
            return json.load(f)
    return {
        "game_number": 1,
        "total_moves_all_games": 0,
        "leaderboard": {},
        "recent_moves": [],
        "last_mover": "",
    }


def save_stats(stats):
    """Save persistent game statistics."""
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)


def load_game():
    """Load the current chess game from PGN file."""
    if PGN_FILE.exists():
        content = PGN_FILE.read_text().strip()
        if content:
            pgn_io = io.StringIO(content)
            game = chess.pgn.read_game(pgn_io)
            if game:
                board = game.board()
                for move in game.mainline_moves():
                    board.push(move)
                return board, game
    return chess.Board(), chess.pgn.Game()


def save_game(board, pgn_game):
    """Save the current chess game to PGN file."""
    # Rebuild PGN from the board's move stack
    game = chess.pgn.Game()
    game.headers["Event"] = f"Kronten28 Community Game"
    game.headers["Site"] = f"https://github.com/{REPO}"
    game.headers["Date"] = "????.??.??"
    game.headers["Round"] = "?"
    game.headers["White"] = "Community (White)"
    game.headers["Black"] = "Community (Black)"

    if board.is_game_over():
        result = board.result()
    else:
        result = "*"
    game.headers["Result"] = result

    node = game
    temp_board = chess.Board()
    for move in board.move_stack:
        node = node.add_variation(move)
        temp_board.push(move)

    with open(PGN_FILE, "w") as f:
        print(game, file=f)


def generate_board_svg(board, last_move=None):
    """Generate a beautiful SVG chess board."""
    # Determine if king is in check
    check_square = None
    if board.is_check():
        check_square = board.king(board.turn)

    # Custom colors for a clean, modern look
    colors = {
        "square light": "#f0d9b5",
        "square dark": "#b58863",
        "square light lastmove": "#cdd16a",
        "square dark lastmove": "#aaa23a",
    }

    svg_content = chess.svg.board(
        board,
        lastmove=last_move,
        check=check_square,
        size=480,
        coordinates=True,
        colors=colors,
    )

    with open(SVG_FILE, "w") as f:
        f.write(svg_content)


def get_grouped_moves(board):
    """Get legal moves grouped by source piece, with SAN notation."""
    grouped = defaultdict(list)

    for move in board.legal_moves:
        piece = board.piece_at(move.from_square)
        if piece:
            square_name = chess.square_name(move.from_square)
            san = board.san(move)
            uci = move.uci()
            to_square = chess.square_name(move.to_square)
            grouped[(piece.piece_type, square_name)].append({
                "uci": uci,
                "san": san,
                "to": to_square.upper(),
            })

    # Sort by piece value (King first, then Queen, etc.) then by square
    piece_order = {chess.KING: 0, chess.QUEEN: 1, chess.ROOK: 2,
                   chess.BISHOP: 3, chess.KNIGHT: 4, chess.PAWN: 5}
    sorted_groups = sorted(grouped.items(),
                           key=lambda x: (piece_order.get(x[0][0], 99), x[0][1]))

    return sorted_groups


def get_game_status_text(board):
    """Get human-readable game status."""
    if board.is_checkmate():
        winner = "Black" if board.turn == chess.WHITE else "White"
        return f"**Checkmate!** {winner} wins!"
    elif board.is_stalemate():
        return "**Draw** by stalemate."
    elif board.is_insufficient_material():
        return "**Draw** by insufficient material."
    elif board.is_fifty_moves():
        return "**Draw** by fifty-move rule."
    elif board.is_repetition():
        return "**Draw** by threefold repetition."
    elif board.is_check():
        color = "White" if board.turn == chess.WHITE else "Black"
        return f"**{color} is in check!**"
    else:
        return "**Game in progress.**"


def get_turn_text(board):
    """Get whose turn it is."""
    if board.is_game_over():
        return "Game over"
    color = "White" if board.turn == chess.WHITE else "Black"
    return f"{color}'s turn"


def make_issue_link(repo, uci, game_num):
    """Create a GitHub Issue link for a chess move."""
    title = urllib.parse.quote(f"chess|move|{uci}|{game_num}")
    body = urllib.parse.quote("Just push 'Submit new issue'. You don't need to do anything else.")
    return f"https://github.com/{repo}/issues/new?title={title}&body={body}"


def get_captured_pieces(board):
    """Get lists of captured pieces for display."""
    # Starting material
    starting = {
        chess.PAWN: 8, chess.KNIGHT: 2, chess.BISHOP: 2,
        chess.ROOK: 2, chess.QUEEN: 1, chess.KING: 1,
    }

    white_captured = []  # black pieces that were captured
    black_captured = []  # white pieces that were captured

    for piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN]:
        white_on_board = len(board.pieces(piece_type, chess.WHITE))
        black_on_board = len(board.pieces(piece_type, chess.BLACK))

        # Captured white pieces (by black)
        white_missing = starting[piece_type] - white_on_board
        # Captured black pieces (by white)
        black_missing = starting[piece_type] - black_on_board

        piece_symbols_white = {
            chess.PAWN: "\u2659", chess.KNIGHT: "\u2658", chess.BISHOP: "\u2657",
            chess.ROOK: "\u2656", chess.QUEEN: "\u2655",
        }
        piece_symbols_black = {
            chess.PAWN: "\u265F", chess.KNIGHT: "\u265E", chess.BISHOP: "\u265D",
            chess.ROOK: "\u265C", chess.QUEEN: "\u265B",
        }

        for _ in range(black_missing):
            white_captured.append(piece_symbols_black[piece_type])
        for _ in range(white_missing):
            black_captured.append(piece_symbols_white[piece_type])

    return white_captured, black_captured


def generate_readme(board, stats, last_move=None):
    """Generate the profile README.md with the chess game."""
    game_num = stats["game_number"]
    status_text = get_game_status_text(board)
    turn_text = get_turn_text(board)
    total_moves = stats["total_moves_all_games"]
    current_moves = len(board.move_stack)
    white_captured, black_captured = get_captured_pieces(board)

    readme = []

    # Header
    readme.append(f"## {REPO_OWNER}'s Community Chess Tournament")
    readme.append("")
    readme.append(f"{status_text} This is open to **anyone** to play the next move. That's the point!")
    readme.append("")

    # Game info bar
    readme.append(f"> **Game #{game_num}** | **{turn_text}** | **Move {current_moves}** | **{total_moves} total moves** across all games")
    readme.append("")

    # Captured pieces
    if white_captured or black_captured:
        captured_parts = []
        if white_captured:
            captured_parts.append(f"White captured: {''.join(white_captured)}")
        if black_captured:
            captured_parts.append(f"Black captured: {''.join(black_captured)}")
        readme.append(f"> {' | '.join(captured_parts)}")
        readme.append("")

    # Board image
    readme.append(f"<p align=\"center\">")
    readme.append(f"  <img src=\"chess_board.svg\" alt=\"Chess Board\" width=\"480\" />")
    readme.append(f"</p>")
    readme.append("")

    if board.is_game_over():
        # New game button
        new_game_title = urllib.parse.quote("chess|new||0")
        new_game_body = urllib.parse.quote("Just push 'Submit new issue'. You don't need to do anything else.")
        new_game_link = f"https://github.com/{REPO}/issues/new?title={new_game_title}&body={new_game_body}"
        readme.append(f"### Game Over! [Click here to start a new game]({new_game_link})")
        readme.append("")
    else:
        # Available moves
        turn_color = "White" if board.turn == chess.WHITE else "Black"
        readme.append(f"### **{turn_color}'s move**, click a link to make your move!")
        readme.append("")

        grouped_moves = get_grouped_moves(board)

        readme.append("| Piece | From | Available Moves |")
        readme.append("| :---: | :---: | --- |")

        for (piece_type, from_square), moves in grouped_moves:
            emoji = PIECE_EMOJI.get(piece_type, "")
            name = PIECE_NAME.get(piece_type, "?")
            move_links = []
            for m in moves:
                link = make_issue_link(REPO, m["uci"], game_num)
                move_links.append(f"[{m['san']}]({link})")
            moves_str = " , ".join(move_links)
            readme.append(f"| {emoji} {name} | **{from_square.upper()}** | {moves_str} |")

        readme.append("")

    # Share link
    share_text = urllib.parse.quote(
        f"I'm playing chess on a GitHub Profile README! "
        f"Can you please take the next move at https://github.com/{REPO}"
    )
    readme.append(f"Share this game: [Post on X (Twitter)](https://x.com/intent/tweet?text={share_text})")
    readme.append("")

    # How it works
    readme.append("<details>")
    readme.append("<summary><strong>How does this work?</strong></summary>")
    readme.append("")
    readme.append("When you click a move link, it opens a GitHub Issue with a pre-filled title. "
                   "Just click **\"Submit new issue\"**, that's it! A [GitHub Action]"
                   "(https://github.blog/2020-07-03-github-action-hero-casey-lee/#getting-started-with-github-actions) "
                   "will process your move, update the board SVG, and refresh this README automatically.")
    readme.append("")
    readme.append(f"Notice a problem? [Raise an issue](https://github.com/{REPO}/issues) and tag `@{REPO_OWNER}`.")
    readme.append("</details>")
    readme.append("")

    # Recent moves
    readme.append("---")
    readme.append("")
    readme.append("#### Last 5 moves")
    readme.append("")
    if stats["recent_moves"]:
        readme.append("| # | Move | Player |")
        readme.append("| :-: | --- | --- |")
        for i, move_info in enumerate(stats["recent_moves"][:5]):
            move_num = current_moves - i
            san = move_info.get("san", f"{move_info['from']} to {move_info['to']}")
            user = move_info["user"]
            readme.append(f"| {move_num} | {san} | [@{user}](https://github.com/{user}) |")
    else:
        readme.append("*No moves yet, be the first!*")
    readme.append("")

    # Leaderboard
    readme.append("#### Top 20 players")
    readme.append("")
    leaderboard = sorted(stats["leaderboard"].items(), key=lambda x: -x[1])[:20]
    if leaderboard:
        readme.append("| Rank | Player | Moves |")
        readme.append("| :-: | --- | :-: |")
        for rank, (user, count) in enumerate(leaderboard, 1):
            medal = {1: "\U0001f947", 2: "\U0001f948", 3: "\U0001f949"}.get(rank, f"{rank}")
            readme.append(f"| {medal} | [@{user}](https://github.com/{user}) | {count} |")
    else:
        readme.append("*No moves yet, make a move to claim the top spot!*")
    readme.append("")

    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(readme))


def handle_new_game(stats):
    """Start a new chess game."""
    board = chess.Board()

    stats["game_number"] += 1
    stats["recent_moves"] = []
    stats["last_mover"] = ""

    save_game(board, None)
    save_stats(stats)
    generate_board_svg(board)
    generate_readme(board, stats)

    return board


def handle_move(uci_move_str, stats):
    """Process a chess move."""
    board, pgn_game = load_game()

    # Validate: don't let same user move twice in a row
    if stats["last_mover"] == ISSUE_USER and REPO == f"{REPO_OWNER}/{REPO_OWNER}":
        return None, "You just moved! Let someone else take the next turn."

    # Validate and apply the move
    try:
        move = chess.Move.from_uci(uci_move_str)
        if move not in board.legal_moves:
            return None, f"'{uci_move_str}' is not a legal move!"
    except ValueError:
        return None, f"'{uci_move_str}' is not a valid move format!"

    san = board.san(move)
    board.push(move)

    # Update stats
    stats["total_moves_all_games"] += 1
    stats["last_mover"] = ISSUE_USER
    stats["leaderboard"][ISSUE_USER] = stats["leaderboard"].get(ISSUE_USER, 0) + 1

    move_record = {
        "from": chess.square_name(move.from_square).upper(),
        "to": chess.square_name(move.to_square).upper(),
        "san": san,
        "user": ISSUE_USER,
    }
    stats["recent_moves"].insert(0, move_record)
    stats["recent_moves"] = stats["recent_moves"][:5]

    # Save everything
    save_game(board, pgn_game)
    save_stats(stats)
    generate_board_svg(board, last_move=move)
    generate_readme(board, stats, last_move=move)

    return board, None


def github_comment(message):
    """Post a comment on the triggering GitHub issue using gh CLI."""
    import subprocess
    subprocess.run(
        ["gh", "issue", "comment", ISSUE_NUMBER, "--repo", REPO, "--body", message],
        check=False,
    )


def github_close_issue():
    """Close the triggering GitHub issue using gh CLI."""
    import subprocess
    subprocess.run(
        ["gh", "issue", "close", ISSUE_NUMBER, "--repo", REPO],
        check=False,
    )


def main():
    """Main entry point, called by GitHub Action."""
    # Parse issue title: chess|command|move|gamenum
    parts = ISSUE_TITLE.split("|")

    if len(parts) < 2 or parts[0] != "chess":
        print("Not a chess command, ignoring.")
        sys.exit(0)

    command = parts[1]
    stats = load_stats()

    if command == "new":
        # Only repo owner can start new games (or if current game is over)
        board, _ = load_game()
        if ISSUE_USER != REPO_OWNER and not board.is_game_over():
            github_comment(f"@{ISSUE_USER} Only the repo owner or anyone after game over can start a new game.")
            github_close_issue()
            sys.exit(0)

        handle_new_game(stats)
        github_comment(f"@{ISSUE_USER} New game started! Head back to https://github.com/{REPO} to play.")
        github_close_issue()

    elif command == "move":
        if len(parts) < 3:
            github_comment(f"@{ISSUE_USER} No move specified.")
            github_close_issue()
            sys.exit(1)

        uci_move = parts[2]
        result, error = handle_move(uci_move, stats)

        if error:
            github_comment(f"@{ISSUE_USER} {error}")
            github_close_issue()
            sys.exit(0)

        if result and result.is_game_over():
            github_comment(f"@{ISSUE_USER} That's game over! Thanks for playing. "
                           f"View the result at https://github.com/{REPO}")
        else:
            github_comment(f"@{ISSUE_USER} Move played! View the board at https://github.com/{REPO}")

        github_close_issue()

    else:
        github_comment(f"@{ISSUE_USER} Unknown command: '{command}'")
        github_close_issue()
        sys.exit(0)


def init():
    """Generate initial board state for a fresh game (run locally)."""
    stats = load_stats()
    board = chess.Board()

    # Don't save PGN for initial state (empty game)
    generate_board_svg(board)
    generate_readme(board, stats)
    print(f"Initial board SVG written to: {SVG_FILE}")
    print(f"Initial README written to: {README_FILE}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        init()
    else:
        main()
