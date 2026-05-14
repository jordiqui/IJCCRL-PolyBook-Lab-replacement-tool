# IJCCRL PolyBook Lab Replacement Tool

Auditable Polyglot/BIN utility replacing legacy poly17 workflows.

## Features
- Inspect Polyglot `.bin` books with deterministic JSON reports.
- Compare two books and quantify added/removed records.
- Merge books with canonical ordering and explicit policies.
- Detect malformed file sizes, sort regressions, duplicates, and learn conflicts.
- Emit SHA-256 checksums for input/output auditability.
- Optional external-engine evaluation summary with external JSONL sidecar output.

## Polyglot Record Format
Each record is exactly 16 bytes:
- uint64 `key` (big-endian)
- uint16 `move` (big-endian)
- uint16 `weight` (big-endian)
- uint32 `learn` (big-endian)

Files whose size is not divisible by 16 are rejected.

## CLI

```bash
python polybook.py inspect BOOK.bin --json report.json
python polybook.py compare OLD.bin NEW.bin --json report.json
python polybook.py merge -o OUT.bin --policy aggregate-sum BOOK1.bin BOOK2.bin --json report.json
python polybook.py eval --book BOOK.bin --engine PATH_TO_UCI_ENGINE --depth 8 --threads 1 --hash 16 --max-ply 16 --max-positions 100 --max-moves-per-position 32 --output-jsonl evals.jsonl --json summary.json
```

## Merge Policies
- `aggregate-sum`: sum duplicate key+move weights with uint16 saturation (65535).
- `aggregate-max`: keep maximum weight among duplicate key+move pairs.
- `keep-duplicates`: keep all records, still canonical-sort output.

Conflict reporting is emitted when duplicate key+move entries contain different `learn` values.

## Evaluation Notes
- Polyglot keys are **not invertible** to FEN.
- Evaluation output is externalized to JSONL/CSV-style sidecars, not stored in BIN by default.
- Any future learn-field annotation should be gated behind explicit flags and documented as non-standard.

## Tests

```bash
python -m pytest -q
```

Covers parser correctness, malformed-size rejection, canonical sorting checks, duplicate detection, merge policy behavior, compare behavior, root move extraction, deterministic traversal placeholder, and UCI score field handling.

## Windows Launchers
- `inspect_polybook.bat`
- `merge_polybooks.bat`
- `eval_polybook.bat`

## Additional docs
- `JSON_SCHEMA.md`
- `MIGRATION_NOTE.md`


## Windows executable build (POLYBOOK-P1)

```bat
build_exe.bat
```

This produces `dist/ijccrl-polybook.exe` and release folders (`dist/examples`, `dist/reports`, `dist/books`) plus `dist/README_EXECUTABLE.txt`.

Windows launcher wrappers that call the executable directly:
- `inspect_book_exe.bat`
- `compare_books_exe.bat`
- `merge_books_exe.bat`
- `eval_book_exe.bat`
