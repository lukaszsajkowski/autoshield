import json

import tiktoken
from openai import AsyncOpenAI

from config import CANARY_STRING, MAX_PROMPT_TOKENS, PROGRAM_FILE, RESEARCH_MODEL
from models import GauntletResult, ResearchProposal


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
