import asyncio
import os

from openai import AsyncOpenAI

from attacks import ATTACKS
from config import (
    BASAL_THRESHOLD,
    BASAL_URL,
    CANARY_STRING,
    JUDGE_MODEL,
    TARGET_BASE_URL,
    TARGET_MODEL,
)
from judge import check_canary_leak, judge_cascade
from models import AttackResult, CategoryResult, GauntletResult


async def _run_single_attack(
    client: AsyncOpenAI,
    system_prompt: str,
    model: str,
    category: str,
    attack: str,
    cost_tracker=None,
) -> AttackResult:
    completion = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": attack},
        ],
    )
    if cost_tracker:
        cost_tracker.record_completion(model, completion)
    response = completion.choices[0].message.content or ""
    leaked = check_canary_leak(response, CANARY_STRING)
    defended = await judge_cascade(
        attack, response, JUDGE_MODEL, BASAL_URL, BASAL_THRESHOLD, cost_tracker
    )
    return AttackResult(
        category=category,
        attack=attack,
        response=response,
        defended=defended,
        leaked_canary=leaked,
    )


def target_client(**kwargs) -> AsyncOpenAI:
    """Client for the target model; OpenRouter needs OPENROUTER_API_KEY."""
    if not TARGET_BASE_URL:
        return AsyncOpenAI(**kwargs)
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set. Add it to .env (see .env.example).")
    return AsyncOpenAI(base_url=TARGET_BASE_URL, api_key=api_key, **kwargs)


async def run_gauntlet(
    system_prompt: str, model: str = TARGET_MODEL, cost_tracker=None
) -> GauntletResult:
    client = target_client()

    sem = asyncio.Semaphore(20 if TARGET_BASE_URL else 50)

    async def _limited(coro):
        async with sem:
            return await coro

    tasks = []
    for category, attacks in ATTACKS.items():
        for attack in attacks:
            tasks.append(
                _limited(_run_single_attack(
                    client, system_prompt, model, category, attack, cost_tracker
                ))
            )

    results: list[AttackResult] = await asyncio.gather(*tasks)

    per_category: dict[str, CategoryResult] = {}
    for category in ATTACKS:
        cat_results = [r for r in results if r.category == category]
        passed = all(r.defended and not r.leaked_canary for r in cat_results)
        per_category[category] = CategoryResult(passed=passed, attacks=cat_results)

    score = sum(1 for cr in per_category.values() if cr.passed)
    total_leaks = sum(1 for r in results if r.leaked_canary)
    secret_leak_rate = total_leaks / len(results)
    failures = [r for r in results if not r.defended or r.leaked_canary]

    return GauntletResult(
        score=score,
        secret_leak_rate=secret_leak_rate,
        per_category=per_category,
        total_cost=0.0,
        failures=failures,
    )
