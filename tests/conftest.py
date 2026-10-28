import pytest


@pytest.fixture(autouse=True)
def no_basal(monkeypatch):
    """Keep tests off a locally running Basal server."""
    monkeypatch.setattr("gauntlet.BASAL_URL", None)


@pytest.fixture(autouse=True)
def target_api_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
