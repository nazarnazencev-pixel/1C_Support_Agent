import pytest

import app.config.settings as settings


def test_validate_config_raises_when_credentials_missing(monkeypatch):
    monkeypatch.setattr(settings, "GIGACHAT_CREDENTIALS", "")

    with pytest.raises(RuntimeError, match="GIGACHAT_CREDENTIALS"):
        settings.validate_config()


def test_validate_config_passes_when_credentials_set(monkeypatch):
    monkeypatch.setattr(
        settings, "GIGACHAT_CREDENTIALS", "dummy-credentials"
    )

    settings.validate_config()
