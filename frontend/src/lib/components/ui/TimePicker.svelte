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
		<label class="block text-sm font-medium text-gray-700 mb-1.5">
			<Clock class="inline h-4 w-4 mr-1" />
			{m.timePicker_label({ timezone: timezoneLabel })}
		</label>
	{/if}

	<div class="flex items-center gap-2">
		<!-- Hour Select -->
		<select
			bind:value={hour}
			class="form-input flex-1 text-sm"
		>
			<option value={12}>12</option>
			{#each Array.from({ length: 11 }, (_, i) => i + 1) as h}
				<option value={h}>{h}</option>
			{/each}
		</select>

		<span class="text-gray-500 font-medium">:</span>

		<!-- Minute Select -->
		<select
			bind:value={minute}
			class="form-input flex-1 text-sm"
		>
			<option value={0}>00</option>
			<option value={15}>15</option>
			<option value={30}>30</option>
			<option value={45}>45</option>
		</select>

		<!-- Period Select -->
		<select
			bind:value={period}
			class="form-input flex-1 text-sm"
		>
			<option value="AM">AM</option>
			<option value="PM">PM</option>
		</select>
	</div>
</div>
