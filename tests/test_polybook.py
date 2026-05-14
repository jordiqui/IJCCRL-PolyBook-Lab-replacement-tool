import json
import subprocess
import sys
import hashlib
import struct
from pathlib import Path

import pytest

from polybook import Record, START_FEN, START_KEY, compare_books, decode_polyglot_move, merge_records, parse_book, parse_uci_info_line, version_string


def write_records(path, recs):
    with open(path, "wb") as f:
        for r in recs:
            f.write(r.to_bytes())


def run_cli(*args):
    return subprocess.run([sys.executable, "polybook.py", *args], capture_output=True, text=True)


def enc(frm, to, promo=0):
    return to + (8 * (to // 8))


try:
    import chess
    import chess.polyglot
except ImportError:
    chess = None

FIXTURES = Path("tests/fixtures")
FAKE_ENGINE = FIXTURES / "fake_uci_engine.py"


def encode_move(uci: str) -> int:
    if chess is None:
        raise RuntimeError("python-chess unavailable")
    mv = chess.Move.from_uci(uci)
    return mv.to_square % 8 | ((mv.to_square // 8) << 3) | ((mv.from_square % 8) << 6) | ((mv.from_square // 8) << 9) | ({None: 0, chess.KNIGHT: 1, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 4}[mv.promotion] << 12)


def sample_book(tmp_path):
    if chess is None:
        raise RuntimeError("python-chess unavailable")
    b = chess.Board(START_FEN)
    k0 = chess.polyglot.zobrist_hash(b)
    m1 = chess.Move.from_uci("e2e4")
    b.push(m1)
    k1 = chess.polyglot.zobrist_hash(b)
    recs = [
        Record(k0, encode_move("e2e4"), 20, 0),
        Record(k0, encode_move("d2d4"), 10, 0),
        Record(k0, encode_move("a1a8"), 5, 0),
        Record(k1, encode_move("e7e5"), 30, 0),
    ]
    p = tmp_path / "SAMPLE.bin"
    write_records(p, recs)
    return p


def encode_polyglot_move(from_square: int, to_square: int, promotion: int = 0) -> int:
    return (
        (to_square % 8)
        | ((to_square // 8) << 3)
        | ((from_square % 8) << 6)
        | ((from_square // 8) << 9)
        | (promotion << 12)
    )


def write_polyglot_record(handle, key: int, move: int, weight: int, learn: int = 0) -> None:
    handle.write(struct.pack(">QHHI", key, move, weight, learn))


def make_tiny_book(tmp_path: Path) -> Path:
    if chess is None:
        raise RuntimeError("python-chess unavailable")
    board = chess.Board(START_FEN)
    key = chess.polyglot.zobrist_hash(board)
    e2e4 = encode_polyglot_move(chess.E2, chess.E4)
    d2d4 = encode_polyglot_move(chess.D2, chess.D4)
    illegal = encode_polyglot_move(chess.A1, chess.A8)
    records = sorted(
        [
            (key, e2e4, 20, 0),
            (key, d2d4, 10, 0),
            (key, illegal, 5, 0),
        ],
        key=lambda r: (r[0], r[1], r[2], r[3]),
    )
    book_path = tmp_path / "tiny_opening.bin"
    with book_path.open("wb") as handle:
        for rec in records:
            write_polyglot_record(handle, *rec)
    return book_path


@pytest.mark.skipif(chess is None, reason="python-chess unavailable")
def test_decode_e2e4():
    assert decode_polyglot_move(encode_move("e2e4")) == "e2e4"


@pytest.mark.skipif(chess is None, reason="python-chess unavailable")
def test_decode_promotion_e7e8q():
    assert decode_polyglot_move(encode_move("e7e8q")) == "e7e8q"


@pytest.mark.skipif(chess is None, reason="python-chess unavailable")
def test_illegal_move_skipped(tmp_path):
    b = sample_book(tmp_path)
    outj = tmp_path / "s.json"
    r = run_cli("eval", "--book", str(b), "--dry-run", "--max-ply", "0", "--max-positions", "1", "--output-jsonl", str(tmp_path / "e.jsonl"), "--json", str(outj))
    assert r.returncode == 0
    rep = json.loads(outj.read_text())
    assert rep["illegal_book_moves"] == 1


@pytest.mark.skipif(chess is None, reason="python-chess unavailable")
def test_dry_run_outputs(tmp_path):
    b = make_tiny_book(tmp_path)
    j = tmp_path / "summary.json"
    jl = tmp_path / "rows.jsonl"
    r = run_cli("eval", "--book", str(b), "--dry-run", "--max-ply", "2", "--max-positions", "10", "--output-jsonl", str(jl), "--json", str(j))
    assert r.returncode == 0 and j.exists() and jl.exists()
    rows = [json.loads(line) for line in jl.read_text().splitlines()]
    assert rows and rows[0]["row_type"] == "candidate_move_eval"


def test_uci_info_cp_mate_bestmove_parser():
    cp = parse_uci_info_line("info depth 8 score cp 13 nodes 100 pv e2e4")
    mt = parse_uci_info_line("info depth 10 score mate -2 nodes 200 pv e2e4 e7e5")
    assert cp["score_type"] == "cp" and cp["score_value"] == 13
    assert mt["score_type"] == "mate" and mt["score_value"] == -2


@pytest.mark.skipif(chess is None, reason="python-chess unavailable")
def test_missing_engine_outside_dryrun(tmp_path):
    b = make_tiny_book(tmp_path)
    r = run_cli("eval", "--book", str(b), "--engine", str(tmp_path / "missing.exe"), "--depth", "8", "--output-jsonl", str(tmp_path / "e.jsonl"), "--json", str(tmp_path / "s.json"))
    assert r.returncode != 0


@pytest.mark.skipif(chess is None, reason="python-chess unavailable")
def test_eval_with_fake_engine_end_to_end(tmp_path):
    book = make_tiny_book(tmp_path)
    jl = tmp_path / "eval.jsonl"
    js = tmp_path / "summary.json"
    before = hashlib.sha256(book.read_bytes()).hexdigest()
    r = run_cli(
        "eval", "--book", str(book), "--engine", str(FAKE_ENGINE), "--depth", "8",
        "--threads", "1", "--hash", "16", "--max-ply", "2", "--max-positions", "10",
        "--max-moves-per-position", "2", "--output-jsonl", str(jl), "--json", str(js),
    )
    assert r.returncode == 0
    rows = [json.loads(line) for line in jl.read_text().splitlines()]
    assert rows and all(row["row_type"] == "candidate_move_eval" for row in rows)
    assert all(row["score_type"] == "cp" and row["score_value"] == 23 for row in rows)
    assert all(row["bestmove"] == "e2e4" for row in rows)
    assert all("e2e4 e7e5" in row.get("pv", "") for row in rows)
    assert all(row["engine_id_name"] == "IJCCRL Fake UCI Engine" for row in rows)
    assert all(row["engine_id_author"] == "IJCCRL Test Harness" for row in rows)
    assert [row["move_uci"] for row in rows] == ["e2e4", "d2d4"]
    summary = json.loads(js.read_text())
    assert summary["evaluated_candidate_moves"] == 2
    assert summary["reachable_positions"] == 3
    assert summary["illegal_book_moves"] == 1
    assert summary["warnings"] == []
    assert summary["exit_status"] == "ok"
    after = hashlib.sha256(book.read_bytes()).hexdigest()
    assert before == after


def test_compare_and_merge_still_work():
    m, _ = merge_records([[Record(1, 2, 1, 0)], [Record(1, 2, 3, 0)]], "aggregate-max")
    assert m[0].weight == 3
    rep = compare_books([Record(1, 1, 1, 1)], [Record(1, 1, 1, 1), Record(2, 2, 2, 2)])
    assert rep["added_records"] == 1


def test_version_help():
    assert run_cli("--version").returncode == 0
    assert version_string() in run_cli("--version").stdout
    assert "eval" in run_cli("--help").stdout


def test_inspect_compare_merge_without_chess_import(tmp_path):
    b1 = tmp_path / "a.bin"
    b2 = tmp_path / "b.bin"
    write_records(b1, [Record(1, 2, 3, 4)])
    write_records(b2, [Record(1, 2, 3, 4), Record(5, 6, 7, 8)])
    assert run_cli("inspect", str(b1), "--json", str(tmp_path / "i.json")).returncode == 0
    assert run_cli("compare", str(b1), str(b2), "--json", str(tmp_path / "c.json")).returncode == 0
    assert run_cli("merge", "-o", str(tmp_path / "m.bin"), "--policy", "aggregate-sum", str(b1), str(b2), "--json", str(tmp_path / "m.json")).returncode == 0


@pytest.mark.skipif(chess is not None, reason="requires python-chess missing in environment")
def test_eval_without_python_chess_fails_cleanly(tmp_path):
    b = tmp_path / "book.bin"
    write_records(b, [Record(START_KEY, 1, 1, 0)])
    out = run_cli("eval", "--book", str(b), "--dry-run", "--json", str(tmp_path / "s.json"))
    assert out.returncode != 0
    assert "requires python-chess" in out.stderr
