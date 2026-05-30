CANARY_STRING = "AUTOSHIELD_CANARY_7X9Q"

TARGET_MODEL = "gpt-oss:20b"
TARGET_BASE_URL = "http://localhost:11434/v1"  # Ollama OpenAI-compatible API
RESEARCH_MODEL = "gpt-5.2"
JUDGE_MODEL = "gpt-5.2"

MAX_PROMPT_TOKENS = 2000
SESSION_COST_LIMIT = 20.0  # USD
MAX_STAGNATION = 3         # consecutive no-improvement iterations before early exit

VERSIONS_DIR = "versions"
ITERATIONS_LOG = "iterations.log"
SYSTEM_PROMPT_FILE = "system_prompt.txt"
PROGRAM_FILE = "program.md"
