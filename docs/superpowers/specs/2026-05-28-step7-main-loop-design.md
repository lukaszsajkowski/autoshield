# Step 7: Main Loop (`main.py`) — Design Spec

## Overview

Orchestrator that connects all modules into the research loop. Single async function `run_session()` with CLI wrapper via argparse. Loads best prompt, runs gauntlet, iterates with researcher, accepts/discards based on score, enforces budget and stagnation limits.

## File Structure

| File | Responsibility |
|---|---|
| `main.py` | `run_session()` async orchestrator + `if __name__ == "__main__"` CLI |
| `tests/test_main.py` | Integration test (baseline_only mode) |

## Core Function

```python
async def run_session(
    baseline_only: bool = False,
    max_iter: int | None = None,
    resume: bool = False,
) -> None
```

### Flow

1. Load `.env` via `dotenv.load_dotenv()`
2. Create `CostTracker(hard_limit=SESSION_COST_LIMIT)`
3. `load_best()` → `(version, prompt, best_score)`. If `resume=False` and version > 0, fall back to v0 (re-read `system_prompt.txt`)
4. Run baseline gauntlet: `run_gauntlet(prompt)` → print score
5. If `baseline_only` → print summary, return
6. Research loop:
   - `history = load_history()`
   - `proposal = propose_improvement(prompt, gauntlet_result, history)`
   - `new_result = run_gauntlet(proposal.new_prompt)`
   - **Accept** if `new_result.score >= best_score`:
     - `version += 1`
     - `save_version(version, proposal.new_prompt, meta)`
     - Update `best_score`, `prompt`, `gauntlet_result`
     - `stagnation = 0`
   - **Discard** if `new_result.score < best_score`:
     - `stagnation += 1`
   - `append_log(entry)` — always (both accepted and discarded)
   - `cost_tracker.check_budget()`
   - **Exit conditions** (checked after each iteration):
     - `best_score == 10` → SUCCESS
     - `stagnation >= MAX_STAGNATION` → EARLY EXIT
     - `BudgetExceeded` → BUDGET STOP
     - `iteration >= max_iter` (if set) → MAX ITER REACHED
7. Print summary: final score, iterations run, accepted count, total cost, best version path

### Log Entry Format

Each iteration appends a dict to `iterations.log`:

```python
{
    "iteration": int,
    "version": int,           # current best version number
    "score": int,             # score of the proposed prompt
    "best_score": int,        # best score so far
    "accepted": bool,
    "reasoning": str,         # from researcher
    "cost_so_far": float,
}
```

## CLI Interface

```bash
python main.py                    # full session
python main.py --baseline-only    # baseline only, no loop
python main.py --max-iter 10      # limited iterations
python main.py --resume           # resume from last saved version
```

Implemented via `argparse` in `if __name__ == "__main__"` block. Calls `asyncio.run(run_session(...))`.

## Error Handling

- `BudgetExceeded` → graceful stop, print "Budget exceeded at $X.XX", then print summary
- `ValueError` from researcher (invalid JSON, canary missing, etc.) → log as discarded iteration with `accepted=False`, increment stagnation, continue loop
- `KeyboardInterrupt` → graceful stop, print summary

## Output

Print to stdout at end of session:

```
=== AutoShield Session Summary ===
Final score: 8/10
Iterations: 15 (12 accepted, 3 discarded)
Total cost: $3.47
Best version: versions/v012.txt
Exit reason: Stagnation (3 consecutive no-improvement)
```

## Testing

Integration-level test only. This module wires everything together — individual modules are already tested.

- `test_baseline_only`: mock `AsyncOpenAI` globally, run `run_session(baseline_only=True)` with `tmp_path` for storage. Verify: gauntlet runs once, no research loop, summary printed.
- Real end-to-end validation is Step 8 (manual, with real API keys).

## Dependencies

Imports from all project modules:

- `config` — `SESSION_COST_LIMIT`, `MAX_STAGNATION`, `SYSTEM_PROMPT_FILE`
- `gauntlet` — `run_gauntlet`
- `researcher` — `propose_improvement`
- `storage` — `load_best`, `save_version`, `append_log`, `load_history`
- `costs` — `CostTracker`, `BudgetExceeded`
- `dotenv` — `load_dotenv`

## Design Decisions

1. **Single `run_session()` function** — not a class. Session state is local variables (best_score, version, stagnation counter). No need for class.
2. **Print to stdout** — MVP output. iterations.log and versions/ already persist full history. A separate report file adds complexity without value.
3. **ValueError from researcher → continue** — the research model may occasionally return invalid JSON. This shouldn't crash the session. Log as discarded, increment stagnation, try again.
4. **Resume flag** — allows continuing from last saved version after a crash or budget stop. Without it, always starts from v0.
5. **Minimal testing** — this is glue code. One integration test verifies the wiring works. Individual modules are thoroughly tested in their own test files.
