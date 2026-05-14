@echo off
python polybook.py eval --book %1 --engine %2 --depth 8 --threads 1 --hash 16 --max-ply 16 --max-positions 100 --max-moves-per-position 32 --output-jsonl evals.jsonl --json eval_summary.json
