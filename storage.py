import json
import os
import re

import config


def save_version(version: int, prompt: str, meta: dict) -> None:
    os.makedirs(config.VERSIONS_DIR, exist_ok=True)
    prefix = f"v{version:03d}"
    with open(os.path.join(config.VERSIONS_DIR, f"{prefix}.txt"), "w") as f:
        f.write(prompt)
    with open(os.path.join(config.VERSIONS_DIR, f"{prefix}.meta.json"), "w") as f:
        json.dump(meta, f, indent=2)


def load_best() -> tuple[int, str, int]:
    if os.path.isdir(config.VERSIONS_DIR):
        files = [f for f in os.listdir(config.VERSIONS_DIR) if re.match(r"v\d{3}\.txt$", f)]
        if files:
            files.sort()
            latest = files[-1]
            version = int(latest[1:4])
            with open(os.path.join(config.VERSIONS_DIR, latest)) as f:
                prompt = f.read()
            meta_path = os.path.join(config.VERSIONS_DIR, latest.replace(".txt", ".meta.json"))
            with open(meta_path) as f:
                meta = json.load(f)
            return version, prompt, meta["score"]

    with open(config.SYSTEM_PROMPT_FILE) as f:
        prompt = f.read()
    return 0, prompt, 0


def append_log(entry: dict) -> None:
    with open(config.ITERATIONS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def load_history(last_n: int = 10) -> list[dict]:
    if not os.path.exists(config.ITERATIONS_LOG):
        return []
    with open(config.ITERATIONS_LOG) as f:
        lines = f.readlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    return entries[-last_n:]
