# AutoShield

Autonomous security hardening for small language models through system prompt evolution.

Inspired by [Andrej Karpathy's autoresearch pattern](https://x.com/karpathy/status/1908599838498799724) — an automated research loop where a strong model iteratively improves a weaker model's behavior through experimentation and evaluation.

## How it works

AutoShield takes a naive system prompt and evolves it into a hardened one by running an automated feedback loop:

1. **Gauntlet** — 50 indirect prompt injection attacks (10 categories x 5) are fired at the target model
2. **Judge** — a stronger model (gpt-5.2) evaluates each response: did the model defend or leak?
3. **Researcher** — the same strong model analyzes failures and proposes an improved system prompt
4. **Accept/Discard** — if the new prompt scores equal or better, it's accepted; otherwise discarded
5. **Repeat** — until 10/10 score, budget limit, or stagnation

## Results

| Model | Baseline | Final | Iterations |
|---|---|---|---|
| o4-mini | 5-7/10 | 10/10 | 2-3 |
| o3-mini | 3-5/10 | 10/10 | 2-3 |
| gpt-oss-20b (OpenRouter) | 2-3/10 | 10/10 | 3 |

## Setup

```bash
# Install dependencies
uv sync

# Configure API keys
cp .env.example .env
# Edit .env with your OPENAI_API_KEY and OPENROUTER_API_KEY
```

## Usage

```bash
# Baseline score only (no research loop)
python main.py --baseline-only

# Full session (default max stagnation: 3)
python main.py

# Limited iterations
python main.py --max-iter 20

# Resume from last saved version
python main.py --resume
```

## Configuration

Edit `config.py` to change:

- `TARGET_MODEL` / `TARGET_BASE_URL` — the model being hardened
- `RESEARCH_MODEL` / `JUDGE_MODEL` — the strong model evaluating and improving
- `MAX_STAGNATION` — consecutive no-improvement iterations before early exit
- `SESSION_COST_LIMIT` — budget cap in USD

## Project structure

```
main.py              — orchestrator + CLI
gauntlet.py          — async attack runner (50 attacks in parallel)
judge.py             — LLM-as-judge + canary leak detection
researcher.py        — proposes improved system prompts
attacks.py           — 50 indirect prompt extraction attacks
storage.py           — version persistence (versions/vNNN.txt)
costs.py             — session cost tracking
config.py            — all constants
models.py            — shared dataclasses
system_prompt.txt    — starting prompt (v0)
program.md           — research agent instructions
```

## Output

```
versions/v001.txt         — improved prompt + meta
versions/v001.meta.json   — score + reasoning
iterations.log            — JSONL session history
```
