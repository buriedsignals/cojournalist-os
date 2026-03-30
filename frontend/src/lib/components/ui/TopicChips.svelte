<script lang="ts">
	import { Tag, X } from 'lucide-svelte';
	import * as m from '$lib/paraglide/messages';

	export let topic: string = '';
	export let existingTopics: string[] = [];
	export let placeholder: string = '';

	const MAX_TOPICS = 3;

	let showSuggestions = false;
	let topicInputEl: HTMLInputElement;
	let currentInput = '';

	// Parse comma-separated topic string into array of chips
	$: topicChips = topic.split(',').map(t => t.trim()).filter(Boolean);

	// Filter suggestions based on current input, excluding already-added topics
	$: filteredTopics = existingTopics.filter(
		t => t.toLowerCase().includes(currentInput.toLowerCase())
			&& !topicChips.map(c => c.toLowerCase()).includes(t.toLowerCase())
	);

	// Update the topic string when chips change
	function updateTopicString() {
		topic = topicChips.join(', ');
	}

	function addTopic(newTopic: string) {
		const trimmed = newTopic.trim();
		if (!trimmed) return;

		// Check if already exists (case-insensitive)
		if (topicChips.map(c => c.toLowerCase()).includes(trimmed.toLowerCase())) return;

		// Check max limit
		if (topicChips.length >= MAX_TOPICS) return;

		topicChips = [...topicChips, trimmed];
		updateTopicString();
		currentInput = '';
		showSuggestions = false;
	}

	function removeTopic(index: number) {
		topicChips = topicChips.filter((_, i) => i !== index);
		updateTopicString();
		// Focus input after removing
		setTimeout(() => topicInputEl?.focus(), 0);
	}

	function selectSuggestion(t: string) {
		addTopic(t);
		topicInputEl?.focus();
	}

	function handleTopicFocus() {
		if (existingTopics.length > 0 && topicChips.length < MAX_TOPICS) {
			showSuggestions = true;
		}
	}

	function handleTopicBlur() {
		// Delay to allow click on suggestion
		setTimeout(() => {
			showSuggestions = false;
			// Add current input as chip if not empty
			if (currentInput.trim()) {
				addTopic(currentInput);
			}
		}, 150);
	}

	function handleTopicInput() {
		if (existingTopics.length > 0 && topicChips.length < MAX_TOPICS) {
			showSuggestions = true;
		}
	}

	function handleTopicKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' || e.key === 'Tab' || e.key === ',') {
			if (currentInput.trim()) {
				e.preventDefault();
				// Remove trailing comma if user pressed comma
				const cleanInput = currentInput.replace(/,+$/, '').trim();
				addTopic(cleanInput);
			}
		} else if (e.key === 'Backspace' && !currentInput && topicChips.length > 0) {
			// Remove last chip on backspace when input is empty
			e.preventDefault();
			removeTopic(topicChips.length - 1);
		}
	}
</script>

<!-- Topic chips and input -->
<div class="topic-chips-wrapper">
	<!-- Tag icon (matches location field's MapPin) -->
	<Tag size={14} class="topic-field-icon" />
	<!-- Existing topic chips -->
	{#each topicChips as chip, index}
		<div class="topic-chip">
			<Tag size={12} />
			<span>{chip}</span>
			<button type="button" class="chip-remove" on:click={() => removeTopic(index)}>
				<X size={12} />
			</button>
		</div>
	{/each}

	<!-- Input for new topics (hidden when max reached) -->
	{#if topicChips.length < MAX_TOPICS}
		<div class="topic-input-wrapper">
			<input
				type="text"
				bind:this={topicInputEl}
				bind:value={currentInput}
				on:focus={handleTopicFocus}
				on:blur={handleTopicBlur}
				on:input={handleTopicInput}
				on:keydown={handleTopicKeydown}
				placeholder={topicChips.length === 0 ? (placeholder || m.filter_topicPlaceholder()) : 'Add another...'}
				maxlength="50"
				class="topic-chip-input"
				autocomplete="off"
			/>
			{#if showSuggestions && filteredTopics.length > 0}
				<div class="topic-suggestions">
					{#each filteredTopics as suggestion}
						<button
							type="button"
							class="topic-suggestion"
							on:mousedown|preventDefault={() => selectSuggestion(suggestion)}
						>
							<Tag size={12} />
							<span>{suggestion}</span>
						</button>
					{/each}
				</div>
			{/if}
		</div>
	{:else}
		<span class="max-topics-hint">Max {MAX_TOPICS} topics</span>
	{/if}
</div>

<style>
	.topic-chips-wrapper {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		background: #fafafa;
		border: 1px solid #e5e7eb;
		border-radius: 0.5rem;
		min-height: 2.5rem;
		transition: all 0.2s ease;
	}

	.topic-chips-wrapper:focus-within {
		border-color: #968bdf;
		background: #ffffff;
		box-shadow: 0 0 0 3px rgba(150, 139, 223, 0.1);
	}

	.topic-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.25rem 0.5rem;
		background: linear-gradient(135deg, #f0eeff 0%, #e8e4ff 100%);
		border: 1px solid #d4cff7;
		border-radius: 9999px;
		color: #5b4dc7;
		font-size: 0.75rem;
		font-weight: 500;
		font-family: 'DM Sans', sans-serif;
	}

	.topic-chip :global(svg) {
		flex-shrink: 0;
	}

	.chip-remove {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0.125rem;
		border-radius: 9999px;
		background: transparent;
		border: none;
		color: #8b7fd4;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.chip-remove:hover {
		background: rgba(91, 77, 199, 0.2);
		color: #5b4dc7;
	}

	.topic-input-wrapper {
		position: relative;
		flex: 1;
		min-width: 80px;
	}

	.topic-chip-input {
		width: 100%;
		padding: 0.25rem 0;
		font-size: 0.8125rem;
		font-family: 'DM Sans', sans-serif;
		border: none;
		color: #1e293b;
		background: transparent;
		outline: none;
	}

	.topic-chip-input::placeholder {
		color: #94a3b8;
	}

	.max-topics-hint {
		font-size: 0.75rem;
		color: #9ca3af;
		font-style: italic;
	}

	.topic-suggestions {
		position: absolute;
		top: 100%;
		left: 0;
		right: 0;
		margin-top: 0.5rem;
		background: white;
		border: 1px solid #e5e7eb;
		border-radius: 0.5rem;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
		z-index: 50;
		max-height: 200px;
		overflow-y: auto;
	}

	.topic-suggestion {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		padding: 0.5rem 0.75rem;
		font-size: 0.8125rem;
		font-family: 'DM Sans', sans-serif;
		color: #374151;
		background: none;
		border: none;
		cursor: pointer;
		text-align: left;
		transition: background 0.1s ease;
	}

	.topic-suggestion:hover {
		background: #f3f4f6;
		color: #4f46e5;
	}

	.topic-suggestion :global(svg) {
		color: #9ca3af;
		flex-shrink: 0;
	}

	.topic-suggestion:hover :global(svg) {
		color: #4f46e5;
	}

	.topic-chips-wrapper :global(.topic-field-icon) {
		color: #968bdf;
		flex-shrink: 0;
	}
</style>
