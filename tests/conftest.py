import pytest


@pytest.fixture(autouse=True)
def no_basal(monkeypatch):
    """Keep tests off a locally running Basal server."""
    monkeypatch.setattr("gauntlet.BASAL_URL", None)
