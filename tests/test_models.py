from models import AttackResult, CategoryResult, GauntletResult


def test_attack_result_fields():
    r = AttackResult(
        category="pressure",
        attack="test attack",
        response="I cannot help with that.",
        defended=True,
        leaked_canary=False,
    )
    assert r.category == "pressure"
    assert r.attack == "test attack"
    assert r.response == "I cannot help with that."
    assert r.defended is True
    assert r.leaked_canary is False


def test_category_result_fields():
    attack = AttackResult(
        category="pressure",
        attack="test",
        response="no",
        defended=True,
        leaked_canary=False,
    )
    r = CategoryResult(passed=True, attacks=[attack])
    assert r.passed is True
    assert len(r.attacks) == 1


def test_gauntlet_result_fields():
    r = GauntletResult(
        score=7,
        secret_leak_rate=0.1,
        per_category={},
        total_cost=0.0,
        failures=[],
    )
    assert r.score == 7
    assert r.secret_leak_rate == 0.1
    assert r.per_category == {}
    assert r.total_cost == 0.0
    assert r.failures == []
