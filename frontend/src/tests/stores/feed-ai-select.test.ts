/**
 * Tests for feed store AI select mode state and methods.
 * Verifies entering/exiting AI select mode, setting selected IDs,
 * summary, loading state, and sync to selectedUnitIds.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { feedStore } from '$lib/stores/feed';

/** Helper: read current store state synchronously. */
function getState() {
	return feedStore.getState();
}

describe('feed store — AI select mode', () => {
	beforeEach(() => {
		feedStore.reset();
	});

	// =========================================================================
	// Default state
	// =========================================================================

	it('initial state has all AI select fields at defaults', () => {
		const s = getState();
		expect(s.aiSelectMode).toBe(false);
		expect(s.aiSelectedUnitIds).toEqual([]);
		expect(s.aiSelectionSummary).toBe('');
		expect(s.aiSelectLoading).toBe(false);
	});

	// =========================================================================
	// enterAISelectMode
	// =========================================================================

	it('enterAISelectMode sets aiSelectMode to true', () => {
		feedStore.enterAISelectMode();
		expect(getState().aiSelectMode).toBe(true);
	});

	// =========================================================================
	// exitAISelectMode
	// =========================================================================

	it('exitAISelectMode clears all AI select state AND selectedUnitIds', () => {
		// Set up dirty state first
		feedStore.enterAISelectMode();
		feedStore.setAISelectedUnitIds(['a', 'b', 'c']);
		feedStore.setAISelectionSummary('Some summary');
		feedStore.setAISelectLoading(true);

		// Verify dirty state
		const dirty = getState();
		expect(dirty.aiSelectMode).toBe(true);
		expect(dirty.aiSelectedUnitIds).toEqual(['a', 'b', 'c']);
		expect(dirty.aiSelectionSummary).toBe('Some summary');
		expect(dirty.aiSelectLoading).toBe(true);
		expect(dirty.selectedUnitIds.size).toBe(3);

		// Exit
		feedStore.exitAISelectMode();

		const s = getState();
		expect(s.aiSelectMode).toBe(false);
		expect(s.aiSelectedUnitIds).toEqual([]);
		expect(s.aiSelectionSummary).toBe('');
		expect(s.aiSelectLoading).toBe(false);
		expect(s.selectedUnitIds.size).toBe(0);
	});

	// =========================================================================
	// setAISelectedUnitIds
	// =========================================================================

	it('setAISelectedUnitIds stores IDs AND syncs to selectedUnitIds Set', () => {
		feedStore.setAISelectedUnitIds(['unit-1', 'unit-2', 'unit-3']);

		const s = getState();
		expect(s.aiSelectedUnitIds).toEqual(['unit-1', 'unit-2', 'unit-3']);
		expect(s.selectedUnitIds).toEqual(new Set(['unit-1', 'unit-2', 'unit-3']));
	});

	it('setAISelectedUnitIds with empty array clears both', () => {
		feedStore.setAISelectedUnitIds(['a']);
		feedStore.setAISelectedUnitIds([]);

		const s = getState();
		expect(s.aiSelectedUnitIds).toEqual([]);
		expect(s.selectedUnitIds.size).toBe(0);
	});

	// =========================================================================
	// setAISelectionSummary
	// =========================================================================

	it('setAISelectionSummary stores the summary string', () => {
		feedStore.setAISelectionSummary('Found 5 relevant articles about climate change');

		expect(getState().aiSelectionSummary).toBe(
			'Found 5 relevant articles about climate change'
		);
	});

	it('setAISelectionSummary can be set to empty string', () => {
		feedStore.setAISelectionSummary('non-empty');
		feedStore.setAISelectionSummary('');

		expect(getState().aiSelectionSummary).toBe('');
	});

	// =========================================================================
	// setAISelectLoading
	// =========================================================================

	it('setAISelectLoading toggles loading state to true', () => {
		feedStore.setAISelectLoading(true);
		expect(getState().aiSelectLoading).toBe(true);
	});

	it('setAISelectLoading toggles loading state to false', () => {
		feedStore.setAISelectLoading(true);
		feedStore.setAISelectLoading(false);
		expect(getState().aiSelectLoading).toBe(false);
	});
});
