#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"

case "$MODE" in
	saas)
		SMOKE_URL="http://localhost:5173"
		;;
	oss-demo)
		SMOKE_URL="http://localhost:4173"
		;;
	-h | --help | help | "")
		cat <<'USAGE'
Usage:
  scripts/dev/browser-smoke.sh saas
  scripts/dev/browser-smoke.sh oss-demo

This script uses browser-harness against the current Chrome session. It does not
enter credentials; sign in manually first if the app is on /login.
USAGE
		exit 0
		;;
	*)
		echo "Unknown mode: $MODE" >&2
		exit 1
		;;
esac

command -v browser-harness >/dev/null 2>&1 || {
	echo "browser-harness is not installed or not on PATH." >&2
	exit 1
}

COJO_SMOKE_MODE="$MODE" COJO_SMOKE_URL="$SMOKE_URL" browser-harness <<'PY'
import json
import os
import sys

mode = os.environ["COJO_SMOKE_MODE"]
url = os.environ["COJO_SMOKE_URL"]


def fail(message):
	path = f"/tmp/cojo-browser-smoke-{mode}.png"
	try:
		screenshot(path, full=True)
		print(f"FAIL: {message} (screenshot: {path})")
	except Exception:
		print(f"FAIL: {message}")
	raise SystemExit(1)


def evaluate(expression):
	return js(expression)


def body_text():
	return evaluate("document.body ? document.body.innerText : ''") or ""


def wait_for(predicate, timeout_ticks=30, label="condition"):
	for _ in range(timeout_ticks):
		if predicate():
			return
		wait(0.25)
	fail(f"Timed out waiting for {label}")


def install_error_capture():
	evaluate("""
(() => {
	window.__cojoSmokeErrors = [];
	const push = (value) => window.__cojoSmokeErrors.push(String(value || ''));
	window.addEventListener('error', (event) => {
		push(event.message || (event.error && event.error.message) || 'window error');
	});
	window.addEventListener('unhandledrejection', (event) => {
		const reason = event.reason;
		push((reason && reason.message) || reason || 'unhandled rejection');
	});
	const originalError = console.error;
	console.error = (...args) => {
		push(args.map((arg) => {
			if (arg instanceof Error) return arg.message;
			if (typeof arg === 'string') return arg;
			try { return JSON.stringify(arg); } catch { return String(arg); }
		}).join(' '));
		originalError.apply(console, args);
	};
	return true;
})()
""")


def smoke_errors():
	raw = evaluate("JSON.stringify(window.__cojoSmokeErrors || [])") or "[]"
	try:
		return json.loads(raw)
	except Exception:
		return [str(raw)]


def assert_no_legacy_event_error(stage):
	matches = [
		error for error in smoke_errors()
		if "void 0 is not a function" in error or "(void 0) is not a function" in error
	]
	if matches:
		fail(f"Legacy component event error after {stage}: {matches[0]}")


def click_by_text(label):
	needle = json.dumps(label.lower())
	ok = evaluate(f"""
(() => {{
	const wanted = {needle};
	const visible = (el) => Boolean(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
	const textFor = (el) => [
		el.innerText,
		el.textContent,
		el.getAttribute('aria-label'),
		el.getAttribute('title')
	].filter(Boolean).join(' ').replace(/\\s+/g, ' ').trim().toLowerCase();
	const candidates = Array.from(document.querySelectorAll('button, a, [role="button"], [role="menuitem"]'));
	const el = candidates.find((node) => visible(node) && textFor(node).includes(wanted));
	if (!el) return false;
	el.scrollIntoView({{ block: 'center', inline: 'center' }});
	el.click();
	return true;
}})()
""")
	if not ok:
		fail(f"Could not find clickable text: {label}")
	wait(0.35)
	assert_no_legacy_event_error(label)


def click_selector(selector, label=None):
	selector_json = json.dumps(selector)
	ok = evaluate(f"""
(() => {{
	const el = document.querySelector({selector_json});
	if (!el) return false;
	el.scrollIntoView({{ block: 'center', inline: 'center' }});
	el.click();
	return true;
}})()
""")
	if not ok:
		fail(f"Could not find selector: {label or selector}")
	wait(0.35)
	assert_no_legacy_event_error(label or selector)


def expect_text(label):
	wait_for(lambda: label in body_text(), label=f"text {label!r}")


new_tab(url)
wait_for_load()
wait(0.8)
install_error_capture()
assert_no_legacy_event_error("initial load")

text = body_text()
if "New Scout" not in text:
	if "Sign in" in text or "Welcome Back" in text or "Authenticate" in text:
		fail(f"{mode} smoke needs an authenticated Chrome session; sign in manually and rerun.")
	fail("Workspace did not load New Scout control.")

panels = [
	("Track a Page", "Page Tracking"),
	("Track a Beat", "Beat Monitoring"),
	("Track a Profile", "Profile Tracking"),
	("Track a Council", "Monitor a Local Council"),
]

for option, expected in panels:
	click_by_text("New Scout")
	for option_text, _ in panels:
		expect_text(option_text)
	click_by_text(option)
	expect_text(expected)
	click_selector(".back-to-workspace", "Back to workspace")
	expect_text("New Scout")

click_by_text("Agents")
expect_text("Connect your AI assistant")
click_selector('button[aria-label="Close"]', "Close agents modal")

click_selector('button[aria-label="User menu"]', "User menu")
click_by_text("Preferences")
expect_text("Preferences")
click_by_text("Cancel")

assert_no_legacy_event_error("workspace smoke")
print(f"PASS: {mode} browser smoke completed at {url}")
PY
