import pytest

from costs import CostTracker, BudgetExceeded, MODEL_PRICING


def test_record_single_call():
    tracker = CostTracker(hard_limit=100.0)
    tracker.record("gpt-4o", prompt_tokens=1000, completion_tokens=500)
    assert abs(tracker.total_cost - 0.0075) < 1e-9


def test_record_multiple_models_accumulates():
    tracker = CostTracker(hard_limit=100.0)
    tracker.record("gpt-4o", prompt_tokens=1000, completion_tokens=500)
    tracker.record("o4-mini", prompt_tokens=2000, completion_tokens=1000)
    assert abs(tracker.total_cost - 0.0141) < 1e-9


def test_check_budget_not_exceeded():
    tracker = CostTracker(hard_limit=100.0)
    tracker.record("gpt-4o", prompt_tokens=1000, completion_tokens=500)
    tracker.check_budget()


def test_check_budget_exceeded():
    tracker = CostTracker(hard_limit=0.001)
    tracker.record("gpt-4o", prompt_tokens=1000, completion_tokens=500)
    with pytest.raises(BudgetExceeded) as exc_info:
        tracker.check_budget()
    assert exc_info.value.total_cost == tracker.total_cost
    assert exc_info.value.limit == 0.001


def test_unknown_model_raises():
    tracker = CostTracker()
    with pytest.raises(ValueError, match="Unknown model"):
        tracker.record("nonexistent-model", prompt_tokens=100, completion_tokens=50)


def test_default_hard_limit():
    tracker = CostTracker()
    assert tracker._hard_limit == 20.0


def test_initial_total_cost_is_zero():
    tracker = CostTracker()
    assert tracker.total_cost == 0.0
