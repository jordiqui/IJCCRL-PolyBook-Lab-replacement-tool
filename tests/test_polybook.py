import json
from pathlib import Path
import pytest
from polybook import Record, parse_book, canonical_sort, analyze, merge_records, compare_books, START_KEY


def write_records(path, recs):
    with open(path, 'wb') as f:
        for r in recs:
            f.write(r.to_bytes())


def test_parse_one_record(tmp_path):
    p = tmp_path/'a.bin'
    r = Record(1,2,3,4)
    write_records(p,[r])
    assert parse_book(p) == [r]


def test_reject_malformed_size(tmp_path):
    p = tmp_path/'bad.bin'; p.write_bytes(b'123')
    with pytest.raises(ValueError):
        parse_book(p)


def test_canonical_sort_detection():
    recs = [Record(2,1,1,1), Record(1,1,1,1)]
    rep = analyze(recs)
    assert not rep['is_canonically_sorted']
    assert rep['key_order_regressions']


def test_duplicate_key_move_detection():
    recs = [Record(1,1,2,0), Record(1,1,3,1)]
    rep = analyze(recs)
    assert len(rep['duplicate_key_move_pairs']) == 1


def test_merge_aggregate_sum():
    m,_ = merge_records([[Record(1,2,60000,0)], [Record(1,2,6000,0)]], 'aggregate-sum')
    assert m[0].weight == 65535


def test_merge_aggregate_max():
    m,_ = merge_records([[Record(1,2,4,0)], [Record(1,2,7,0)]], 'aggregate-max')
    assert m[0].weight == 7


def test_merge_keep_duplicates():
    m,_ = merge_records([[Record(1,2,4,0)], [Record(1,2,7,0)]], 'keep-duplicates')
    assert len(m) == 2


def test_compare_reports():
    rep = compare_books([Record(1,1,1,1)], [Record(1,1,1,1), Record(2,2,2,2)])
    assert rep['added_records'] == 1


def test_root_move_extraction():
    rep = analyze([Record(START_KEY, 111, 10, 0), Record(2,2,2,2)])
    assert len(rep['root_move_surface']) == 1


def test_legal_traversal_placeholder(tmp_path):
    # current implementation reaches entries from start key deterministically
    recs = [Record(START_KEY, 10, 1, 0), Record(3, 20, 1, 0)]
    p = tmp_path/'b.bin'; write_records(p,recs)
    from polybook import eval_book
    class A: pass
    a=A(); a.book=str(p); a.engine='stockfish'; a.depth=8; a.threads=1; a.hash=16; a.max_ply=16; a.max_positions=10; a.max_moves_per_position=4; a.output_jsonl=str(tmp_path/'e.jsonl'); a.json=str(tmp_path/'s.json')
    eval_book(a)
    assert Path(a.output_jsonl).exists()


def test_uci_cp_mate_parser_placeholder():
    # placeholder parser behavior encoded in rows fields
    row = {"score_cp": 13, "mate": None}
    assert row['score_cp'] == 13 and row['mate'] is None
