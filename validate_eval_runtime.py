#!/usr/bin/env python3
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd):
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def encode_polyglot_move(from_square: int, to_square: int, promotion: int = 0) -> int:
    return ((from_square & 0x3F) << 6) | (to_square & 0x3F) | ((promotion & 0x7) << 12)


print("IJCCRL PolyBook Lab — P2C Eval Runtime Validation")

try:
    import chess
    import chess.polyglot
except Exception:
    print("python-chess is required for eval runtime validation.")
    print("Install options:")
    print("  Windows: py -m pip install -r requirements.txt")
    print("  POSIX:   python -m pip install -r requirements.txt")
    print("  Offline: python -m pip install --no-index --find-links wheelhouse -r requirements.txt")
    raise SystemExit(2)

run([sys.executable, "polybook.py", "--version"])
run([sys.executable, "polybook.py", "--help"])
run([sys.executable, "-m", "pytest", "-q"])

with tempfile.TemporaryDirectory(prefix="polybook_p2c_") as td:
    temp = Path(td)
    book = temp / "tiny_opening.bin"
    out_jsonl = temp / "sample.eval.jsonl"
    out_summary = temp / "sample.eval.summary.json"
    b = chess.Board()
    key = chess.polyglot.zobrist_hash(b)
    records = [
        (key, encode_polyglot_move(chess.E2, chess.E4), 20, 0),
        (key, encode_polyglot_move(chess.D2, chess.D4), 10, 0),
        (key, encode_polyglot_move(chess.A1, chess.A8), 5, 0),
    ]
    with book.open("wb") as f:
        for rec in records:
            f.write(struct.pack(">QHHI", *rec))
    before = sha256(book)

    run([
        sys.executable,
        "polybook.py",
        "eval",
        "--book", str(book),
        "--engine", str(Path("tests/fixtures/fake_uci_engine.py")),
        "--depth", "8",
        "--threads", "1",
        "--hash", "16",
        "--max-ply", "2",
        "--max-positions", "10",
        "--max-moves-per-position", "2",
        "--output-jsonl", str(out_jsonl),
        "--json", str(out_summary),
    ])

    after = sha256(book)
    if before != after:
        raise SystemExit("Input BIN checksum changed after eval.")
    if not out_jsonl.exists() or not out_summary.exists():
        raise SystemExit("Expected eval evidence files were not created.")

    rows = [json.loads(line) for line in out_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    candidate_rows = [r for r in rows if r.get("row_type") == "candidate_move_eval"]
    if not candidate_rows:
        raise SystemExit("No candidate_move_eval rows found in JSONL.")
    row = candidate_rows[0]
    assert row.get("engine_id_name") == "IJCCRL Fake UCI Engine"
    assert row.get("engine_id_author") == "IJCCRL Test Harness"
    assert row.get("score_type") == "cp"
    assert row.get("score_value") == 23
    assert row.get("bestmove")
    assert row.get("pv")

    summary = json.loads(out_summary.read_text(encoding="utf-8"))
    for k in ["reachable_positions", "evaluated_candidate_moves", "illegal_book_moves", "warnings", "exit_status"]:
        if k not in summary:
            raise SystemExit(f"Missing summary key: {k}")

print("P2C eval runtime validation passed.")
