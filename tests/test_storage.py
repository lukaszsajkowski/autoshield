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
