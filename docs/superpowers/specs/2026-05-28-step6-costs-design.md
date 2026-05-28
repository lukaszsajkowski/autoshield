# Step 6: Cost Tracker (`costs.py`) — Design Spec

## Overview

Session-level cost tracking with hard budget limit. Tracks API call costs by model and raises `BudgetExceeded` when the session exceeds the configured limit. The only stateful class in the project — accumulates costs across a session.

## File Structure

| File | Responsibility |
|---|---|
| `costs.py` | `CostTracker` class, `BudgetExceeded` exception, `MODEL_PRICING` dict |
| `tests/test_costs.py` | Pure tests (no mocks needed) |

## Model Pricing

Hardcoded dict, prices per 1M tokens (input, output):

```python
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "o4-mini": (1.10, 4.40),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}
```

## BudgetExceeded Exception

```python
class BudgetExceeded(Exception):
    def __init__(self, total_cost: float, limit: float)
```

Custom exception (not ValueError) so main.py can distinguish budget stops from validation errors.

## CostTracker Class

```python
class CostTracker:
    def __init__(self, hard_limit: float = 20.0)
    def record(self, model: str, prompt_tokens: int, completion_tokens: int) -> None
    def check_budget(self) -> None
    @property
    def total_cost(self) -> float
```

### `record(model, prompt_tokens, completion_tokens)`

- Looks up `(input_price, output_price)` from `MODEL_PRICING`
- Calculates: `(prompt_tokens * input_price + completion_tokens * output_price) / 1_000_000`
- Adds to internal `total_cost` accumulator
- Unknown model → raises `ValueError`

### `check_budget()`

- If `total_cost >= hard_limit` → raises `BudgetExceeded(total_cost, hard_limit)`
- Otherwise does nothing

### `total_cost` property

- Returns accumulated cost as float (USD)

## Testing

Pure tests, no mocks:

- Record single call → check total_cost matches manual calculation
- Record multiple calls with different models → costs accumulate
- Budget exceeded → raises BudgetExceeded
- Budget not exceeded → no exception
- Unknown model → raises ValueError
- Default hard_limit is 20.0
- BudgetExceeded has total_cost and limit attributes

## Design Decisions

1. **Class, not functions** — cost tracker accumulates state (total cost) across a session. This is the one place where a class is justified.
2. **Hardcoded pricing** — no public OpenAI pricing API. Dict is easy to update manually. Sufficient for MVP.
3. **Custom BudgetExceeded exception** — main.py needs to distinguish "budget exceeded" (graceful stop) from "validation error" (bug). ValueError would conflate the two.
4. **Fail-fast on unknown model** — ValueError if model not in pricing dict. Catches typos and missing model configs immediately rather than silently ignoring costs.
5. **Default limit from config** — `hard_limit` defaults to 20.0 (matching `SESSION_COST_LIMIT` in config), but is configurable per instance for testing.
