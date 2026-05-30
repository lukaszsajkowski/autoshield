MODEL_PRICING: dict[str, tuple[float, float]] = {
    "o4-mini": (1.10, 4.40),
    "o3-mini": (1.10, 4.40),
    "gpt-oss:20b": (0.0, 0.0),  # local Ollama model
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-5.2": (1.75, 14.00),
}


class BudgetExceeded(Exception):
    def __init__(self, total_cost: float, limit: float) -> None:
        self.total_cost = total_cost
        self.limit = limit
        super().__init__(
            f"Session budget exceeded: ${total_cost:.2f} >= ${limit:.2f} limit"
        )


class CostTracker:
    def __init__(self, hard_limit: float = 20.0) -> None:
        self._hard_limit = hard_limit
        self._total_cost = 0.0

    def record(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        if model not in MODEL_PRICING:
            raise ValueError(f"Unknown model: {model}")
        input_price, output_price = MODEL_PRICING[model]
        cost = (prompt_tokens * input_price + completion_tokens * output_price) / 1_000_000
        self._total_cost += cost

    def check_budget(self) -> None:
        if self._total_cost >= self._hard_limit:
            raise BudgetExceeded(self._total_cost, self._hard_limit)

    @property
    def total_cost(self) -> float:
        return self._total_cost
