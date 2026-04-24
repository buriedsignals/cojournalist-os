#!/usr/bin/env python3
"""
Bump a user's coJournalist credit balance by email.

Post-cutover (2026-04-21): credits live in Supabase Postgres `credit_accounts`.
This script uses asyncpg directly against `DATABASE_URL` (the same DSN the
FastAPI app reads from `app.config.get_settings()`).

See docs/architecture/follow-ups.md for related cleanup items.

USAGE
-----
    python3 scripts/bump_credits.py <email>               # show balance, no write
    python3 scripts/bump_credits.py <email> <N>           # set balance to N
    python3 scripts/bump_credits.py <email> +N            # add N
    python3 scripts/bump_credits.py <email> -N            # subtract N (clamped to 0)

Any change with |delta| > 100 prompts for confirmation.

Requires the backend venv (so `app.config` + `asyncpg` are importable):

    cd backend && source .venv/bin/activate
    python3 scripts/bump_credits.py alice@example.com +50
"""
import argparse
import asyncio
import pathlib
import sys

import asyncpg

# Allow `import app.config` when run as `python3 scripts/bump_credits.py`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402


async def _find_user_id(conn: asyncpg.Connection, email: str) -> str | None:
    return await conn.fetchval(
        "SELECT id FROM auth.users WHERE LOWER(email) = LOWER($1)",
        email.strip(),
    )


async def _get_credits(conn: asyncpg.Connection, user_id: str):
    return await conn.fetchrow(
        "SELECT balance, tier, monthly_cap "
        "FROM credit_accounts WHERE user_id = $1::uuid",
        user_id,
    )


async def _set_balance(conn: asyncpg.Connection, user_id: str, new_balance: int) -> int:
    return await conn.fetchval(
        "UPDATE credit_accounts "
        "SET balance = $1, updated_at = NOW() "
        "WHERE user_id = $2::uuid RETURNING balance",
        new_balance, user_id,
    )


def _parse_target(current: int, arg: str) -> int:
    s = arg.strip()
    if s.startswith("+"):
        return current + int(s[1:])
    if s.startswith("-"):
        return max(0, current - int(s[1:]))
    return int(s)


async def _run(email: str, credits_arg: str | None) -> None:
    settings = get_settings()
    if not settings.database_url:
        print("Error: DATABASE_URL not set in backend .env", file=sys.stderr)
        sys.exit(1)

    conn = await asyncpg.connect(
        dsn=settings.database_url,
        statement_cache_size=0,  # Supavisor / PgBouncer compatibility.
    )
    try:
        user_id = await _find_user_id(conn, email)
        if user_id is None:
            print(f"No user found with email: {email}", file=sys.stderr)
            sys.exit(1)

        row = await _get_credits(conn, user_id)
        if row is None:
            print(f"No credit_accounts row for user {user_id}", file=sys.stderr)
            sys.exit(1)

        balance, tier, cap = row["balance"], row["tier"], row["monthly_cap"]
        print(f"\n  user_id:     {user_id}")
        print(f"  tier:        {tier}")
        print(f"  balance:     {balance}")
        print(f"  monthly_cap: {cap}")

        if credits_arg is None:
            return

        new_balance = _parse_target(balance, credits_arg)
        delta = new_balance - balance
        if delta == 0:
            print(f"\n  Balance already at {balance}, no change.")
            return

        if abs(delta) > 100:
            prompt = (
                f"\n  About to change balance by {delta:+d} "
                f"({balance} -> {new_balance}). Proceed? [y/N] "
            )
            resp = input(prompt)
            if resp.strip().lower() != "y":
                print("Aborted.")
                return

        final = await _set_balance(conn, user_id, new_balance)
        print(f"\n  Balance updated: {balance} -> {final}")
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Look up and bump a coJournalist user's credit balance by email.",
    )
    parser.add_argument("email", help="User email (case-insensitive match against auth.users)")
    parser.add_argument(
        "credits",
        nargs="?",
        default=None,
        help="New balance (500), delta (+200 / -50), or omit to just display.",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.email, args.credits))


if __name__ == "__main__":
    main()
