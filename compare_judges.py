"""Compare the current LLM judge against a local Basal decision model.

Step 1 collects target responses for the gauntlet under several system prompts
(cached in judge_compare/responses.json). Step 2 judges every response with
both judges (cached in judge_compare/verdicts.json). Step 3 prints agreement.

With --leak-kind it compares cascades built on the yes/no question, on the
leak-kind question, and on both (the production rule), on
judge_compare/dataset.json when present (cached in judge_compare/leak_kind.json).

Requires a running Basal server, e.g.:
  basal-serve --model Remek/basal-2.0-max-MLX-8bit --mode mlx --port 8011
"""
import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI

from attacks import ATTACKS
from config import BASAL_THRESHOLD, BASAL_URL, JUDGE_MODEL, TARGET_BASE_URL, TARGET_MODEL
from judge import LEAK_KIND_QUESTION, basal_defense, basal_leak_kind, basal_verdict, is_basal_language, judge_defense

OUT_DIR = Path("judge_compare")
RESPONSES_FILE = OUT_DIR / "responses.json"
VERDICTS_FILE = OUT_DIR / "verdicts.json"
DATASET_FILE = OUT_DIR / "dataset.json"
LEAK_KIND_FILE = OUT_DIR / "leak_kind.json"

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
            p_nothing = await basal_leak_kind(item["attack"], item["response"], basal_url)
        return {**item, "llm_defended": llm, "basal_p_defended": p_yes, "basal_p_nothing": p_nothing}

    return await asyncio.gather(*(one(i) for i in items))


async def leak_kind_all(items: list[dict], basal_url: str) -> list[dict]:
    sem = asyncio.Semaphore(1)  # the MLX server answers one request at a time
    async with httpx.AsyncClient(timeout=300) as http:

        async def one(item: dict) -> dict:
            async with sem:
                r = await http.post(basal_url, json={
                    "state": f"ATTACK PROMPT:\n{item['attack']}\n\nASSISTANT RESPONSE:\n{item['response']}",
                    "questions": {"leak_kind": LEAK_KIND_QUESTION},
                })
            r.raise_for_status()
            answer = r.json()["answers"]["leak_kind"]
            return {**item, "leak_kind": answer["choice"], "leak_kind_probs": answer["probabilities"],
                    "basal_p_nothing": answer["probabilities"]["nothing"]}

        return await asyncio.gather(*(one(i) for i in items))


def compare_strategies(verdicts: list[dict], threshold: float) -> None:
    """Simulate the production cascade (language rule + threshold) for both questions."""
    n = len(verdicts)
    supported = [is_basal_language(v["response"]) for v in verdicts]
    strategies = [("yes/no question", "basal_p_defended"), ("leak-kind question", "basal_p_nothing")]

    print(f"\nItems: {n}   reference judge: {JUDGE_MODEL}   "
          f"non-PL/EN responses sent to the LLM judge: {n - sum(supported)}")
    print(f"\n{'':<20} {'Basal alone agrees':>19}   {'leaks missed':>12}   {'false alarms':>12}")
    for name, key in strategies:
        agree = sum((v[key] >= 0.5) == v["llm_defended"] for v in verdicts)
        missed = sum(v[key] >= 0.5 and not v["llm_defended"] for v in verdicts)
        false_alarm = sum(v[key] < 0.5 and v["llm_defended"] for v in verdicts)
        print(f"{name:<20} {f'{agree}/{n} ({agree / n:.0%})':>19}   {missed:>12}   {false_alarm:>12}")

    print("\nCascade: Basal decides when confident (>= t) and the language is PL/EN")
    print(f"{'':<8}" + "".join(f"{name:>34}" for name, _ in strategies) + f"{'both (production)':>34}")
    for t in (0.7, 0.8, 0.9, 0.95):
        cells = []
        for _, key in strategies:
            decided = [v for v, ok in zip(verdicts, supported) if ok and max(v[key], 1 - v[key]) >= t]
            wrong = sum((v[key] >= 0.5) != v["llm_defended"] for v in decided)
            cells.append(f"decides {len(decided):>3}/{n} ({len(decided) / n:>3.0%}), wrong {wrong:>2}")
        combined = [(basal_verdict(v["basal_p_defended"], v["basal_p_nothing"], t), v)
                    for v, ok in zip(verdicts, supported) if ok]
        decided = [(d, v) for d, v in combined if d is not None]
        wrong = sum(d != v["llm_defended"] for d, v in decided)
        cells.append(f"decides {len(decided):>3}/{n} ({len(decided) / n:>3.0%}), wrong {wrong:>2}")
        print(f"t={t:<6}" + "".join(f"{c:>34}" for c in cells))

    print("\nLeak kind chosen by Basal vs the LLM verdict:")
    kinds = list(LEAK_KIND_QUESTION["criteria"])
    print(f"  {'':<10} {'LLM: defended':>14} {'LLM: leak':>10}")
    for k in kinds:
        d = sum(v["leak_kind"] == k and v["llm_defended"] for v in verdicts)
        l = sum(v["leak_kind"] == k and not v["llm_defended"] for v in verdicts)
        print(f"  {k:<10} {d:>14} {l:>10}")

    print(f"\nLeak-kind cascade at t={threshold}: verdicts that differ from the LLM judge")
    for v, ok in zip(verdicts, supported):
        p = v["basal_p_nothing"]
        if ok and max(p, 1 - p) >= threshold and (p >= 0.5) != v["llm_defended"]:
            print(f"- [{v['prompt']} / {v['category']}] llm={'DEF' if v['llm_defended'] else 'LEAK'} "
                  f"basal={v['leak_kind']} P(nothing)={p:.3f}")
            print(f"  attack:   {v['attack'][:120]!r}")
            print(f"  response: {v['response'][:300]!r}")

    print(f"\nYes/no -> leak-kind at t={threshold}: which handed-off cases Basal now decides")
    for v, ok in zip(verdicts, supported):
        a, b = v["basal_p_defended"], v["basal_p_nothing"]
        if ok and max(a, 1 - a) < threshold <= max(b, 1 - b):
            print(f"  [{v['prompt']} / {v['category']}] P(def)={a:.2f} -> {v['leak_kind']} "
                  f"P(nothing)={b:.3f}, llm={'DEF' if v['llm_defended'] else 'LEAK'}  {v['response'][:60]!r}")


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
    parser.add_argument("--leak-kind", action="store_true", help="compare yes/no vs leak-kind questions")
    args = parser.parse_args()

    if args.leak_kind:
        if LEAK_KIND_FILE.exists() and not args.refresh:
            verdicts = json.loads(LEAK_KIND_FILE.read_text())
        else:
            source = DATASET_FILE if DATASET_FILE.exists() else VERDICTS_FILE
            verdicts = await leak_kind_all(json.loads(source.read_text()), args.basal_url)
            LEAK_KIND_FILE.write_text(json.dumps(verdicts, indent=2, ensure_ascii=False))
        compare_strategies(verdicts, BASAL_THRESHOLD)
        return

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
