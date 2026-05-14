IJCCRL PolyBook executable release

Executable:
- dist\ijccrl-polybook.exe

What it does:
- Replaces operational use of legacy poly17 executables for essential Polyglot/BIN workflows.
- Supports inspect, compare, merge, and eval commands from a standalone executable.

Polyglot/BIN format:
- Standard Polyglot opening book binary format.
- Each record is exactly 16 bytes: key(8) move(2) weight(2) learn(4), big-endian.
- Files with size not divisible by 16 are rejected.

Safe operations:
- inspect: read-only analysis + deterministic JSON report.
- compare: read-only comparison + deterministic JSON report.
- merge: writes canonical sorted standard BIN output.
- eval: writes external JSONL/JSON reports only; does not mutate BIN by default.

Command reference:
- ijccrl-polybook.exe --help
- ijccrl-polybook.exe --version
- ijccrl-polybook.exe inspect BOOK.bin --json report.json
- ijccrl-polybook.exe compare OLD.bin NEW.bin --json report.json
- ijccrl-polybook.exe merge -o OUT.bin --policy aggregate-sum BOOK1.bin BOOK2.bin --json merge_report.json
- ijccrl-polybook.exe eval --book BOOK.bin --engine PATH_TO_UCI_ENGINE --depth 8 --threads 1 --hash 16 --max-ply 16 --max-positions 1000 --output-jsonl evals.jsonl --json eval_summary.json

JSON reports:
- Generated deterministically with stable ordering and indentation.
- Outputs are written only to user-requested paths.

Release folder layout:
- dist\ijccrl-polybook.exe
- dist\examples\
- dist\reports\
- dist\books\
- dist\README_EXECUTABLE.txt

Why replace, not patch, poly17:
- Clean-room replacement keeps behavior auditable, reproducible, and maintainable.
- No reverse engineering or binary patching of legacy executables.


POLYBOOK-P2 eval notes:
- Keys cannot be inverted to FEN; eval traverses legally from seed FEN(s).
- Use --dry-run for traversal-only evidence/summary output.
- BIN is not modified by default.
- Example: ijccrl-polybook.exe eval --book BOOK.bin --engine C:\path\stockfish.exe --depth 8 --threads 1 --hash 16 --max-ply 16 --max-positions 1000 --max-moves-per-position 8 --output-jsonl evals.jsonl --json eval_summary.json


Dependency note: eval requires python-chess plus a UCI engine (`py -m pip install python-chess` on Windows, or `python -m pip install python-chess` on POSIX shells).
inspect/compare/merge and top-level `--help`/`--version` do not require python-chess or Stockfish at CLI startup.
Project tests validate eval using a deterministic fake UCI engine and do not require Stockfish.


## P2C eval runtime validation
- inspect/compare/merge do not require python-chess or Stockfish at CLI startup.
- eval requires python-chess and a UCI engine path.
- Unit tests use `tests/fixtures/fake_uci_engine.py` (deterministic), not Stockfish.
- Full P2C closure requires python-chess installed so eval tests run instead of skip.
- Network-restricted/Codex environments may legitimately skip eval tests when python-chess cannot be installed.
- `python validate_eval_runtime.py` is the authoritative dependency-present validation script (`validate_eval_runtime.bat` on Windows).
- No `.bin` fixture is committed; tiny Polyglot books are generated at runtime in temporary directories.
- Eval evidence is written as external JSONL/JSON files and does not mutate the input BIN.
- Optional offline install flow: place `python_chess*.whl` into `wheelhouse/`, then run `python -m pip install --no-index --find-links wheelhouse -r requirements.txt`.
