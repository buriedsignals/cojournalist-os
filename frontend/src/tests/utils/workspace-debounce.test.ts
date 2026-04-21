/**
 * Tests for workspace search debounce helper.
 * Pure logic — no Svelte rendering.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { debounce } from '$lib/utils/workspace-debounce';

describe('debounce', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('delays the callback by the wait interval', () => {
		const spy = vi.fn();
		const d = debounce(spy, 300);
		d('a');
		expect(spy).not.toHaveBeenCalled();
		vi.advanceTimersByTime(299);
		expect(spy).not.toHaveBeenCalled();
		vi.advanceTimersByTime(1);
		expect(spy).toHaveBeenCalledTimes(1);
		expect(spy).toHaveBeenCalledWith('a');
	});

	it('coalesces rapid calls into one trailing call with the last args', () => {
		const spy = vi.fn();
		const d = debounce(spy, 200);
		d('first');
		vi.advanceTimersByTime(50);
		d('second');
		vi.advanceTimersByTime(50);
		d('third');
		expect(spy).not.toHaveBeenCalled();
		vi.advanceTimersByTime(200);
		expect(spy).toHaveBeenCalledTimes(1);
		expect(spy).toHaveBeenCalledWith('third');
	});

	it('cancel() clears the pending call', () => {
		const spy = vi.fn();
		const d = debounce(spy, 300);
		d('x');
		d.cancel();
		vi.advanceTimersByTime(500);
		expect(spy).not.toHaveBeenCalled();
	});

	it('flush() fires the pending call immediately and clears the timer', () => {
		const spy = vi.fn();
		const d = debounce(spy, 300);
		d('flushme');
		d.flush();
		expect(spy).toHaveBeenCalledTimes(1);
		expect(spy).toHaveBeenCalledWith('flushme');
		vi.advanceTimersByTime(500);
		expect(spy).toHaveBeenCalledTimes(1);
	});

	it('flush() is a no-op when no call is pending', () => {
		const spy = vi.fn();
		const d = debounce(spy, 300);
		d.flush();
		expect(spy).not.toHaveBeenCalled();
	});

	it('supports multiple argument types', () => {
		const spy = vi.fn<(a: string, b: number) => void>();
		const d = debounce(spy, 100);
		d('hello', 42);
		vi.advanceTimersByTime(100);
		expect(spy).toHaveBeenCalledWith('hello', 42);
	});
});
