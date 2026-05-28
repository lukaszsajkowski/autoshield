from dataclasses import dataclass


@dataclass
class AttackResult:
    category: str
    attack: str
    response: str
    defended: bool
    leaked_canary: bool


@dataclass
class CategoryResult:
    passed: bool
    attacks: list[AttackResult]


@dataclass
class GauntletResult:
    score: int
    secret_leak_rate: float
    per_category: dict[str, CategoryResult]
    total_cost: float
    failures: list[AttackResult]
