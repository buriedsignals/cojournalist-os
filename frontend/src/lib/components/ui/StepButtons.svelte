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

	export let onStep1: () => void = () => {};
	export let onStep2: () => void = () => {};
	export let onStep3: () => void = () => {};

	$: hasStep3 = step3Label !== '';
</script>

<div class="flex flex-col gap-1.5">
	<!-- Step 1 -->
	<button
		class="btn-primary w-full relative justify-center!"
		on:click={onStep1}
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
		class="btn-secondary w-full relative justify-center! transition-all duration-300 {step2Enabled ? 'ring-2 ring-purple-500/30' : 'opacity-50'}"
		disabled={!step2Enabled}
		on:click={onStep2}
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
			class="btn-secondary w-full relative justify-center! transition-all duration-300 {step3Enabled ? 'ring-2 ring-purple-500/30' : 'opacity-50'}"
			disabled={!step3Enabled}
			on:click={onStep3}
		>
			<span class="step-badge absolute left-4" class:step-active={step3Enabled}>3</span>
			<span class="flex items-center gap-2">
				{#if step3Icon}
					<svelte:component this={step3Icon} size={16} />
				{:else}
					<CalendarClock size={16} />
				{/if}
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
		width: 1.375rem;
		height: 1.375rem;
		border: 1px solid var(--color-border-strong);
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 500;
		background: var(--color-bg);
		color: var(--color-ink-muted);
	}

	.step-badge.step-active {
		background: var(--color-primary);
		border-color: var(--color-primary);
		color: var(--color-bg);
	}

	.step-connector {
		margin-left: 0.6875rem;
		width: 0.5rem;
		height: 0.5rem;
		border-left: 1px solid var(--color-border-strong);
		border-bottom: 1px solid var(--color-border-strong);
	}
</style>
