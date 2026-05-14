# JSON Report Fields

## inspect
- `file`, `sha256`
- `total_records`, `unique_keys`, `unique_key_move_pairs`
- `is_canonically_sorted`, `key_order_regressions`
- `duplicate_key_move_pairs`, `duplicate_full_records`
- `branching_density_distribution`, `maximum_moves_per_key`
- `root_move_surface`
- `learn_field_distribution`

## compare
- `old` and `new` (same structure as inspect without file/checksum)
- `added_records`, `removed_records`
- `checksums`

## merge
- `policy`
- `inputs[]` with `path`, `sha256`
- `output` with `path`, `sha256`, `records`
- `conflicting_learn`
- `analysis` (inspect structure)

## eval
- `mode`, `book`, `engine`
- `config` (depth, threads, hash, max_ply, max_positions, max_moves_per_position)
- `positions_evaluated`
- `note`
