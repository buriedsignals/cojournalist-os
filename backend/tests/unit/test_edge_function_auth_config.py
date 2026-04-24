from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SUPABASE_CONFIG = REPO_ROOT / "supabase" / "config.toml"
SUPABASE_FUNCTIONS = REPO_ROOT / "supabase" / "functions"
AUTH_MARKERS = ("requireUser(req)", "requireUserOrApiKey(req)")


def _configured_verify_jwt_settings() -> dict[str, bool]:
    settings: dict[str, bool] = {}
    current_function: str | None = None

    for raw_line in SUPABASE_CONFIG.read_text().splitlines():
        line = raw_line.strip()
        match = re.match(r"^\[functions\.([^\]]+)\]$", line)
        if match:
            current_function = match.group(1)
            continue
        if current_function and line.startswith("verify_jwt"):
            _, _, value = line.partition("=")
            settings[current_function] = value.strip().lower() == "true"
            current_function = None

    return settings


def _functions_using_in_handler_auth() -> list[str]:
    functions: list[str] = []

    for entrypoint in SUPABASE_FUNCTIONS.glob("*/index.ts"):
        contents = entrypoint.read_text()
        if any(marker in contents for marker in AUTH_MARKERS):
            functions.append(entrypoint.parent.name)

    return sorted(functions)


def test_in_handler_auth_functions_disable_gateway_jwt_verification() -> None:
    configured = _configured_verify_jwt_settings()
    missing = [
        name
        for name in _functions_using_in_handler_auth()
        if configured.get(name) is not False
    ]

    assert missing == [], (
        "Functions that validate auth in-handler must set verify_jwt = false "
        f"in supabase/config.toml: {', '.join(missing)}"
    )
