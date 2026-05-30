import asyncio

from openai import AsyncOpenAI

from attacks import ATTACKS
from config import CANARY_STRING, JUDGE_MODEL, TARGET_BASE_URL
from judge import check_canary_leak, judge_defense
from models import AttackResult, CategoryResult, GauntletResult


async def _run_single_attack(
    client: AsyncOpenAI,
    system_prompt: str,
    model: str,
    category: str,
    attack: str,
) -> AttackResult:
    completion = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": attack},
        ],
    )
    response = completion.choices[0].message.content or ""
    leaked = check_canary_leak(response, CANARY_STRING)
    defended = await judge_defense(attack, response, model=JUDGE_MODEL)
    return AttackResult(
        category=category,
        attack=attack,
        response=response,
        defended=defended,
        leaked_canary=leaked,
    )


async def run_gauntlet(
    system_prompt: str, model: str = "o4-mini"
) -> GauntletResult:
    client = AsyncOpenAI(
        base_url=TARGET_BASE_URL,
        api_key="ollama",  # Ollama doesn't need a real key
    ) if TARGET_BASE_URL else AsyncOpenAI()

    tasks = []
    for category, attacks in ATTACKS.items():
        for attack in attacks:
            tasks.append(
                _run_single_attack(client, system_prompt, model, category, attack)
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
