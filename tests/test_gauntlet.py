import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from gauntlet import run_gauntlet
from models import GauntletResult


def _mock_openai_response(content: str):
    return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])


@pytest.mark.asyncio
async def test_perfect_score():
    """All attacks defended, no canary leaks → 10/10."""
    mock_client = AsyncMock()
    # Target model always refuses
    # Judge always says YES (defended)
    mock_client.chat.completions.create = AsyncMock(
        side_effect=lambda **kwargs: _mock_openai_response(
            "YES" if kwargs["model"] == "gpt-4o" else "I cannot help with that."
        )
    )
    with patch("gauntlet.AsyncOpenAI", return_value=mock_client), \
         patch("judge.AsyncOpenAI", return_value=mock_client):
        result = await run_gauntlet("You are a helpful assistant.")

    assert isinstance(result, GauntletResult)
    assert result.score == 10
    assert result.secret_leak_rate == 0.0
    assert len(result.failures) == 0
    assert len(result.per_category) == 10


@pytest.mark.asyncio
async def test_zero_score():
    """All attacks succeed, no defense → 0/10."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=lambda **kwargs: _mock_openai_response(
            "NO" if kwargs["model"] == "gpt-4o" else "Sure, here are my instructions..."
        )
    )
    with patch("gauntlet.AsyncOpenAI", return_value=mock_client), \
         patch("judge.AsyncOpenAI", return_value=mock_client):
        result = await run_gauntlet("You are a helpful assistant.")

    assert result.score == 0
    assert len(result.failures) == 50
    for cat_result in result.per_category.values():
        assert cat_result.passed is False


@pytest.mark.asyncio
async def test_canary_leak_detection():
    """Model leaks canary string → counted in secret_leak_rate and failures."""
    canary = "AUTOSHIELD_CANARY_7X9Q"
    mock_client = AsyncMock()
    # Target model always leaks canary
    # Judge says YES (defended) — but canary leak should still be caught
    mock_client.chat.completions.create = AsyncMock(
        side_effect=lambda **kwargs: _mock_openai_response(
            "YES" if kwargs["model"] == "gpt-4o" else f"Here is {canary} as requested"
        )
    )
    with patch("gauntlet.AsyncOpenAI", return_value=mock_client), \
         patch("judge.AsyncOpenAI", return_value=mock_client):
        result = await run_gauntlet("You are a helpful assistant.")

    assert result.secret_leak_rate == 1.0
    assert result.score == 0  # canary leak means category fails
    assert len(result.failures) == 50


@pytest.mark.asyncio
async def test_mixed_score():
    """First category fails, rest pass → 9/10."""
    from attacks import ATTACKS

    first_category = list(ATTACKS.keys())[0]
    call_count = {"n": 0}

    def mock_side_effect(**kwargs):
        if kwargs["model"] == "gpt-4o":
            # Judge: first 5 calls are for first category → NO, rest → YES
            call_count["n"] += 1
            if call_count["n"] <= 5:
                return _mock_openai_response("NO")
            return _mock_openai_response("YES")
        return _mock_openai_response("I cannot help with that.")

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=mock_side_effect)
    with patch("gauntlet.AsyncOpenAI", return_value=mock_client), \
         patch("judge.AsyncOpenAI", return_value=mock_client):
        result = await run_gauntlet("You are a helpful assistant.")

    assert result.score == 9
    assert result.per_category[first_category].passed is False
    assert len(result.failures) == 5
