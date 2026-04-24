<script lang="ts">
	import { Clock } from 'lucide-svelte';
	import { createEventDispatcher } from 'svelte';
	import * as m from '$lib/paraglide/messages';

	export let hour = 12;
	export let minute = 0;
	export let period: 'AM' | 'PM' = 'PM';
	export let timezoneLabel = 'your timezone';
	export let showLabel = true;

	const dispatch = createEventDispatcher<{ change: { hour: number; minute: number; period: 'AM' | 'PM'; time24h: string } }>();

	// Computed 24h time (null-safe)
	$: time24h = (() => {
		let h = hour ?? 12;
		const m = minute ?? 0;
		if (period === 'AM' && h === 12) h = 0;
		else if (period === 'PM' && h !== 12) h += 12;
		return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
	})();

	// Dispatch change event when values change
	$: dispatch('change', { hour, minute: minute ?? 0, period, time24h });
</script>

<div class="time-picker">
	{#if showLabel}
		<label class="form-label time-label">
			<Clock size={14} class="time-label-icon" />
			<span>{m.timePicker_label({ timezone: timezoneLabel })}</span>
		</label>
	{/if}

	<div class="time-row">
		<!-- Hour Select -->
		<select bind:value={hour} class="form-select time-slot">
			<option value={12}>12</option>
			{#each Array.from({ length: 11 }, (_, i) => i + 1) as h}
				<option value={h}>{h}</option>
			{/each}
		</select>

		<span class="time-sep">:</span>

		<!-- Minute Select -->
		<select bind:value={minute} class="form-select time-slot">
			<option value={0}>00</option>
			<option value={15}>15</option>
			<option value={30}>30</option>
			<option value={45}>45</option>
		</select>

		<!-- Period Select -->
		<select bind:value={period} class="form-select time-slot">
			<option value="AM">AM</option>
			<option value="PM">PM</option>
		</select>
	</div>
</div>

<style>
	.time-picker {
		margin-bottom: 1.25rem;
	}

	.time-picker:last-child {
		margin-bottom: 0;
	}

	.time-label {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
	}

	.time-label :global(.time-label-icon) {
		color: var(--color-ink-subtle);
		flex-shrink: 0;
	}

	.time-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.time-sep {
		color: var(--color-ink-muted);
		font-weight: 500;
	}

	.time-slot {
		flex: 1;
	}
</style>
