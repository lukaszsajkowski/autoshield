# Step 5: Versioning & Persistence (`storage.py`) — Design Spec

## Overview

File-based persistence for prompt versions and iteration logs. Four pure functions — no state, no database. Reads/writes to `versions/` directory and `iterations.log` JSONL file.

## File Structure

| File | Responsibility |
|---|---|
| `storage.py` | `save_version()`, `load_best()`, `append_log()`, `load_history()` |
| `tests/test_storage.py` | Round-trip tests using pytest `tmp_path` fixture |

## Functions

### `save_version(version: int, prompt: str, meta: dict) -> None`

- Creates `versions/` directory if it doesn't exist
- Writes `versions/vNNN.txt` with prompt text
- Writes `versions/vNNN.meta.json` with meta dict as JSON
- Version numbers zero-padded to 3 digits (v000, v001, ..., v999)

### `load_best() -> tuple[int, str, int]`

Returns `(version, prompt, score)`.

- Scans `versions/` for `vNNN.txt` files
- Takes the highest version number
- Reads prompt from `.txt`, score from `.meta.json` (`meta["score"]`)
- If no versions exist → reads `system_prompt.txt` (via `SYSTEM_PROMPT_FILE` from config), returns `(0, prompt_text, 0)`

### `append_log(entry: dict) -> None`

- Appends one JSON line to `iterations.log` (via `ITERATIONS_LOG` from config)
- Creates file if it doesn't exist

### `load_history(last_n: int = 10) -> list[dict]`

- Reads `iterations.log`, parses JSONL
- Returns last `last_n` entries
- If file doesn't exist → returns `[]`

## On-Disk Format

### Versions

```
versions/v000.txt          — plain text prompt
versions/v000.meta.json    — {"score": 3, "reasoning": "...", ...}
versions/v001.txt
versions/v001.meta.json
```

### Iterations Log

```
iterations.log             — JSONL, one dict per line, append-only
{"iteration": 1, "version": 1, "score": 5, "accepted": true, "reasoning": "..."}
{"iteration": 2, "version": 1, "score": 4, "accepted": false, "reasoning": "..."}
```

## Testing

All tests use pytest `tmp_path` fixture and monkeypatch config constants. No mocking of I/O functions.

- `save_version` + `load_best` round-trip: save v1, load → get v1 back
- `save_version` multiple versions: save v1, v2 → load_best returns v2
- `load_best` fallback: no versions dir → reads system_prompt.txt, returns (0, prompt, 0)
- `append_log` + `load_history` round-trip: append 3 entries, load last 2 → get last 2
- `load_history` missing file → returns `[]`
- `load_history` default last_n: append 15, load default → get last 10

## Design Decisions

1. **Pure functions, no state** — consistent with judge.py, gauntlet.py, researcher.py patterns. No class needed.
2. **JSONL for iterations.log** — append-only, human-readable, one dict per line. Easy to parse, grep, and tail.
3. **Zero-padded version numbers** — `v000` through `v999`. Sorts correctly in filesystem. 999 versions is far more than any session will produce.
4. **Fallback to system_prompt.txt** — storage knows where v0 lives (via config). Caller doesn't need to handle "no versions yet" case.
5. **tmp_path testing** — pytest provides temporary directories per test. No need to mock open/os functions. Tests exercise real file I/O.
