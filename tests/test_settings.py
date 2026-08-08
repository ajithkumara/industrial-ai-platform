"""
Manual smoke-test script: run directly (`python tests/test_settings.py`) to
print the effective loaded settings for the current .env.

NOTE: guarded behind __main__ (validate_settings() requires real env vars
that are not present in CI) so pytest collection doesn't fail on import.
"""

from config.settings import settings, validate_settings

if __name__ == "__main__":
    validate_settings()

    print("\n========== SETTINGS ==========\n")

    print("Event Hub")
    print("--------------------------------")
    print(f"Hub Name         : {settings.eventhub.hub_name}")
    print(f"Consumer Group   : {settings.eventhub.consumer_group}")
    print(f"Connection String: {'Loaded' if settings.eventhub.connection_string else 'Missing'}")

    print()

    print("Storage")
    print("--------------------------------")
    print(f"Storage Account  : {settings.storage.account_name}")
    print(f"Filesystem       : {settings.storage.filesystem_name}")
    print(f"Raw Folder       : {settings.storage.raw_folder}")
    print(f"Connection String: {'Loaded' if settings.storage.connection_string else 'Missing'}")

    print()

    print("Batch Size")
    print("--------------------------------")
    print(settings.consumer_batch_size)

    print("\n[OK] Configuration test PASSED")