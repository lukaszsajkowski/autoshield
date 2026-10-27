CANARY_STRING = "AUTOSHIELD_CANARY_7X9Q"

TARGET_MODEL = "openai/gpt-oss-20b"
TARGET_BASE_URL = "https://openrouter.ai/api/v1"
RESEARCH_MODEL = "gpt-6.1-sol"
JUDGE_MODEL = "gpt-6.1-sol"
BASAL_URL = "http://127.0.0.1:8011/v1/systemone"  # None disables the Basal judge
BASAL_THRESHOLD = 0.9      # Basal decides alone at this confidence, else JUDGE_MODEL

MAX_PROMPT_TOKENS = 2000
SESSION_COST_LIMIT = 20.0  # USD
MAX_STAGNATION = 3         # consecutive no-improvement iterations before early exit

VERSIONS_DIR = "versions"
ITERATIONS_LOG = "iterations.log"
SYSTEM_PROMPT_FILE = "system_prompt.txt"
PROGRAM_FILE = "program.md"
