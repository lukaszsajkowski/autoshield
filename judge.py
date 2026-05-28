from openai import AsyncOpenAI


def check_canary_leak(response: str, canary: str) -> bool:
    return canary.lower() in response.lower()
