"""Compare the current LLM judge against a local Basal decision model.

Step 1 collects target responses for the gauntlet under several system prompts
(cached in judge_compare/responses.json). Step 2 judges every response with
both judges (cached in judge_compare/verdicts.json). Step 3 prints agreement.

Requires a running Basal server, e.g.:
  basal-serve --model Remek/basal-2.0-max-MLX-8bit --mode mlx --port 8011
"""
import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from attacks import ATTACKS
from config import BASAL_URL, JUDGE_MODEL, TARGET_BASE_URL, TARGET_MODEL
from judge import basal_defense, judge_defense

OUT_DIR = Path("judge_compare")
RESPONSES_FILE = OUT_DIR / "responses.json"
VERDICTS_FILE = OUT_DIR / "verdicts.json"

async def collect_responses(prompt_files: list[Path]) -> list[dict]:
    client = AsyncOpenAI(
        base_url=TARGET_BASE_URL,
        api_key=os.environ.get("OPENROUTER_API_KEY", "ollama"),
        max_retries=5,
        timeout=120,
    )
    sem = asyncio.Semaphore(10)

    async def one(prompt_name: str, system_prompt: str, category: str, attack: str) -> dict:
        async with sem:
            completion = await client.chat.completions.create(
                model=TARGET_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": attack},
                ],
            )
        return {
            "prompt": prompt_name,
            "category": category,
            "attack": attack,
            "response": completion.choices[0].message.content or "",
        }

    tasks = []
    for path in prompt_files:
        system_prompt = path.read_text()
        for category, attacks in ATTACKS.items():
            for attack in attacks:
                tasks.append(one(path.name, system_prompt, category, attack))
    return await asyncio.gather(*tasks)


async def judge_all(items: list[dict], basal_url: str, basal_concurrency: int) -> list[dict]:
    llm_sem = asyncio.Semaphore(20)
    basal_sem = asyncio.Semaphore(basal_concurrency)

    async def one(item: dict) -> dict:
        async with llm_sem:
            llm = await judge_defense(item["attack"], item["response"], model=JUDGE_MODEL)
        async with basal_sem:
            p_yes = await basal_defense(item["attack"], item["response"], basal_url)
        return {**item, "llm_defended": llm, "basal_p_defended": p_yes}

    return await asyncio.gather(*(one(i) for i in items))


def report(verdicts: list[dict]) -> None:
    n = len(verdicts)
    rows = [(v["llm_defended"], v["basal_p_defended"] >= 0.5, v) for v in verdicts]
    agree = sum(1 for llm, basal, _ in rows if llm == basal)
    tt = sum(1 for llm, basal, _ in rows if llm and basal)
    ff = sum(1 for llm, basal, _ in rows if not llm and not basal)
    tf = sum(1 for llm, basal, _ in rows if llm and not basal)
    ft = sum(1 for llm, basal, _ in rows if not llm and basal)

    print(f"\nItems: {n}   reference judge: {JUDGE_MODEL}")
    print(f"Agreement: {agree}/{n} = {agree / n:.1%}")
    print("\n                 basal DEFENDED   basal LEAKED")
    print(f"llm DEFENDED     {tt:>14}   {tf:>12}")
    print(f"llm LEAKED       {ft:>14}   {ff:>12}   <- top-right of this row = leaks Basal misses")

    print("\nBy prompt:")
    for prompt in sorted({v["prompt"] for v in verdicts}):
        sub = [r for r in rows if r[2]["prompt"] == prompt]
        a = sum(1 for llm, basal, _ in sub if llm == basal)
        leaks = sum(1 for llm, _, _ in sub if not llm)
        print(f"  {prompt:<20} agree {a}/{len(sub)}   llm-leaks {leaks}")

    print("\nCascade: trust Basal when confidence >= t, else ask the LLM judge")
    for t in (0.6, 0.7, 0.8, 0.9, 0.95):
        confident = [r for r in rows if max(r[2]["basal_p_defended"], 1 - r[2]["basal_p_defended"]) >= t]
        wrong = sum(1 for llm, basal, _ in confident if llm != basal)
        print(f"  t={t:.2f}: Basal decides {len(confident)}/{n} ({len(confident) / n:.0%}), "
              f"disagrees on {wrong}")

    print("\nDisagreements:")
    for llm, basal, v in rows:
        if llm != basal:
            print(f"- [{v['prompt']} / {v['category']}] llm={'DEF' if llm else 'LEAK'} "
                  f"basal P(def)={v['basal_p_defended']:.2f}")
            print(f"  attack:   {v['attack'][:120]!r}")
            print(f"  response: {v['response'][:300]!r}")


async def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("prompts", nargs="*", type=Path, default=[Path("system_prompt.txt")])
    parser.add_argument("--basal-url", default=BASAL_URL)
    parser.add_argument("--basal-concurrency", type=int, default=2)
    parser.add_argument("--refresh", action="store_true", help="ignore cached files")
    args = parser.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    if RESPONSES_FILE.exists() and not args.refresh:
        items = json.loads(RESPONSES_FILE.read_text())
    else:
        items = await collect_responses(args.prompts)
        RESPONSES_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False))
    print(f"{len(items)} responses")

    if VERDICTS_FILE.exists() and not args.refresh:
        verdicts = json.loads(VERDICTS_FILE.read_text())
    else:
        verdicts = await judge_all(items, args.basal_url, args.basal_concurrency)
        VERDICTS_FILE.write_text(json.dumps(verdicts, indent=2, ensure_ascii=False))

    report(verdicts)


if __name__ == "__main__":
    asyncio.run(main())
