<script lang="ts">
	import { CalendarClock } from 'lucide-svelte';
	import * as m from '$lib/paraglide/messages';

	export let step1Disabled: boolean = false;
	export let step1Loading: boolean = false;
	export let step1Label: string;
	export let step1LoadingLabel: string;
	export let step2Enabled: boolean = false;
	export let step2Label: string = m.pulse_scheduleScout();
	export let step3Enabled: boolean = false;
	export let step3Label: string = '';
	export let step3Icon: ConstructorOfATypedSvelteComponent | null = null;

	/** Optional icon component rendered before step 1 label (only when not loading) */
	export let step1Icon: ConstructorOfATypedSvelteComponent | null = null;

	import { createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher<{
		step1: void;
		step2: void;
		step3: void;
	}>();

	$: hasStep3 = step3Label !== '';
</script>

<div class="flex flex-col gap-1.5">
	<!-- Step 1 -->
	<button
		class="btn-primary w-full relative !justify-center"
		on:click={() => dispatch('step1')}
		disabled={step1Disabled}
	>
		<span class="step-badge absolute left-4">1</span>
		<span class="flex items-center gap-2">
			{#if step1Loading}
				<span>{step1LoadingLabel}</span>
			{:else}
				{#if step1Icon}
					<svelte:component this={step1Icon} size={16} />
				{/if}
				<span>{step1Label}</span>
			{/if}
		</span>
	</button>

	<!-- L-connector -->
	<div class="step-connector"></div>

	<!-- Step 2 -->
	<button
		class="btn-secondary w-full relative !justify-center transition-all duration-300 {step2Enabled ? 'ring-2 ring-purple-500/30' : 'opacity-50'}"
		disabled={!step2Enabled}
		on:click={() => dispatch('step2')}
	>
		<span class="step-badge absolute left-4" class:step-active={step2Enabled}>2</span>
		<span class="flex items-center gap-2">
			{#if !hasStep3}
				<CalendarClock size={16} />
			{/if}
			<span>{step2Label}</span>
		</span>
	</button>

	{#if hasStep3}
		<!-- Optional content between step 2 and step 3 -->
		{#if $$slots['between-step2-step3']}
			<slot name="between-step2-step3" />
		{/if}

		<!-- L-connector -->
		<div class="step-connector"></div>

		<!-- Step 3 -->
		<button
			class="btn-secondary w-full relative !justify-center transition-all duration-300 {step3Enabled ? 'ring-2 ring-purple-500/30' : 'opacity-50'}"
			disabled={!step3Enabled}
			on:click={() => dispatch('step3')}
		>
			<span class="step-badge absolute left-4" class:step-active={step3Enabled}>3</span>
			<span class="flex items-center gap-2">
				<CalendarClock size={16} />
				<span>{step3Label}</span>
			</span>
		</button>
	{/if}
</div>

<style>
	.step-badge {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.25rem;
		height: 1.25rem;
		border-radius: 9999px;
		font-size: 0.6875rem;
		font-weight: 600;
		background: var(--color-bg-tertiary, #e5e7eb);
		color: var(--color-text-secondary);
	}

	.step-badge.step-active {
		background: var(--color-accent, #968bdf);
		color: white;
	}

	.step-connector {
		margin-left: 0.5rem;
		width: 0.5rem;
		height: 0.5rem;
		border-left: 1.5px solid var(--color-border, #d1d5db);
		border-bottom: 1.5px solid var(--color-border, #d1d5db);
		border-bottom-left-radius: 2px;
	}

	:global(.dark) .step-connector {
		border-color: #4b5563;
	}
</style>
