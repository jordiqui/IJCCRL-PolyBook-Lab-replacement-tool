#!/usr/bin/env python3
import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

IJCCRL_POLYBOOK_VERSION = "0.2.0-p2"
PHASE_NAME = "POLYBOOK-P2"
POLYGLOT_RECORD_SIZE = 16
TOOL_NAME = "IJCCRL PolyBook Lab"

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
START_KEY = 0x463B96181691FC9C


class PolyBookUserError(ValueError):
    pass


def require_python_chess() -> Tuple[Any, Any]:
    try:
        import chess
        import chess.polyglot
    except ImportError as exc:
        raise PolyBookUserError(
            "The eval command requires python-chess. Install it with: py -m pip install python-chess"
        ) from exc
    return chess, chess.polyglot


@dataclass(frozen=True)
class Record:
    key: int
    move: int
    weight: int
    learn: int

    def to_bytes(self) -> bytes:
        return (
            self.key.to_bytes(8, "big")
            + self.move.to_bytes(2, "big")
            + self.weight.to_bytes(2, "big")
            + self.learn.to_bytes(4, "big")
        )


def decode_polyglot_move(encoded: int) -> str:
    to_file = encoded & 0x7
    to_rank = (encoded >> 3) & 0x7
    from_file = (encoded >> 6) & 0x7
    from_rank = (encoded >> 9) & 0x7
    promo = (encoded >> 12) & 0x7
    s = f"{chr(ord('a') + from_file)}{from_rank + 1}{chr(ord('a') + to_file)}{to_rank + 1}"
    if promo:
        s += {1: "n", 2: "b", 3: "r", 4: "q"}.get(promo, "")
    return s


def parse_uci_info_line(line: str) -> Dict:
    parts = line.strip().split()
    out = {"score_type": "unknown", "score_value": None}
    if not parts or parts[0] != "info":
        return out
    i = 1
    while i < len(parts):
        tok = parts[i]
        if tok in {"depth", "seldepth", "nodes", "nps", "time", "multipv"} and i + 1 < len(parts):
            out[tok if tok != "time" else "time_ms"] = int(parts[i + 1])
            i += 2
        elif tok == "score" and i + 2 < len(parts):
            st, sv = parts[i + 1], parts[i + 2]
            if st == "cp":
                out["score_type"] = "cp"
                out["score_value"] = int(sv)
            elif st == "mate":
                out["score_type"] = "mate"
                out["score_value"] = int(sv)
            i += 3
        elif tok == "pv":
            out["pv"] = " ".join(parts[i + 1 :])
            break
        else:
            i += 1
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_book(path: Path) -> List[Record]:
    if not path.exists():
        raise FileNotFoundError(f"Book file not found: {path}")
    data = path.read_bytes()
    if len(data) % POLYGLOT_RECORD_SIZE != 0:
        raise ValueError(f"Invalid file size {len(data)} for {path}; expected multiple of {POLYGLOT_RECORD_SIZE} bytes")
    recs = []
    for i in range(0, len(data), POLYGLOT_RECORD_SIZE):
        b = data[i : i + POLYGLOT_RECORD_SIZE]
        recs.append(Record(int.from_bytes(b[0:8], "big"), int.from_bytes(b[8:10], "big"), int.from_bytes(b[10:12], "big"), int.from_bytes(b[12:16], "big")))
    return recs


def canonical_sort(recs: Iterable[Record]) -> List[Record]:
    return sorted(recs, key=lambda r: (r.key, r.move, r.weight, r.learn))

# ... keep old helpers unchanged

def analyze(recs: List[Record]) -> Dict:
    sorted_recs = canonical_sort(recs)
    regressions = []
    for i in range(1, len(recs)):
        if (recs[i - 1].key, recs[i - 1].move, recs[i - 1].weight, recs[i - 1].learn) > (recs[i].key, recs[i].move, recs[i].weight, recs[i].learn):
            regressions.append(i)
    keymove_counter = Counter((r.key, r.move) for r in recs)
    full_counter = Counter(recs)
    branch = Counter(k for (k, _) in keymove_counter)
    density = Counter(branch.values())
    root_surface = [asdict(r) for r in recs if r.key == START_KEY]
    return {"branching_density_distribution": {str(k): v for k, v in sorted(density.items())}, "duplicate_full_records": [{"record": asdict(r), "count": c} for r, c in full_counter.items() if c > 1], "duplicate_key_move_pairs": [{"key": k, "move": m, "count": c} for (k, m), c in keymove_counter.items() if c > 1], "is_canonically_sorted": recs == sorted_recs, "key_order_regressions": regressions, "learn_field_distribution": {str(k): v for k, v in Counter(r.learn for r in recs).items()}, "maximum_moves_per_key": max(branch.values()) if branch else 0, "root_move_surface": root_surface, "total_records": len(recs), "unique_key_move_pairs": len(set((r.key, r.move) for r in recs)), "unique_keys": len(set(r.key for r in recs))}


def merge_records(record_sets: List[List[Record]], policy: str):
    all_recs = [r for rs in record_sets for r in rs]
    conflicts = []
    if policy == "keep-duplicates":
        return canonical_sort(all_recs), conflicts
    grouped: Dict[Tuple[int, int], List[Record]] = defaultdict(list)
    for r in all_recs:
        grouped[(r.key, r.move)].append(r)
    merged = []
    for (k, m), vals in grouped.items():
        learns = set(v.learn for v in vals)
        if len(learns) > 1:
            conflicts.append({"key": k, "move": m, "learn_values": sorted(learns)})
        learn = vals[0].learn
        weight = min(65535, sum(v.weight for v in vals)) if policy == "aggregate-sum" else max(v.weight for v in vals)
        merged.append(Record(k, m, weight, learn))
    return canonical_sort(merged), conflicts


def compare_books(old: List[Record], new: List[Record]) -> Dict:
    oc, nc = Counter(old), Counter(new)
    return {"added_records": sum((nc - oc).values()), "new": analyze(new), "old": analyze(old), "removed_records": sum((oc - nc).values())}


class UCIEngine:
    def __init__(self, path: str):
        self.proc = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        self.id_name = None; self.id_author = None

    def send(self, cmd: str): self.proc.stdin.write(cmd + "\n"); self.proc.stdin.flush()
    def read_until(self, token: str) -> List[str]:
        lines = []
        while True:
            line = self.proc.stdout.readline()
            if not line: raise RuntimeError("UCI engine terminated unexpectedly")
            s = line.strip(); lines.append(s)
            if s.startswith("id name "): self.id_name = s[8:]
            if s.startswith("id author "): self.id_author = s[10:]
            if s == token: return lines

    def init(self, threads: int, hash_mb: int, multipv: int):
        self.send("uci"); self.read_until("uciok")
        self.send(f"setoption name Threads value {threads}")
        self.send(f"setoption name Hash value {hash_mb}")
        self.send(f"setoption name MultiPV value {multipv}")
        self.send("isready"); self.read_until("readyok")

    def eval_fen(self, fen: str, depth: Optional[int], movetime: Optional[int], clear_hash: bool) -> Dict:
        if clear_hash:
            self.send("setoption name Clear Hash")
            self.send("isready"); self.read_until("readyok")
        self.send(f"position fen {fen}")
        self.send(f"go depth {depth}" if depth is not None else f"go movetime {movetime}")
        result = {"score_type": "unknown", "score_value": None, "bestmove": None, "pv": ""}
        while True:
            line = self.proc.stdout.readline().strip()
            if line.startswith("info "):
                info = parse_uci_info_line(line)
                result.update({k: v for k, v in info.items() if v is not None})
            if line.startswith("bestmove "):
                result["bestmove"] = line.split()[1]
                return result

    def close(self):
        if self.proc.poll() is None:
            self.send("quit")
            self.proc.wait(timeout=2)


def eval_book(args):
    chess, chess_polyglot = require_python_chess()
    recs = parse_book(Path(args.book)); by_key = defaultdict(list)
    for r in recs: by_key[r.key].append(r)
    for k in by_key: by_key[k].sort(key=lambda r: (-r.weight, r.move, r.learn))
    if args.depth is not None and args.movetime is not None: raise ValueError("Use either --depth or --movetime, not both")
    if args.depth is None and args.movetime is None: args.depth = 8
    if not args.dry_run and (not args.engine or not Path(args.engine).exists()): raise FileNotFoundError(f"Engine file not found: {args.engine}")
    seed_fens = args.seed_fen or [START_FEN]
    for fen in seed_fens: chess.Board(fen)

    engine = None; warnings=[]; errors=[]
    if not args.dry_run:
        engine = UCIEngine(args.engine); engine.init(args.threads, args.hash, args.multipv)
    out = Path(args.output_jsonl) if args.output_jsonl else None
    if out: out.parent.mkdir(parents=True, exist_ok=True); f = out.open("w", encoding="utf-8")
    else: f = None
    visited=set(); q: Deque[Tuple[str,int,str]] = deque((fen,0,fen) for fen in seed_fens)
    reachable=evaluated_pos=evaluated_moves=illegal=skipped=maxply=0
    try:
        while q and reachable < args.max_positions:
            fen, ply, seed = q.popleft(); board=chess.Board(fen); key=chess_polyglot.zobrist_hash(board)
            state=(fen,ply)
            if state in visited: continue
            visited.add(state); reachable += 1; maxply=max(maxply,ply)
            entries = by_key.get(key, [])[: args.max_moves_per_position]
            legal_candidates=[]
            for e in entries:
                uci = decode_polyglot_move(e.move)
                mv = chess.Move.from_uci(uci)
                if mv in board.legal_moves: legal_candidates.append((e,uci,mv))
                else: illegal += 1
            if args.evaluate == "position":
                evaluated_pos += 1
                ev = {"score_type":"unknown","score_value":None,"bestmove":None,"pv":""} if args.dry_run else engine.eval_fen(fen,args.depth,args.movetime,args.clear_hash)
                row={"tool_name":TOOL_NAME,"tool_version":IJCCRL_POLYBOOK_VERSION,"phase":PHASE_NAME,"book_path":Path(args.book).name,"book_sha256":sha256_file(Path(args.book)),"engine_path":Path(args.engine).name if args.engine else None,"engine_id_name":engine.id_name if engine else None,"engine_id_author":engine.id_author if engine else None,"depth":args.depth,"movetime":args.movetime,"threads":args.threads,"hash_mb":args.hash,"multipv":args.multipv,"seed_fen":seed,"ply_from_seed":ply,"row_type":"position_eval","fen":fen,"polyglot_key":f"0x{key:016x}","legal_book_move_count":len(legal_candidates),"legal_status":"legal",**ev}
                if f: f.write(json.dumps(row, sort_keys=True)+"\n")
            else:
                for e,uci,mv in legal_candidates:
                    child=board.copy(); san=child.san(mv); child.push(mv)
                    child_fen=child.fen(); evaluated_moves += 1
                    ev={"score_type":"unknown","score_value":None,"bestmove":None,"pv":""} if args.dry_run else engine.eval_fen(child_fen,args.depth,args.movetime,args.clear_hash)
                    row={"tool_name":TOOL_NAME,"tool_version":IJCCRL_POLYBOOK_VERSION,"phase":PHASE_NAME,"book_path":Path(args.book).name,"book_sha256":sha256_file(Path(args.book)),"engine_path":Path(args.engine).name if args.engine else None,"engine_id_name":engine.id_name if engine else None,"engine_id_author":engine.id_author if engine else None,"depth":args.depth,"movetime":args.movetime,"threads":args.threads,"hash_mb":args.hash,"multipv":args.multipv,"seed_fen":seed,"ply_from_seed":ply,"row_type":"candidate_move_eval","parent_fen":fen,"child_fen":child_fen,"polyglot_key":f"0x{key:016x}","move_uci":uci,"encoded_move":e.move,"san":san,"weight":e.weight,"learn":e.learn,"legal_status":"legal",**ev}
                    if f: f.write(json.dumps(row, sort_keys=True)+"\n")
            if ply < args.max_ply:
                for _,_,mv in legal_candidates:
                    b2=board.copy(); b2.push(mv); q.append((b2.fen(),ply+1,seed))
        if q: skipped = len(q)
    finally:
        if f: f.close()
        if engine: engine.close()
    summary={"command":"eval","tool_name":TOOL_NAME,"version":IJCCRL_POLYBOOK_VERSION,"phase":PHASE_NAME,"timestamp_utc":datetime.now(timezone.utc).isoformat(),"book_path":str(args.book),"book_sha256":sha256_file(Path(args.book)),"engine_path":args.engine,"engine_id":{"name":engine.id_name if engine else None,"author":engine.id_author if engine else None},"depth":args.depth,"movetime":args.movetime,"threads":args.threads,"hash_mb":args.hash,"multipv":args.multipv,"seed_fens":seed_fens,"max_ply":args.max_ply,"max_positions":args.max_positions,"max_moves_per_position":args.max_moves_per_position,"evaluation_mode":args.evaluate,"output_jsonl_path":args.output_jsonl,"total_records_in_book":len(recs),"unique_keys_in_book":len(set(r.key for r in recs)),"reachable_positions":reachable,"evaluated_positions":evaluated_pos,"evaluated_candidate_moves":evaluated_moves,"illegal_book_moves":illegal,"skipped_due_to_limits":skipped,"max_reached_ply":maxply,"warnings":warnings,"errors":errors,"exit_status":"ok"}
    write_report(args.json, summary)


def write_report(path: str, obj: Dict):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(obj, indent=2, sort_keys=True)+"\n", encoding="utf-8")

def cmd_inspect(args):
    p = Path(args.book); rep = analyze(parse_book(p)); rep.update({"file": args.book, "sha256": sha256_file(p)}); write_report(args.json, rep)

def cmd_compare(args):
    p1,p2=Path(args.old),Path(args.new); rep=compare_books(parse_book(p1), parse_book(p2)); rep["checksums"]={args.old:sha256_file(p1), args.new:sha256_file(p2)}; write_report(args.json, rep)

def cmd_merge(args):
    paths=[Path(p) for p in args.books]; merged, conflicts=merge_records([parse_book(p) for p in paths], args.policy); out=Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        for r in merged: f.write(r.to_bytes())
    rep={"analysis":analyze(merged),"conflicting_learn":conflicts,"inputs":[{"path":str(p),"sha256":sha256_file(p)} for p in paths],"output":{"path":str(out),"records":len(merged),"sha256":sha256_file(out)},"policy":args.policy}; write_report(args.json,rep)

def version_string() -> str:
    return f"{TOOL_NAME} {IJCCRL_POLYBOOK_VERSION} — {PHASE_NAME} — Polyglot/BIN {POLYGLOT_RECORD_SIZE}-byte records"

def build_parser():
    ap=argparse.ArgumentParser(prog="ijccrl-polybook", description="IJCCRL PolyBook CLI"); ap.add_argument("--version", action="version", version=version_string()); sp=ap.add_subparsers(dest="cmd", required=True)
    p=sp.add_parser("inspect"); p.add_argument("book"); p.add_argument("--json", required=True); p.set_defaults(func=cmd_inspect)
    p=sp.add_parser("compare"); p.add_argument("old"); p.add_argument("new"); p.add_argument("--json", required=True); p.set_defaults(func=cmd_compare)
    p=sp.add_parser("merge"); p.add_argument("-o","--output",required=True); p.add_argument("--policy",choices=["aggregate-sum","aggregate-max","keep-duplicates"],required=True); p.add_argument("books",nargs="+"); p.add_argument("--json",required=True); p.set_defaults(func=cmd_merge)
    p=sp.add_parser("eval"); p.add_argument("--book",required=True); p.add_argument("--engine"); p.add_argument("--depth",type=int); p.add_argument("--movetime",type=int); p.add_argument("--threads",type=int,default=1); p.add_argument("--hash",type=int,default=16); p.add_argument("--max-ply",type=int,default=16); p.add_argument("--max-positions",type=int,default=1000); p.add_argument("--max-moves-per-position",type=int,default=8); p.add_argument("--seed-fen",action="append"); p.add_argument("--clear-hash",action="store_true"); p.add_argument("--multipv",type=int,default=1); p.add_argument("--evaluate",choices=["position","candidate-moves"],default="candidate-moves"); p.add_argument("--output-jsonl"); p.add_argument("--json",required=True); p.add_argument("--dry-run",action="store_true"); p.set_defaults(func=eval_book)
    return ap

def main()->int:
    parser=build_parser(); args=parser.parse_args()
    try:
        if args.cmd=="eval" and not args.dry_run and not args.output_jsonl: raise ValueError("--output-jsonl is required unless --dry-run is used")
        args.func(args); return 0
    except (FileNotFoundError, ValueError, RuntimeError, PolyBookUserError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr); return 2

if __name__=="__main__":
    raise SystemExit(main())
