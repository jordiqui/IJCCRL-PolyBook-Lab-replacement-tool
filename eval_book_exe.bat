@echo off
set BOOK=BOOK.bin
set ENGINE=C:\path\to\stockfish.exe
set DEPTH=8
set MAX_PLY=16
set MAX_POSITIONS=1000
set OUTPUT_JSONL=evals.jsonl
set SUMMARY_JSON=eval_summary.json

ijccrl-polybook.exe eval --book %BOOK% --engine %ENGINE% --depth %DEPTH% --threads 1 --hash 16 --max-ply %MAX_PLY% --max-positions %MAX_POSITIONS% --max-moves-per-position 8 --output-jsonl %OUTPUT_JSONL% --json %SUMMARY_JSON%
