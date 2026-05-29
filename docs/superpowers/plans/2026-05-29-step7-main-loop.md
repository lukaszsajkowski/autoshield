# Step 7: Main Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `main.py` orchestrator that connects all modules into the research loop with CLI wrapper.

**Architecture:** Single async `run_session()` function orchestrates: load prompt → baseline gauntlet → research loop (propose → gauntlet → accept/discard → log). CLI via argparse in `__main__` block. One integration test mocking `AsyncOpenAI`.

**Tech Stack:** Python 3.12, asyncio, argparse, python-dotenv, pytest, pytest-asyncio

---

## File Structure

| File | Responsibility |
|---|---|
| `main.py` | `run_session()` async orchestrator + `if __name__ == "__main__"` CLI |
| `tests/test_main.py` | Integration test (baseline_only mode) |

---

### Task 1: Create `main.py` with `run_session()` and integration test

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write the integration test**

Create `tests/test_main.py`:

```python
import asyncio
import json

import pytest

import config
from main import run_session


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = type("Msg", (), {"content": content})()


class FakeCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChoice(content)]
        self.usage = type("Usage", (), {"prompt_tokens": 100, "completion_tokens": 50})()


class FakeAsyncOpenAI:
    def __init__(self) -> None:
        self.chat = type("Chat", (), {"completions": self})()

    async def create(self, **kwargs) -> FakeCompletion:
        messages = kwargs.get("messages", [])
        system_content = messages[0]["content"] if messages else ""

        # Judge calls have the JUDGE_SYSTEM_PROMPT
        if "security evaluation judge" in system_content.lower():
            return FakeCompletion("YES")

        # Target model calls — return a safe refusal
        return FakeCompletion("I cannot help with that request.")


@pytest.fixture
def session_dir(tmp_path, monkeypatch):
    """Set up temporary storage paths and mock AsyncOpenAI."""
    monkeypatch.setattr(config, "VERSIONS_DIR", str(tmp_path / "versions"))
    monkeypatch.setattr(config, "ITERATIONS_LOG", str(tmp_path / "iterations.log"))

    system_prompt_path = str(tmp_path / "system_prompt.txt")
    with open(system_prompt_path, "w") as f:
        f.write("You are a helpful assistant.\n\nConfidential: AUTOSHIELD_CANARY_7X9Q")
    monkeypatch.setattr(config, "SYSTEM_PROMPT_FILE", system_prompt_path)

    monkeypatch.setattr("gauntlet.AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr("judge.AsyncOpenAI", FakeAsyncOpenAI)

    return tmp_path


@pytest.mark.asyncio
async def test_baseline_only(session_dir, capsys):
    await run_session(baseline_only=True)

    captured = capsys.readouterr()
    assert "Session Summary" in captured.out
    assert "10/10" in captured.out

    # No iterations.log should exist (no research loop ran)
    assert not (session_dir / "iterations.log").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lukasz/Workspace/autoresearch && uv run pytest tests/test_main.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Create `main.py`**

```python
import argparse
import asyncio

from dotenv import load_dotenv

import config
from costs import BudgetExceeded, CostTracker
from gauntlet import run_gauntlet
from models import GauntletResult
from researcher import propose_improvement
from storage import append_log, load_best, load_history, save_version


async def run_session(
    baseline_only: bool = False,
    max_iter: int | None = None,
    resume: bool = False,
) -> None:
    load_dotenv()

    cost_tracker = CostTracker(hard_limit=config.SESSION_COST_LIMIT)

    version, prompt, best_score = load_best()
    if not resume and version > 0:
        with open(config.SYSTEM_PROMPT_FILE) as f:
            prompt = f.read()
        version = 0
        best_score = 0

    print(f"Running baseline gauntlet (v{version:03d})...")
    gauntlet_result = await run_gauntlet(prompt)
    best_score = gauntlet_result.score
    print(f"Baseline score: {best_score}/10")

    if baseline_only:
        print(f"\n=== AutoShield Session Summary ===")
        print(f"Final score: {best_score}/10")
        print(f"Iterations: 0 (baseline only)")
        print(f"Total cost: ${cost_tracker.total_cost:.2f}")
        return

    iteration = 0
    accepted_count = 0
    stagnation = 0
    exit_reason = "Unknown"

    try:
        while True:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")

            history = load_history()

            try:
                proposal = await propose_improvement(prompt, gauntlet_result, history)
            except ValueError as e:
                print(f"Researcher error: {e}")
                append_log({
                    "iteration": iteration,
                    "version": version,
                    "score": 0,
                    "best_score": best_score,
                    "accepted": False,
                    "reasoning": f"Error: {e}",
                    "cost_so_far": cost_tracker.total_cost,
                })
                stagnation += 1
                if stagnation >= config.MAX_STAGNATION:
                    exit_reason = f"Stagnation ({stagnation} consecutive no-improvement)"
                    break
                continue

            new_result = await run_gauntlet(proposal.new_prompt)

            if new_result.score >= best_score:
                version += 1
                save_version(version, proposal.new_prompt, {
                    "score": new_result.score,
                    "reasoning": proposal.reasoning,
                })
                best_score = new_result.score
                prompt = proposal.new_prompt
                gauntlet_result = new_result
                stagnation = 0
                accepted_count += 1
                accepted = True
                print(f"Accepted: score {new_result.score}/10 (v{version:03d})")
            else:
                stagnation += 1
                accepted = False
                print(f"Discarded: score {new_result.score}/10 (best: {best_score}/10)")

            append_log({
                "iteration": iteration,
                "version": version,
                "score": new_result.score,
                "best_score": best_score,
                "accepted": accepted,
                "reasoning": proposal.reasoning,
                "cost_so_far": cost_tracker.total_cost,
            })

            cost_tracker.check_budget()

            if best_score == 10:
                exit_reason = "Perfect score (10/10)"
                break
            if stagnation >= config.MAX_STAGNATION:
                exit_reason = f"Stagnation ({stagnation} consecutive no-improvement)"
                break
            if max_iter is not None and iteration >= max_iter:
                exit_reason = f"Max iterations reached ({max_iter})"
                break

    except BudgetExceeded as e:
        exit_reason = f"Budget exceeded (${e.total_cost:.2f})"
    except KeyboardInterrupt:
        exit_reason = "Interrupted by user"

    discarded_count = iteration - accepted_count
    best_version_path = f"versions/v{version:03d}.txt" if version > 0 else config.SYSTEM_PROMPT_FILE

    print(f"\n=== AutoShield Session Summary ===")
    print(f"Final score: {best_score}/10")
    print(f"Iterations: {iteration} ({accepted_count} accepted, {discarded_count} discarded)")
    print(f"Total cost: ${cost_tracker.total_cost:.2f}")
    print(f"Best version: {best_version_path}")
    print(f"Exit reason: {exit_reason}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutoShield research session")
    parser.add_argument("--baseline-only", action="store_true", help="Run baseline gauntlet only")
    parser.add_argument("--max-iter", type=int, default=None, help="Maximum iterations")
    parser.add_argument("--resume", action="store_true", help="Resume from last saved version")
    args = parser.parse_args()

    asyncio.run(run_session(
        baseline_only=args.baseline_only,
        max_iter=args.max_iter,
        resume=args.resume,
    ))
```

- [ ] **Step 4: Run integration test**

Run: `cd /Users/lukasz/Workspace/autoresearch && uv run pytest tests/test_main.py -v`

Expected: PASS — `test_baseline_only` passes.

- [ ] **Step 5: Run the full test suite**

Run: `cd /Users/lukasz/Workspace/autoresearch && uv run pytest -v`

Expected: All tests pass (test_attacks: 5, test_models: 3, test_judge: 10, test_gauntlet: 4, test_researcher: 7, test_storage: 8, test_costs: 7, test_main: 1 = 45 total).

- [ ] **Step 6: Commit**

```bash
cd /Users/lukasz/Workspace/autoresearch
git add main.py tests/test_main.py
git commit -m "feat: add main loop orchestrator with CLI"
```

---
