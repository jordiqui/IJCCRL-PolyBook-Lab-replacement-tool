#!/usr/bin/env python3
import argparse, hashlib, json
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Tuple, Iterable

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
# Standard initial position key in polyglot
START_KEY = 0x463b96181691fc9c

@dataclass(frozen=True)
class Record:
    key: int
    move: int
    weight: int
    learn: int

    def to_bytes(self) -> bytes:
        return self.key.to_bytes(8, 'big') + self.move.to_bytes(2, 'big') + self.weight.to_bytes(2, 'big') + self.learn.to_bytes(4, 'big')


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def parse_book(path: Path) -> List[Record]:
    data = path.read_bytes()
    if len(data) % 16 != 0:
        raise ValueError(f"Invalid file size {len(data)}; not divisible by 16")
    recs = []
    for i in range(0, len(data), 16):
        b = data[i:i+16]
        recs.append(Record(int.from_bytes(b[0:8], 'big'), int.from_bytes(b[8:10], 'big'), int.from_bytes(b[10:12], 'big'), int.from_bytes(b[12:16], 'big')))
    return recs


def canonical_sort(recs: Iterable[Record]) -> List[Record]:
    return sorted(recs, key=lambda r: (r.key, r.move, r.weight, r.learn))


def analyze(recs: List[Record]) -> Dict:
    sorted_recs = canonical_sort(recs)
    is_canon = recs == sorted_recs
    regressions = []
    for i in range(1, len(recs)):
        if (recs[i-1].key, recs[i-1].move, recs[i-1].weight, recs[i-1].learn) > (recs[i].key, recs[i].move, recs[i].weight, recs[i].learn):
            regressions.append(i)

    keymove_counter = Counter((r.key, r.move) for r in recs)
    full_counter = Counter(recs)
    branch = Counter(keymove_counter_key[0] for keymove_counter_key in keymove_counter)
    density = Counter(branch.values())
    root_surface = [asdict(r) for r in recs if r.key == START_KEY]

    return {
        "total_records": len(recs),
        "unique_keys": len(set(r.key for r in recs)),
        "unique_key_move_pairs": len(set((r.key, r.move) for r in recs)),
        "is_canonically_sorted": is_canon,
        "key_order_regressions": regressions,
        "duplicate_key_move_pairs": [{"key": k, "move": m, "count": c} for (k, m), c in keymove_counter.items() if c > 1],
        "duplicate_full_records": [{"record": asdict(r), "count": c} for r, c in full_counter.items() if c > 1],
        "branching_density_distribution": {str(k): v for k, v in sorted(density.items())},
        "maximum_moves_per_key": max(branch.values()) if branch else 0,
        "root_move_surface": root_surface,
        "learn_field_distribution": {str(k): v for k, v in Counter(r.learn for r in recs).items()},
    }


def merge_records(record_sets: List[List[Record]], policy: str):
    all_recs = [r for rs in record_sets for r in rs]
    conflicts = []
    if policy == 'keep-duplicates':
        merged = canonical_sort(all_recs)
        return merged, conflicts

    grouped: Dict[Tuple[int,int], List[Record]] = defaultdict(list)
    for r in all_recs:
        grouped[(r.key, r.move)].append(r)

    merged = []
    for (k,m), vals in grouped.items():
        learns = set(v.learn for v in vals)
        if len(learns) > 1:
            conflicts.append({"key": k, "move": m, "learn_values": sorted(learns)})
        learn = vals[0].learn
        if policy == 'aggregate-sum':
            weight = min(65535, sum(v.weight for v in vals))
        elif policy == 'aggregate-max':
            weight = max(v.weight for v in vals)
        else:
            raise ValueError('Unknown policy')
        merged.append(Record(k,m,weight,learn))
    return canonical_sort(merged), conflicts


def compare_books(old: List[Record], new: List[Record]) -> Dict:
    oc, nc = Counter(old), Counter(new)
    added = sum((nc-oc).values())
    removed = sum((oc-nc).values())
    return {
        "old": analyze(old),
        "new": analyze(new),
        "added_records": added,
        "removed_records": removed,
    }

# Minimal placeholder traversal/eval scaffolding for deterministic reporting

def eval_book(args):
    recs = parse_book(Path(args.book))
    reachable = [r for r in recs if r.key == START_KEY][:args.max_moves_per_position]
    rows = []
    for idx, r in enumerate(reachable[:args.max_positions]):
        rows.append({"index": idx, "key": r.key, "move": r.move, "score_cp": 0, "mate": None, "pv": []})
    with open(args.output_jsonl, 'w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row)+"\n")
    summary = {
        "mode": "eval",
        "book": args.book,
        "engine": args.engine,
        "config": {
            "depth": args.depth, "threads": args.threads, "hash": args.hash, "max_ply": args.max_ply,
            "max_positions": args.max_positions, "max_moves_per_position": args.max_moves_per_position,
        },
        "positions_evaluated": len(rows),
        "note": "Polyglot keys are not inverted into FEN; traversal must come from seed FENs.",
    }
    Path(args.json).write_text(json.dumps(summary, indent=2), encoding='utf-8')


def write_report(path: str, obj: Dict):
    Path(path).write_text(json.dumps(obj, indent=2), encoding='utf-8')


def cmd_inspect(args):
    p = Path(args.book)
    recs = parse_book(p)
    rep = analyze(recs)
    rep.update({"file": args.book, "sha256": sha256_file(p)})
    write_report(args.json, rep)


def cmd_compare(args):
    p1,p2 = Path(args.old), Path(args.new)
    rep = compare_books(parse_book(p1), parse_book(p2))
    rep["checksums"] = {args.old: sha256_file(p1), args.new: sha256_file(p2)}
    write_report(args.json, rep)


def cmd_merge(args):
    paths = [Path(p) for p in args.books]
    parsed = [parse_book(p) for p in paths]
    merged, conflicts = merge_records(parsed, args.policy)
    out = Path(args.output)
    with out.open('wb') as f:
        for r in merged:
            f.write(r.to_bytes())
    rep = {
        "policy": args.policy,
        "inputs": [{"path": str(p), "sha256": sha256_file(p)} for p in paths],
        "output": {"path": str(out), "sha256": sha256_file(out), "records": len(merged)},
        "conflicting_learn": conflicts,
        "analysis": analyze(merged),
    }
    write_report(args.json, rep)


def build_parser():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('inspect'); p.add_argument('book'); p.add_argument('--json', required=True); p.set_defaults(func=cmd_inspect)
    p = sp.add_parser('compare'); p.add_argument('old'); p.add_argument('new'); p.add_argument('--json', required=True); p.set_defaults(func=cmd_compare)
    p = sp.add_parser('merge'); p.add_argument('-o','--output', required=True); p.add_argument('--policy', choices=['aggregate-sum','aggregate-max','keep-duplicates'], required=True); p.add_argument('books', nargs='+'); p.add_argument('--json', required=True); p.set_defaults(func=cmd_merge)
    p = sp.add_parser('eval'); p.add_argument('--book', required=True); p.add_argument('--engine', required=True); p.add_argument('--depth', type=int, default=8); p.add_argument('--threads', type=int, default=1); p.add_argument('--hash', type=int, default=16); p.add_argument('--max-ply', type=int, default=16); p.add_argument('--max-positions', type=int, default=100); p.add_argument('--max-moves-per-position', type=int, default=32); p.add_argument('--output-jsonl', required=True); p.add_argument('--json', required=True); p.set_defaults(func=eval_book)
    return ap


def main():
    args = build_parser().parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
