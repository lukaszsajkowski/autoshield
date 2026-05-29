import argparse
import asyncio

from dotenv import load_dotenv

import config
from costs import BudgetExceeded, CostTracker
from gauntlet import run_gauntlet
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
                # Don't count researcher errors as stagnation — it's a
                # technical failure, not a failed improvement attempt.
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
