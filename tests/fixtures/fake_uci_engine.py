#!/usr/bin/env python3
import sys

ENGINE_NAME = "IJCCRL Fake UCI Engine"
ENGINE_AUTHOR = "IJCCRL Test Harness"


def out(line: str) -> None:
    print(line, flush=True)


while True:
    line = sys.stdin.readline()
    if not line:
        break
    cmd = line.strip()
    if cmd == "uci":
        out(f"id name {ENGINE_NAME}")
        out(f"id author {ENGINE_AUTHOR}")
        out("option name Threads type spin default 1 min 1 max 1024")
        out("option name Hash type spin default 16 min 1 max 1048576")
        out("option name MultiPV type spin default 1 min 1 max 256")
        out("uciok")
    elif cmd == "isready":
        out("readyok")
    elif cmd.startswith("setoption name "):
        # Accept Threads/Hash/MultiPV/Clear Hash options.
        continue
    elif cmd == "ucinewgame":
        continue
    elif cmd.startswith("position fen "):
        continue
    elif cmd.startswith("go depth "):
        depth = cmd.split()[-1]
        out(f"info depth {depth} seldepth {depth} score cp 23 nodes 1234 nps 100000 time 10 pv e2e4 e7e5")
        out("bestmove e2e4")
    elif cmd == "quit":
        break
