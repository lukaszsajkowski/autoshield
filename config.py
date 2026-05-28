CANARY_STRING = "AUTOSHIELD_CANARY_7X9Q"

TARGET_MODEL = "o4-mini"
RESEARCH_MODEL = "gpt-4o"  # fallback; upgrade to gpt-5.4-pro when available
JUDGE_MODEL = "gpt-4o"

MAX_PROMPT_TOKENS = 2000
SESSION_COST_LIMIT = 20.0  # USD
MAX_STAGNATION = 3         # consecutive no-improvement iterations before early exit

VERSIONS_DIR = "versions"
ITERATIONS_LOG = "iterations.log"
SYSTEM_PROMPT_FILE = "system_prompt.txt"
PROGRAM_FILE = "program.md"
