# `cojo` CLI — Post-Release Test Checklist

Run through this after merging to `main` and tagging a release
(`cli-v0.1.0` and onward). Exercises the full path a real user takes
from `install` to `run`. No GitHub auth required for install — release
assets live on the public mirror `buriedsignals/cojournalist-os`.

Full reference: `docs/cli-implementation.md`.

## 0. Prerequisites

```bash
which curl codesign spctl  # codesign/spctl are macOS-only
# For workflow log inspection you'll also want:
gh auth status             # logged in to buriedsignals/coJournalist (private monorepo)
```

## 1. Workflow completed on the private monorepo

The workflow runs where the Apple secrets live — the private
`buriedsignals/coJournalist` repo.

```bash
gh run list --repo buriedsignals/coJournalist --workflow=cli-release.yml --limit 3
```

Expected: most recent run `completed / success`, head branch `<tag>`.
If it failed: `gh run view <run-id> --log-failed --repo buriedsignals/coJournalist`.

## 2. Release published on the public mirror with all 8 files

```bash
gh release view cli-v0.1.0 --repo buriedsignals/cojournalist-os
# or in a browser (no auth):
# https://github.com/buriedsignals/cojournalist-os/releases/tag/cli-v0.1.0
```

Expected assets (count should be 8):

- `cojo-darwin-arm64` + `cojo-darwin-arm64.sha256`
- `cojo-darwin-x86_64` + `cojo-darwin-x86_64.sha256`
- `cojo-linux-arm64` + `cojo-linux-arm64.sha256`
- `cojo-linux-x86_64` + `cojo-linux-x86_64.sha256`

## 3. Download binary for this machine (no auth)

```bash
# Pick the asset name matching your platform (mac arm64 shown)
ASSET=cojo-darwin-arm64
mkdir -p /tmp/cojo-dl && cd /tmp/cojo-dl
curl -fsSL -O "https://github.com/buriedsignals/cojournalist-os/releases/latest/download/${ASSET}"
curl -fsSL -O "https://github.com/buriedsignals/cojournalist-os/releases/latest/download/${ASSET}.sha256"
ls -lh
```

Expected: two files — the binary (~73–88 MB) and the matching `.sha256`.

## 4. Verify sha256

```bash
# macOS
shasum -a 256 -c "${ASSET}.sha256"
# Linux
sha256sum -c "${ASSET}.sha256"
```

Expected: `${ASSET}: OK`.

## 5. Verify code signature (macOS only)

```bash
codesign --verify --deep --strict --verbose=2 "${ASSET}"
codesign -dv --verbose=4 "${ASSET}" 2>&1 | grep -E 'Authority|TeamIdentifier'
```

Expected:
- `${ASSET}: valid on disk` + `satisfies its Designated Requirement`
- `Authority=Developer ID Application: Thomas Théo Andreé Vaillant (W88GY2SHZ5)`
- `TeamIdentifier=W88GY2SHZ5`

## 6. Verify Gatekeeper acceptance (macOS only)

```bash
spctl --assess --type execute --verbose "${ASSET}"
```

Expected: `${ASSET}: accepted` + `source=Notarized Developer ID`.
If you see `source=Developer ID` without `Notarized`, notarization failed
silently — check workflow logs for the `notarytool` step.

## 7. Install

```bash
sudo install -m 0755 "${ASSET}" /usr/local/bin/cojo
which cojo && cojo --version
```

Expected: `/usr/local/bin/cojo` and `cojo 0.1.0` (no trailing `dev`).

## 8. First-run Gatekeeper test (macOS only, fresh machine or fresh download)

Open the binary the way a user would:

```bash
# Should NOT trigger the "unidentified developer" dialog
cojo --help
```

Expected: help text prints, no dialog. If you see the dialog, the binary
isn't notarized — stop and diagnose.

## 9. Configure against production

Point at the current FastAPI backend (pre-cutover) and paste a JWT:

```bash
cojo config set api_url=https://www.cojournalist.ai/api
cojo config set auth_token=<paste from browser devtools>
cojo config show
```

The JWT comes from <https://www.cojournalist.ai> after login — browser
devtools → Application → Cookies / localStorage, whichever holds the
session token. `cojo config show` should redact the token.

## 10. Read-only subcommand smoke

Each of these hits a different endpoint — covers the `resolvePath` shim end-to-end:

```bash
cojo projects list
cojo scouts list
cojo units list --since 7d
cojo units search --query "test"
```

Expected: tabular output (or `(no rows)` if the account is empty).
**Failures to watch for:**
- `404 Not Found` on a path like `/functions/v1/projects` → the shim is
  not rewriting. Check `resolvePath` logic in `lib/client.ts`.
- `401 Unauthorized` → JWT expired or wrong. Re-paste from devtools.

## 11. Write subcommand smoke (optional, creates real data)

Create and delete a scratch project to verify POST + DELETE round-trip:

```bash
cojo projects add --name "CLI smoke test $(date +%s)" --visibility private
cojo projects list | head -3
# Copy the id from output, then:
cojo projects delete <id>
```

Expected: project appears in the list, deletes cleanly.

## 12. Post-cutover shim verification (future)

Once the Supabase cutover is live, run the same smoke after flipping config:

```bash
cojo config set api_url=https://gfmdziplticfoakhrfpt.supabase.co/functions/v1
cojo projects list    # now hits /functions/v1/projects (not rewritten)
```

Both URLs should work from the same installed binary — that's the whole
point of the dual-backend shim. When all users are on Supabase and the
FastAPI backend retires, remove `resolvePath` (see
`docs/cli-implementation.md` → "Dual-backend path shim").

## 13. Cleanup

```bash
rm -rf /tmp/cojo-dl
# Keep /usr/local/bin/cojo if you're going to use it day-to-day
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `gh release view` says "release not found" on cojournalist-os | Workflow's release job failed, or `OSS_RELEASE_PAT` expired | Check workflow logs for the `Create GitHub release on public mirror` step; rotate PAT if needed |
| Workflow shows green but no release appeared on cojournalist-os | Cross-repo PAT step silently errored (shouldn't — softprops fails loudly, but rare) | Inspect `softprops/action-gh-release` logs; manually re-run workflow_dispatch with the same tag |
| `codesign --verify` fails | Signing step failed on runner | Check `Codesign binary` step logs; cert may have been revoked or `APPLE_CERT_PASSWORD` is wrong |
| `spctl --assess` says `source=Developer ID` not `Notarized Developer ID` | Notarization didn't actually run or Apple rejected | Check `Notarize binary` step logs; look for `Invalid` status from `notarytool log <submission-id>` |
| First-run dialog "cannot be opened because the developer cannot be verified" | Binary downloaded from a path that didn't clear quarantine | Usually means Gatekeeper can't reach Apple's notary-status server — retry on network, or `xattr -d com.apple.quarantine <path>` as a one-off |
| `404` on read-only subcommands | `resolvePath` shim broken or `api_url` misconfigured | Run `cojo config show`; verify it matches the production URL exactly |
| `401` on all requests | Stale JWT | Re-paste from browser devtools |
| Binary reports `cojo dev` not `cojo 0.1.0` | `sed` version-injection step didn't fire — build was a manual dispatch or local compile, not a tag push | Use the tag-triggered release, not `workflow_dispatch` |

## Rollback

Pre-install (no users have downloaded yet):

```bash
# Delete the release on the public mirror
gh release delete cli-v0.1.0 --repo buriedsignals/cojournalist-os --yes --cleanup-tag
# Delete the tag on the private monorepo too
git push --delete origin cli-v0.1.0
# fix the issue, re-tag
```

Post-install: leave the broken release up (users already downloaded anyway),
publish `cli-v0.1.1` with the fix. No auto-update yet — users re-run the
install command to upgrade.
