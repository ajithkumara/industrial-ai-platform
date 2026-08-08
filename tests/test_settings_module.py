"""
Automated, CI-safe unit tests for config/settings.py.

Proves the Phase 5 invariant: importing config.settings must NOT crash or
require any production environment variables to be present. Validation of
required settings is opt-in and explicit via validate_settings(), called
only from real entry points (consumer.eventhub_consumer.main,
edge.base_producer.EventHubProducer.__init__) — never automatically at
import time.

Referenced from tests/test_config.py's module docstring as the automated
counterpart to that manual smoke-test script.
"""

import importlib
import os

import pytest


_RELEVANT_VARS = (
    "EVENTHUB_CONNECTION_STRING",
    "EVENTHUB_NAME",
    "CONSUMER_GROUP",
    "EVENTHUB_CONSUMER_CONNECTION_STRING",
    "STORAGE_ACCOUNT_NAME",
    "STORAGE_CONNECTION_STRING",
    "FILESYSTEM_NAME",
    "RAW_FOLDER",
    "RAW_BATCH_SIZE",
    "CONSUMER_BATCH_SIZE",
)


def _reload_settings_without_dotenv_or_env(monkeypatch):
    """
    Reload config.settings with no relevant environment variables set AND
    with dotenv disabled, so a developer-local .env file (present on disk
    but git-ignored — see config/settings.py's load_dotenv(BASE_DIR/".env"))
    cannot leak real values into this test and mask the behavior under test.
    """
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: None)

    for var in _RELEVANT_VARS:
        monkeypatch.delenv(var, raising=False)

    import config.settings as settings_module

    importlib.reload(settings_module)
    return settings_module


def test_importing_settings_module_does_not_require_env_vars(monkeypatch):
    """
    Importing config.settings with no relevant environment variables set
    (and no .env file loaded) must succeed (not raise), even though the
    resulting settings object will contain empty/default values.
    """
    settings_module = _reload_settings_without_dotenv_or_env(monkeypatch)

    assert settings_module.settings.eventhub.connection_string == ""
    assert settings_module.settings.storage.account_name == ""


def test_validate_settings_raises_only_when_called_explicitly(monkeypatch):
    """
    validate_settings() must still correctly detect missing required
    configuration when called explicitly (it is not a no-op) — it simply
    must not run automatically on import.
    """
    settings_module = _reload_settings_without_dotenv_or_env(monkeypatch)

    with pytest.raises(ValueError, match="Missing configuration values"):
        settings_module.validate_settings()


def test_validate_settings_passes_when_required_vars_present(monkeypatch):
    monkeypatch.setenv("EVENTHUB_CONNECTION_STRING", "Endpoint=sb://fake/")
    monkeypatch.setenv("EVENTHUB_NAME", "fake-hub")
    monkeypatch.setenv("STORAGE_ACCOUNT_NAME", "fakeaccount")
    monkeypatch.setenv("STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;fake")
    monkeypatch.setenv("FILESYSTEM_NAME", "raw")

    import config.settings as settings_module

    importlib.reload(settings_module)

    settings_module.validate_settings()  # must not raise
