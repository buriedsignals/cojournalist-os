#!/usr/bin/env python3
"""
Test MuckRock client_credentials grant (OAuth2).

CONTEXT
-------
coJournalist needs server-to-server access to fetch user
data (email, org membership) from accounts.muckrock.com. We switched from
passing the client_secret as a raw Bearer token (which returned 403) to a
proper OAuth2 client_credentials flow. MuckRock's /openid/token endpoint
returned "invalid_scope", then "invalid_client" — indicating the grant type
may not be enabled for this client.

This script exercises the exact same HTTP calls that our production code
makes (backend/app/services/muckrock_client.py lines 164-236) so the issue
can be reproduced and debugged independently of the rest of the codebase.

SETUP
-----
1. Fill in muckrock-credentials.txt at the repo root:

       MUCKROCK_CLIENT_ID=<client_id>
       MUCKROCK_CLIENT_SECRET=<secret>

2. Run:

       python3 test_muckrock_client_credentials.py

   No dependencies beyond the standard library are required.

WHAT IT TESTS
-------------
Step 1 — Token request
    POST https://accounts.muckrock.com/openid/token
    with HTTP Basic auth (client_id:client_secret)
    and body: grant_type=client_credentials

    Expected success: {"access_token": "...", "expires_in": ..., "token_type": "Bearer"}

Step 2 — User data fetch (only runs if Step 1 succeeds)
    GET https://accounts.muckrock.com/api/users/{uuid}/
    with Authorization: Bearer <token>

    Uses TEST_USER_UUID env var. Expected: JSON with an "email" field.

Step 3 — Alternate auth method (POST body credentials)
    Same as Step 1 but sends client_id/client_secret in the POST body
    instead of HTTP Basic auth, in case the server only supports one method.

PRODUCTION CODE REFERENCE
-------------------------
The production code that depends on this grant is in:

    backend/app/services/muckrock_client.py

    get_client_credentials_token()  — lines 164-200
        Makes the same POST /openid/token with HTTP Basic auth.

    fetch_user_data(uuid)           — lines 207-236
        Uses the token to GET /api/users/{uuid}/ and expects an email field.

    _get_authenticated_headers()    — lines 202-205
        Wraps the token in a Bearer Authorization header.

These are called from:

    backend/app/dependencies.py     — line ~237
        get_user_email() calls fetch_user_data() and reads response["email"].
"""

import base64
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = "https://accounts.muckrock.com"
TOKEN_ENDPOINT = f"{BASE_URL}/openid/token"
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "muckrock-credentials.txt")

# A test user UUID — replace with a real one if available.
# This is only used if the token request succeeds.
TEST_USER_UUID = os.getenv("TEST_USER_UUID", None)


def load_credentials():
    """Load client_id and client_secret from muckrock-credentials.txt."""
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"ERROR: {CREDENTIALS_FILE} not found.")
        print("Create it with:")
        print("    MUCKROCK_CLIENT_ID=<client_id>")
        print("    MUCKROCK_CLIENT_SECRET=<secret>")
        sys.exit(1)

    creds = {}
    with open(CREDENTIALS_FILE) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                creds[key.strip()] = value.strip()

    client_id = creds.get("MUCKROCK_CLIENT_ID", "")
    client_secret = creds.get("MUCKROCK_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print("ERROR: MUCKROCK_CLIENT_ID and MUCKROCK_CLIENT_SECRET must be set")
        print(f"       in {CREDENTIALS_FILE}")
        sys.exit(1)

    return client_id, client_secret


def http_post(url, data=None, headers=None):
    """Make a POST request, return (status_code, response_body_dict)."""
    body = urllib.parse.urlencode(data or {}).encode()
    req = urllib.request.Request(url, data=body, headers=headers or {}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def http_get(url, headers=None):
    """Make a GET request, return (status_code, response_body_dict)."""
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_token_basic_auth(client_id, client_secret):
    """Step 1: Request token using HTTP Basic auth (production method)."""
    print("=" * 60)
    print("STEP 1: Token request — HTTP Basic auth")
    print("=" * 60)
    print(f"  POST {TOKEN_ENDPOINT}")
    print(f"  Auth: Basic (client_id={client_id}, client_secret=***)")
    print(f"  Body: grant_type=client_credentials")
    print()

    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"grant_type": "client_credentials"}

    status, body = http_post(TOKEN_ENDPOINT, data=data, headers=headers)

    print(f"  Status: {status}")
    print(f"  Response: {json.dumps(body, indent=2)}")
    print()

    if status == 200 and "access_token" in body:
        print("  RESULT: SUCCESS — token received")
        return body["access_token"]
    else:
        print(f"  RESULT: FAILED — {body.get('error', 'unknown error')}")
        if "error_description" in body:
            print(f"  Detail: {body['error_description']}")
        return None


def test_token_post_body(client_id, client_secret):
    """Step 3: Request token with credentials in POST body (alternate method)."""
    print("=" * 60)
    print("STEP 3: Token request — POST body credentials")
    print("=" * 60)
    print(f"  POST {TOKEN_ENDPOINT}")
    print(f"  Body: grant_type=client_credentials")
    print(f"        client_id={client_id}")
    print(f"        client_secret=***")
    print()

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    status, body = http_post(TOKEN_ENDPOINT, data=data, headers=headers)

    print(f"  Status: {status}")
    print(f"  Response: {json.dumps(body, indent=2)}")
    print()

    if status == 200 and "access_token" in body:
        print("  RESULT: SUCCESS — token received")
        return body["access_token"]
    else:
        print(f"  RESULT: FAILED — {body.get('error', 'unknown error')}")
        if "error_description" in body:
            print(f"  Detail: {body['error_description']}")
        return None


def test_user_fetch(token, uuid):
    """Step 2: Fetch user data using the token."""
    print("=" * 60)
    print("STEP 2: User data fetch")
    print("=" * 60)
    url = f"{BASE_URL}/api/users/{uuid}/"
    print(f"  GET {url}")
    print(f"  Auth: Bearer ***")
    print()

    headers = {"Authorization": f"Bearer {token}"}
    status, body = http_get(url, headers=headers)

    print(f"  Status: {status}")
    print(f"  Response: {json.dumps(body, indent=2)}")
    print()

    if status == 200:
        if "email" in body:
            print(f"  RESULT: SUCCESS — email field present: {body['email']}")
        else:
            print("  RESULT: PARTIAL — 200 OK but no 'email' field in response")
            print(f"  Available fields: {list(body.keys())}")
    else:
        print(f"  RESULT: FAILED — status {status}")


def main():
    print()
    print("MuckRock Client Credentials Grant — Diagnostic Test")
    print()

    client_id, client_secret = load_credentials()

    # Step 1: HTTP Basic auth (this is what production uses)
    token = test_token_basic_auth(client_id, client_secret)

    # Step 2: If we got a token, try fetching user data
    if token and TEST_USER_UUID:
        test_user_fetch(token, TEST_USER_UUID)
    elif token:
        print("=" * 60)
        print("STEP 2: User data fetch — SKIPPED")
        print("=" * 60)
        print("  Set TEST_USER_UUID in this script to test user data fetch.")
        print()

    # Step 3: Try alternate auth method
    test_token_post_body(client_id, client_secret)

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if token:
        print("  Token grant is WORKING.")
        print("  No code changes needed — the production code in")
        print("  backend/app/services/muckrock_client.py should work as-is.")
    else:
        print("  Token grant is FAILING.")
        print()
        print("  For MuckRock to debug, verify that the client:")
        print("    1. Has 'client_credentials' in its allowed grant_types")
        print("    2. Supports HTTP Basic auth for client authentication")
        print("    3. Has the correct client_secret on file")
        print()
        print("  The relevant django-oidc-provider / Squarelet config is")
        print("  typically in the Client model's response_types and")
        print("  grant_types fields.")
    print()


if __name__ == "__main__":
    main()
