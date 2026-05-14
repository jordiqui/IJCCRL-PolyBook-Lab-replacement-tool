@echo off
python polybook.py merge -o merged.bin --policy aggregate-sum %* --json merge_report.json
