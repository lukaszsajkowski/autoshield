# Step 5: Versioning & Persistence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build file-based persistence for prompt versions (`versions/vNNN.txt` + `.meta.json`) and iteration history (`iterations.log` JSONL).

**Architecture:** Single file `storage.py` with four pure functions. Version files in `versions/` directory, iteration log as JSONL. All paths read from `config.py`. Tests use pytest `tmp_path` for real filesystem I/O.

**Tech Stack:** Python 3.12, json (stdlib), pathlib (stdlib), pytest

---

## File Structure

| File | Responsibility |
|---|---|
| `storage.py` | `save_version()`, `load_best()`, `append_log()`, `load_history()` |
| `tests/test_storage.py` | Round-trip tests with `tmp_path` and monkeypatch |

---

### Task 1: Create `storage.py` with version functions and tests

**Files:**
- Create: `storage.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: Write tests for `save_version` and `load_best`**

Create `tests/test_storage.py`:

```python
import json
import os

import pytest

import config
from storage import save_version, load_best


@pytest.fixture
def storage_dir(tmp_path, monkeypatch):
    """Set up a temporary storage directory for versions and system_prompt."""
    versions_dir = str(tmp_path / "versions")
    monkeypatch.setattr(config, "VERSIONS_DIR", versions_dir)

    # Create a system_prompt.txt in tmp_path for fallback testing
    system_prompt_path = str(tmp_path / "system_prompt.txt")
    with open(system_prompt_path, "w") as f:
        f.write("You are a helpful assistant.\n\nConfidential: AUTOSHIELD_CANARY_7X9Q")
    monkeypatch.setattr(config, "SYSTEM_PROMPT_FILE", system_prompt_path)

    return tmp_path


def test_save_and_load_single_version(storage_dir):
    meta = {"score": 5, "reasoning": "Added refusal patterns"}
    save_version(1, "Prompt v1 text", meta)

    version, prompt, score = load_best()
    assert version == 1
    assert prompt == "Prompt v1 text"
    assert score == 5


def test_save_multiple_versions_loads_highest(storage_dir):
    save_version(1, "Prompt v1", {"score": 3, "reasoning": "first"})
    save_version(2, "Prompt v2", {"score": 7, "reasoning": "second"})

    version, prompt, score = load_best()
    assert version == 2
    assert prompt == "Prompt v2"
    assert score == 7


def test_load_best_fallback_to_system_prompt(storage_dir):
    version, prompt, score = load_best()
    assert version == 0
    assert "AUTOSHIELD_CANARY_7X9Q" in prompt
    assert score == 0


def test_version_files_on_disk(storage_dir):
    save_version(3, "Test prompt", {"score": 8, "reasoning": "test"})

    versions_dir = storage_dir / "versions"
    assert (versions_dir / "v003.txt").exists()
    assert (versions_dir / "v003.meta.json").exists()

    with open(versions_dir / "v003.txt") as f:
        assert f.read() == "Test prompt"

    with open(versions_dir / "v003.meta.json") as f:
        meta = json.load(f)
        assert meta["score"] == 8
        assert meta["reasoning"] == "test"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/lukasz/Workspace/autoresearch && uv run pytest tests/test_storage.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'storage'`

- [ ] **Step 3: Create `storage.py` with version functions**

```python
import json
import os
import re

from config import ITERATIONS_LOG, SYSTEM_PROMPT_FILE, VERSIONS_DIR


def save_version(version: int, prompt: str, meta: dict) -> None:
    os.makedirs(VERSIONS_DIR, exist_ok=True)
    prefix = f"v{version:03d}"
    with open(os.path.join(VERSIONS_DIR, f"{prefix}.txt"), "w") as f:
        f.write(prompt)
    with open(os.path.join(VERSIONS_DIR, f"{prefix}.meta.json"), "w") as f:
        json.dump(meta, f, indent=2)


def load_best() -> tuple[int, str, int]:
    if os.path.isdir(VERSIONS_DIR):
        files = [f for f in os.listdir(VERSIONS_DIR) if re.match(r"v\d{3}\.txt$", f)]
        if files:
            files.sort()
            latest = files[-1]
            version = int(latest[1:4])
            with open(os.path.join(VERSIONS_DIR, latest)) as f:
                prompt = f.read()
            meta_path = os.path.join(VERSIONS_DIR, latest.replace(".txt", ".meta.json"))
            with open(meta_path) as f:
                meta = json.load(f)
            return version, prompt, meta["score"]

    with open(SYSTEM_PROMPT_FILE) as f:
        prompt = f.read()
    return 0, prompt, 0


def append_log(entry: dict) -> None:
    with open(ITERATIONS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def load_history(last_n: int = 10) -> list[dict]:
    if not os.path.exists(ITERATIONS_LOG):
        return []
    with open(ITERATIONS_LOG) as f:
        lines = f.readlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    return entries[-last_n:]
```

- [ ] **Step 4: Run version tests**

Run: `cd /Users/lukasz/Workspace/autoresearch && uv run pytest tests/test_storage.py -v`

Expected: All 4 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/lukasz/Workspace/autoresearch
git add storage.py tests/test_storage.py
git commit -m "feat: add version save/load to storage"
```

---

### Task 2: Add log functions and tests

**Files:**
- Modify: `tests/test_storage.py`

- [ ] **Step 1: Append log tests to `tests/test_storage.py`**

Append to the end of the file:

```python
from storage import append_log, load_history


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    """Set up a temporary iterations.log path."""
    log_path = str(tmp_path / "iterations.log")
    monkeypatch.setattr(config, "ITERATIONS_LOG", log_path)
    return tmp_path


def test_append_and_load_history(log_dir):
    append_log({"iteration": 1, "score": 3, "accepted": True})
    append_log({"iteration": 2, "score": 5, "accepted": True})
    append_log({"iteration": 3, "score": 4, "accepted": False})

    history = load_history(last_n=2)
    assert len(history) == 2
    assert history[0]["iteration"] == 2
    assert history[1]["iteration"] == 3


def test_load_history_missing_file(log_dir):
    history = load_history()
    assert history == []


def test_load_history_default_last_n(log_dir):
    for i in range(15):
        append_log({"iteration": i, "score": i})

    history = load_history()
    assert len(history) == 10
    assert history[0]["iteration"] == 5
    assert history[-1]["iteration"] == 14


def test_log_file_is_jsonl(log_dir):
    append_log({"iteration": 1, "score": 3, "accepted": True})
    append_log({"iteration": 2, "score": 5, "accepted": True})

    log_path = log_dir / "iterations.log"
    with open(log_path) as f:
        lines = f.readlines()
    assert len(lines) == 2
    for line in lines:
        data = json.loads(line)
        assert "iteration" in data
```

- [ ] **Step 2: Run all storage tests**

Run: `cd /Users/lukasz/Workspace/autoresearch && uv run pytest tests/test_storage.py -v`

Expected: All 8 tests pass (4 version + 4 log).

- [ ] **Step 3: Run the full test suite**

Run: `cd /Users/lukasz/Workspace/autoresearch && uv run pytest -v`

Expected: All tests pass (test_attacks: 5, test_models: 3, test_judge: 10, test_gauntlet: 4, test_researcher: 7, test_storage: 8 = 37 total).

- [ ] **Step 4: Commit**

```bash
cd /Users/lukasz/Workspace/autoresearch
git add tests/test_storage.py
git commit -m "feat: add iteration log append/load to storage"
```

---
