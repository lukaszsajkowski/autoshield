# Step 4: Research Agent (`researcher.py`) — Design Spec

## Overview

Research agent that analyzes gauntlet results and proposes improved system prompts. Single async function that calls a research model (GPT-4o), parses JSON response, and validates the proposed prompt. Uses `program.md` as agent instructions.

## File Structure

| File | Responsibility |
|---|---|
| `researcher.py` | `propose_improvement()` — load program.md, call research model, parse + validate response |
| `models.py` | Add `ResearchProposal` dataclass |
| `tests/test_researcher.py` | Validation tests + mocked API tests |

## Data Types

New dataclass in `models.py`:

```python
@dataclass
class ResearchProposal:
    new_prompt: str
    reasoning: str
```

## Researcher (`researcher.py`)

```python
async def propose_improvement(
    current_prompt: str,
    gauntlet_result: GauntletResult,
    history: list[dict],
) -> ResearchProposal
```

### Flow

1. Load `program.md` from disk as system prompt (using `PROGRAM_FILE` from config)
2. Build user message from three blocks:
   - `CURRENT SYSTEM PROMPT:` — the current prompt text
   - `GAUNTLET RESULTS:` — score, per-category pass/fail, failure details (attack + response for each failure)
   - `ITERATION HISTORY:` — last N iterations (what changed, score, accepted/discarded)
3. Call `AsyncOpenAI` with `RESEARCH_MODEL` from config (gpt-4o)
4. Parse JSON from response (`new_prompt` + `reasoning`) via `json.loads()`
5. Validate new prompt:
   - `new_prompt != current_prompt` (must differ)
   - `CANARY_STRING` present in new prompt
   - Token count ≤ `MAX_PROMPT_TOKENS` (2000) via `tiktoken`
6. If validation fails → raise `ValueError` with description of what's wrong
7. Return `ResearchProposal(new_prompt, reasoning)`

### Input Format

- `current_prompt: str` — the current best system prompt text
- `gauntlet_result: GauntletResult` — from gauntlet.py (score, per_category, failures)
- `history: list[dict]` — iteration history as dicts (compatible with JSONL from Step 5 storage). Researcher doesn't care where history comes from — receives it as argument.

### Error Handling

- Invalid JSON response → `ValueError("Research model returned invalid JSON")`
- Missing `new_prompt` or `reasoning` keys → `ValueError` with specifics
- Prompt unchanged → `ValueError("Proposed prompt is identical to current prompt")`
- Canary missing → `ValueError("Proposed prompt is missing the canary string")`
- Token limit exceeded → `ValueError("Proposed prompt exceeds token limit (N > 2000)")`

### Dependencies

- `tiktoken` — for accurate token counting (new dependency in pyproject.toml)
- `openai` — AsyncOpenAI for API calls
- `config.py` — RESEARCH_MODEL, CANARY_STRING, MAX_PROMPT_TOKENS, PROGRAM_FILE

## Testing

### Validation Tests (no mocks)

- Token count: short prompt passes, prompt exceeding 2000 tokens fails
- Canary: prompt with canary passes, without canary fails
- Unchanged: identical prompt fails
- Valid proposal: all checks pass

### API Tests (mocked)

- Happy path: mock returns valid JSON → `ResearchProposal` returned
- Invalid JSON: mock returns non-JSON → `ValueError` raised
- Mock `open()` for program.md loading
- Mock `AsyncOpenAI` for API calls

## Design Decisions

1. **Function, not class** — researcher holds no state between calls. History is passed as argument. Consistent with judge.py and gauntlet.py patterns.
2. **Full history as text (last N)** — gives research model maximum context for analysis. Token cost acceptable on MVP since history is bounded by iteration count.
3. **tiktoken for token counting** — accurate OpenAI token counting vs heuristic. Lightweight dependency, ensures prompts actually fit within the limit.
4. **ValueError for all validation failures** — simple, no custom exception hierarchy on MVP. Caller (main.py in Step 7) catches and logs.
5. **program.md loaded from disk each call** — no caching. File is small, read is fast, and allows hot-reloading if user edits program.md between iterations.
