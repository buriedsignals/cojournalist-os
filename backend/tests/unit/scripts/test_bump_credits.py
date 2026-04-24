"""Tests for `bump_credits._parse_target` — the pure balance-delta parser.

The rest of the script is an asyncpg + asyncio CLI that's covered by manual
smoke testing (see docs/architecture/follow-ups.md and the script's own
usage examples). This file pins the user-facing semantics of the credit
argument: absolute (500), delta (+200), clamped subtraction (-50 → max 0).
"""
import pathlib
import sys

# Make `scripts` importable when running the test from `backend/`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from scripts.bump_credits import _parse_target  # noqa: E402


def test_absolute_value_replaces_balance():
    assert _parse_target(current=42, arg="500") == 500
    assert _parse_target(current=42, arg="0") == 0


def test_plus_prefix_adds_to_balance():
    assert _parse_target(current=10, arg="+50") == 60


def test_minus_prefix_subtracts_and_clamps_to_zero():
    assert _parse_target(current=100, arg="-30") == 70
    # Clamps at 0 — never goes negative (balance has CHECK (balance >= 0)).
    assert _parse_target(current=10, arg="-999") == 0


def test_whitespace_in_arg_is_tolerated():
    assert _parse_target(current=5, arg="  +10  ") == 15
