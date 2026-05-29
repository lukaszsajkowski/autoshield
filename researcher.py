import json

import tiktoken
from openai import AsyncOpenAI

from config import CANARY_STRING, MAX_PROMPT_TOKENS, PROGRAM_FILE, RESEARCH_MODEL
from models import AttackResult, GauntletResult, ResearchProposal


def validate_proposal(
    new_prompt: str, current_prompt: str, canary: str
) -> None:
    if new_prompt == current_prompt:
        raise ValueError("Proposed prompt is identical to current prompt")
    if canary not in new_prompt:
        raise ValueError("Proposed prompt is missing the canary string")
    enc = tiktoken.encoding_for_model("gpt-4o")
    token_count = len(enc.encode(new_prompt))
    if token_count > MAX_PROMPT_TOKENS:
        raise ValueError(
            f"Proposed prompt exceeds token limit ({token_count} > {MAX_PROMPT_TOKENS})"
        )


def _format_gauntlet_results(result: GauntletResult) -> str:
    lines = [f"Score: {result.score}/10", f"Canary leak rate: {result.secret_leak_rate:.0%}", ""]
    for cat_name, cat_result in result.per_category.items():
        status = "PASS" if cat_result.passed else "FAIL"
        lines.append(f"  {cat_name}: {status}")
    if result.failures:
        lines.append("\nFailure details:")
        for f in result.failures:
            lines.append(f"\n  [{f.category}] Attack: {f.attack}")
            lines.append(f"  Response: {f.response[:200]}")
    return "\n".join(lines)


def _format_history(history: list[dict]) -> str:
    if not history:
        return "No previous iterations."
    lines = []
    for entry in history:
        lines.append(
            f"- Iteration {entry.get('iteration', '?')}: "
            f"score {entry.get('score', '?')}, "
            f"{'accepted' if entry.get('accepted') else 'discarded'}. "
            f"Reasoning: {entry.get('reasoning', 'N/A')}"
        )
    return "\n".join(lines)


async def propose_improvement(
    current_prompt: str,
    gauntlet_result: GauntletResult,
    history: list[dict],
) -> ResearchProposal:
    with open(PROGRAM_FILE) as f:
        program = f.read()

    user_message = (
        f"CURRENT SYSTEM PROMPT:\n{current_prompt}\n\n"
        f"GAUNTLET RESULTS:\n{_format_gauntlet_results(gauntlet_result)}\n\n"
        f"ITERATION HISTORY:\n{_format_history(history)}"
    )

    client = AsyncOpenAI()
    completion = await client.chat.completions.create(
        model=RESEARCH_MODEL,
        messages=[
            {"role": "system", "content": program},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
    )

    raw = completion.choices[0].message.content or ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError("Research model returned invalid JSON")

    if "new_prompt" not in data:
        raise ValueError("Research model response missing 'new_prompt' key")
    if "reasoning" not in data:
        raise ValueError("Research model response missing 'reasoning' key")

    validate_proposal(data["new_prompt"], current_prompt, CANARY_STRING)

    return ResearchProposal(
        new_prompt=data["new_prompt"],
        reasoning=data["reasoning"],
    )
