from attacks import ATTACKS
from config import CANARY_STRING

EXPECTED_CATEGORIES = [
    "pressure",
    "persona_play",
    "code_injection",
    "obfuscation",
    "multi_step_bypass",
    "token_smuggling",
    "translator_tunneling",
    "payload_splitting",
    "social_engineering",
    "output_forcing",
]


def test_attacks_has_all_categories():
    assert sorted(ATTACKS.keys()) == sorted(EXPECTED_CATEGORIES)


def test_each_category_has_five_attacks():
    for category, prompts in ATTACKS.items():
        assert len(prompts) == 5, f"{category} has {len(prompts)} attacks, expected 5"


def test_all_attacks_are_nonempty_strings():
    for category, prompts in ATTACKS.items():
        for i, prompt in enumerate(prompts):
            assert isinstance(prompt, str), f"{category}[{i}] is not a string"
            assert len(prompt.strip()) > 0, f"{category}[{i}] is empty"


def test_no_duplicate_attacks():
    all_attacks = [p for prompts in ATTACKS.values() for p in prompts]
    assert len(all_attacks) == len(set(all_attacks)), "Duplicate attacks found"


def test_canary_appears_in_at_least_one_attack():
    all_text = " ".join(p for prompts in ATTACKS.values() for p in prompts)
    assert CANARY_STRING in all_text, (
        f"No attack references the canary string '{CANARY_STRING}'. "
        "At least one attack should try to extract it by name."
    )
