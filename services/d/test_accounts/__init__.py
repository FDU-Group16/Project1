"""Explicit staging/test account adapter, separate from the future campus D-01."""
# TEMPORARY-DEPENDENCY D-TEST-ACCOUNTS: dedicated directory inventory is in README.md.
import os


def enabled():
    flag = os.getenv("D_TEST_ACCOUNTS_ENABLED", "0")
    if flag not in {"", "0", "1"}:
        raise RuntimeError("D_TEST_ACCOUNTS_ENABLED must be 0 or 1")
    if flag != "1":
        return False
    if os.getenv("APP_ENV") not in {"staging", "test"}:
        raise RuntimeError("Test accounts require APP_ENV=staging or test")
    return True
