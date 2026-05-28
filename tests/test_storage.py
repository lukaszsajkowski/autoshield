import json
import os

import pytest

import config
from storage import save_version, load_best, append_log, load_history


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
