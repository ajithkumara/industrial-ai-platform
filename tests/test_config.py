"""
Manual smoke-test script: run directly (`python tests/test_config.py`) to
verify environment configuration loads and validates against a real .env.

NOTE: this is intentionally guarded behind __main__ rather than exposing a
`test_*` function, because `validate_settings()` requires real environment
variables (EVENTHUB_CONNECTION_STRING, STORAGE_ACCOUNT_NAME, ...) that are
not present in CI. Running it at import time previously made this file
fail as soon as pytest collected it. See tests/test_settings_module.py for
an automated, CI-safe unit test of the settings module.
"""

from config.settings import validate_settings

if __name__ == "__main__":
    validate_settings()
    print("[OK] Settings validated successfully.")