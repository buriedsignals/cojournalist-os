<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { goto } from '$app/navigation';
	import { Crosshair, MapPin, Radar, Users, Landmark } from 'lucide-svelte';
	import { authStore } from '$lib/stores/auth';
	import * as m from '$lib/paraglide/messages';

	export let open = false;
	export let sidebarCollapsed = false;

	$: isPro = ($authStore.user?.tier ?? 'free') !== 'free';

	const dispatch = createEventDispatcher<{
		trackPage: void;
		locationScout: void;
		beatScout: void;
		profileScout: void;
		civicScout: void;
		close: void;
	}>();

	function handleTrackPage() {
		dispatch('trackPage');
		dispatch('close');
	}

	function handleLocationScout() {
		dispatch('locationScout');
		dispatch('close');
	}

	function handleBeatScout() {
		dispatch('beatScout');
		dispatch('close');
	}

	function handleProfileScout() {
		dispatch('profileScout');
		dispatch('close');
	}

	function handleCivicScout() {
		if (!isPro) {
			dispatch('close');
			goto('/pricing');
			return;
		}
		dispatch('civicScout');
		dispatch('close');
	}

	function handleClickOutside(event: MouseEvent) {
		const target = event.target as HTMLElement;
		if (!target.closest('.new-scout-dropdown')) {
			dispatch('close');
		}
	}
</script>

{#if open}
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div class="dropdown-backdrop" on:click={handleClickOutside}>
		<div class="new-scout-dropdown" style:left={sidebarCollapsed ? '56px' : '228px'}>
			<button class="scout-option" on:click={handleTrackPage}>
				<div class="option-icon">
					<Crosshair size={20} />
				</div>
				<div class="option-content">
					<span class="option-title">{m.newScout_trackTitle()}</span>
					<span class="option-description">{m.newScout_trackDescription()}</span>
				</div>
			</button>

			<div class="option-divider"></div>

			<button class="scout-option" on:click={handleLocationScout}>
				<div class="option-icon">
					<MapPin size={20} />
				</div>
				<div class="option-content">
					<span class="option-title">{m.newScout_locationScoutTitle()}</span>
					<span class="option-description">{m.newScout_locationScoutDescription()}</span>
				</div>
			</button>

			<div class="option-divider"></div>

			<button class="scout-option" on:click={handleBeatScout}>
				<div class="option-icon">
					<Radar size={20} />
				</div>
				<div class="option-content">
					<span class="option-title">{m.newScout_beatScoutTitle()}</span>
					<span class="option-description">{m.newScout_beatScoutDescription()}</span>
				</div>
			</button>

			<div class="option-divider"></div>

			<button class="scout-option" on:click={handleProfileScout}>
				<div class="option-icon">
					<Users size={20} />
				</div>
				<div class="option-content">
					<span class="option-title">{m.newScout_profileTitle()}</span>
					<span class="option-description">{m.newScout_profileDescription()}</span>
				</div>
			</button>

			<div class="option-divider"></div>

			<button class="scout-option scout-option--civic" class:scout-option--locked={!isPro} on:click={handleCivicScout}>
				<div class="option-icon option-icon--civic" class:option-icon--locked={!isPro}>
					<Landmark size={20} />
				</div>
				<div class="option-content">
					<span class="option-title">
						{m.civic_trackCouncil()}
						{#if !isPro}
							<span class="pro-badge">PRO</span>
						{/if}
					</span>
					<span class="option-description">{m.civic_monitorDescription()}</span>
				</div>
			</button>
		</div>
	</div>
{/if}

<style>
	.dropdown-backdrop {
		position: fixed;
		inset: 0;
		z-index: 50;
		cursor: pointer;
	}

	.new-scout-dropdown {
		position: absolute;
		left: 228px;
		top: 60px;
		width: 280px;
		background: white;
		border: 1px solid #e5e7eb;
		border-radius: 0.75rem;
		box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
		padding: 0.5rem;
		animation: slideIn 0.15s ease-out;
	}

	@keyframes slideIn {
		from {
			opacity: 0;
			transform: translateX(-8px);
		}
		to {
			opacity: 1;
			transform: translateX(0);
		}
	}

	.scout-option {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		width: 100%;
		padding: 0.75rem;
		border: none;
		background: transparent;
		border-radius: 0.5rem;
		cursor: pointer;
		transition: background 0.15s ease;
		text-align: left;
	}

	.scout-option:hover {
		background: #f5f3ff;
	}

	.scout-option--civic:hover {
		background: #f0fdf4;
	}

	.option-icon {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 36px;
		height: 36px;
		border-radius: 0.5rem;
		background: #f3f4f6;
		color: #6b7280;
		transition: all 0.15s ease;
	}

	.scout-option:hover .option-icon {
		background: #ede9fe;
		color: #7c3aed;
	}

	.scout-option--civic:hover .option-icon--civic {
		background: #dcfce7;
		color: #16a34a;
	}

	.option-content {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
		min-width: 0;
	}

	.option-title {
		display: inline-flex;
		align-items: center;
		font-size: 0.875rem;
		font-weight: 600;
		color: #1f2937;
	}

	.option-description {
		font-size: 0.75rem;
		color: #6b7280;
		line-height: 1.4;
	}

	.option-divider {
		height: 1px;
		background: #f3f4f6;
		margin: 0.25rem 0.75rem;
	}

	.scout-option--locked {
		opacity: 0.6;
	}

	.scout-option--locked:hover {
		background: #f9fafb;
	}

	.option-icon--locked {
		background: #f3f4f6;
		color: #9ca3af;
	}

	.scout-option--locked:hover .option-icon--locked {
		background: #f3f4f6;
		color: #9ca3af;
	}

	.pro-badge {
		display: inline-block;
		font-size: 0.5625rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		padding: 0.125rem 0.375rem;
		background: linear-gradient(135deg, #f59e0b, #d97706);
		color: white;
		border-radius: 999px;
		vertical-align: middle;
		margin-left: 0.375rem;
	}
</style>
