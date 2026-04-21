#!/usr/bin/env python3
"""
Bump a user's coJournalist credits by email address.

⚠️ NEEDS v2 PORT — TARGETS DYNAMODB, NOT SUPABASE
After the 2026-04-21 v2 cutover, live credits live in Supabase
public.credit_accounts. This script still writes to DynamoDB
(scraping-jobs CREDITS records) and so is currently a no-op
against production. Tracked in POST-CUTOVER-TODO.md as item #9.

Looks up the user via MuckRock API (email -> UUID), then reads/updates
their CREDITS record in DynamoDB.

SETUP
-----
Requires the backend venv (boto3, httpx, dotenv):

    cd backend && source .venv/bin/activate
    python3 scripts/bump_credits.py <email> <new_balance>

Reads MUCKROCK_CLIENT_ID and MUCKROCK_CLIENT_SECRET from ../.env.

EXAMPLES
--------
    # Look up a user (show current balance, no changes)
    python3 scripts/bump_credits.py mads.trellevik@ba.no

    # Set their balance to 500
    python3 scripts/bump_credits.py mads.trellevik@ba.no 500

    # Add 200 credits on top of current balance
    python3 scripts/bump_credits.py mads.trellevik@ba.no +200
"""
import argparse
import sys
import time
from pathlib import Path

import boto3
import httpx
from dotenv import dotenv_values

TABLE_NAME = "scraping-jobs"
MUCKROCK_BASE_URL = "https://accounts.muckrock.com"


def load_env():
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        print(f"Error: {env_path} not found", file=sys.stderr)
        sys.exit(1)
    env = dotenv_values(env_path)
    client_id = env.get("MUCKROCK_CLIENT_ID", "")
    client_secret = env.get("MUCKROCK_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        print("Error: MUCKROCK_CLIENT_ID and MUCKROCK_CLIENT_SECRET must be set in .env", file=sys.stderr)
        sys.exit(1)
    return client_id, client_secret


def get_muckrock_token(client_id: str, client_secret: str) -> str:
    """Get a client_credentials access token from MuckRock."""
    resp = httpx.post(
        f"{MUCKROCK_BASE_URL}/openid/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code != 200:
        print(f"Error: MuckRock token request failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)
    return resp.json()["access_token"]


def find_user_uuid_by_email(email: str, token: str, table) -> str | None:
    """Scan DynamoDB USER# profiles, look up each via MuckRack API to match email."""
    # Scan for all USER# PROFILE records
    items = []
    scan_kwargs = {
        "FilterExpression": "begins_with(PK, :pk) AND SK = :sk",
        "ExpressionAttributeValues": {":pk": "USER#", ":sk": "PROFILE"},
        "ProjectionExpression": "PK, username",
    }
    while True:
        resp = table.scan(**scan_kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    print(f"Found {len(items)} users in DynamoDB, checking emails via MuckRock API...")

    headers = {"Authorization": f"Bearer {token}"}
    target = email.lower().strip()

    for item in items:
        uuid = item["PK"].removeprefix("USER#")
        username = item.get("username", "?")
        try:
            resp = httpx.get(
                f"{MUCKROCK_BASE_URL}/api/users/{uuid}/",
                headers=headers,
                timeout=10,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            user_email = (data.get("email") or "").lower().strip()
            if user_email == target:
                print(f"  Match: {username} ({uuid})")
                return uuid
        except httpx.RequestError:
            continue

    return None


def get_credits(table, user_id: str) -> dict | None:
    resp = table.get_item(Key={"PK": f"USER#{user_id}", "SK": "CREDITS"})
    return resp.get("Item")


def set_balance(table, user_id: str, new_balance: int):
    table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": "CREDITS"},
        UpdateExpression="SET balance = :bal",
        ExpressionAttributeValues={":bal": new_balance},
    )


def main():
    parser = argparse.ArgumentParser(description="Look up a user by email and bump their credits.")
    parser.add_argument("email", help="User's email address")
    parser.add_argument("credits", nargs="?", default=None,
                        help="New balance (e.g. 500) or delta (e.g. +200). Omit to just display.")
    args = parser.parse_args()

    client_id, client_secret = load_env()
    token = get_muckrock_token(client_id, client_secret)

    dynamodb = boto3.resource("dynamodb", region_name="eu-central-1")
    table = dynamodb.Table(TABLE_NAME)

    uuid = find_user_uuid_by_email(args.email, token, table)
    if not uuid:
        print(f"\nNo user found with email: {args.email}", file=sys.stderr)
        sys.exit(1)

    credits = get_credits(table, uuid)
    if not credits:
        print(f"\nNo CREDITS record for user {uuid}", file=sys.stderr)
        sys.exit(1)

    balance = int(credits.get("balance", 0))
    cap = int(credits.get("monthly_cap", 0))
    tier = credits.get("tier", "?")

    print(f"\n  Tier:        {tier}")
    print(f"  Balance:     {balance}")
    print(f"  Monthly cap: {cap}")

    if args.credits is None:
        return

    # Parse credit argument
    credit_str = args.credits.strip()
    if credit_str.startswith("+"):
        new_balance = balance + int(credit_str[1:])
    elif credit_str.startswith("-"):
        new_balance = max(0, balance - int(credit_str[1:]))
    else:
        new_balance = int(credit_str)

    if new_balance == balance:
        print(f"\n  Balance already at {balance}, no change.")
        return

    set_balance(table, uuid, new_balance)
    print(f"\n  Balance updated: {balance} -> {new_balance}")


if __name__ == "__main__":
    main()
