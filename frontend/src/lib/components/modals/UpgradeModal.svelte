<script lang="ts">
	import { X, Zap, ExternalLink } from 'lucide-svelte';
	import { createEventDispatcher } from 'svelte';
	import * as m from '$lib/paraglide/messages';
	import { authStore } from '$lib/stores/auth';

	export let open = false;
	export let currentCredits = 0;
	export let requiredCredits = 0;
	export let operationType: 'extraction' | 'monitoring' | 'export' | 'scout scheduling' = 'extraction';

	const dispatch = createEventDispatcher();

	$: shortfall = Math.max(0, requiredCredits - currentCredits);
	$: upgradeUrl = $authStore.user?.upgrade_url || '#';

	function close() {
		dispatch('close');
	}

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			close();
		}
	}
</script>

{#if open}
	<div
		class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
		on:click={handleBackdropClick}
		on:keydown={(e) => e.key === 'Escape' && close()}
		role="button"
		tabindex="0"
	>
		<div class="modal-content">
			<!-- Header -->
			<div class="modal-header">
				<div class="icon-wrapper">
					<Zap class="w-6 h-6" />
				</div>
				<button on:click={close} class="close-button" aria-label="Close modal">
					<X class="w-5 h-5" />
				</button>
			</div>

			<!-- Content -->
			<div class="modal-body">
				<h2 class="modal-title">{m.upgrade_required()}</h2>
				<p class="modal-subtitle">
					{m.upgrade_needCredits({ operationType })}
				</p>

				<!-- Credit breakdown -->
				<div class="credit-breakdown">
					<div class="credit-row">
						<span class="credit-label">{m.upgrade_yourBalance()}</span>
						<span class="credit-value current">{m.upgrade_creditsUnit({ count: currentCredits })}</span>
					</div>
					<div class="credit-row">
						<span class="credit-label">{m.upgrade_requiredCredits()}</span>
						<span class="credit-value required">{m.upgrade_creditsUnit({ count: requiredCredits })}</span>
					</div>
					<div class="credit-divider"></div>
					<div class="credit-row shortfall">
						<span class="credit-label">{m.upgrade_shortfall()}</span>
						<span class="credit-value">{m.upgrade_creditsUnit({ count: shortfall })}</span>
					</div>
				</div>

				<p class="upgrade-hint">
					{m.upgrade_hint()}
				</p>
			</div>

			<!-- Footer -->
			<div class="modal-footer">
				<button on:click={close} class="btn-cancel">{m.common_cancel()}</button>
				<a
					href={upgradeUrl}
					target="_blank"
					rel="noopener noreferrer"
					class="btn-upgrade"
				>
					<span>{m.upgrade_upgradeToPro()}</span>
					<ExternalLink class="w-4 h-4" />
				</a>
			</div>
		</div>
	</div>
{/if}

<style>
	.modal-content {
		background: white;
		border-radius: 1.5rem;
		box-shadow: 0 20px 48px rgba(0, 0, 0, 0.12);
		max-width: 28rem;
		width: 100%;
		overflow: hidden;
		animation: modalIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
	}

	@keyframes modalIn {
		from {
			opacity: 0;
			transform: scale(0.95) translateY(10px);
		}
		to {
			opacity: 1;
			transform: scale(1) translateY(0);
		}
	}

	.modal-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1.5rem 1.5rem 0;
	}

	.icon-wrapper {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 3rem;
		height: 3rem;
		border-radius: 0.75rem;
		background: linear-gradient(135deg, #fbbf24, #f59e0b);
		color: white;
	}

	.close-button {
		color: var(--color-text-tertiary);
		transition: color 0.2s ease;
		padding: 0.5rem;
		border-radius: 0.5rem;
	}

	.close-button:hover {
		color: var(--color-text-primary);
		background: var(--color-bg-tertiary);
	}

	.modal-body {
		padding: 1.5rem;
	}

	.modal-title {
		font-family: 'Crimson Pro', Georgia, serif;
		font-size: 1.5rem;
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: 0.5rem;
	}

	.modal-subtitle {
		font-size: 0.9375rem;
		color: var(--color-text-secondary);
		margin-bottom: 1.5rem;
		line-height: 1.5;
	}

	.credit-breakdown {
		background: var(--color-bg-tertiary);
		border-radius: 0.75rem;
		padding: 1rem;
		margin-bottom: 1.25rem;
	}

	.credit-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.5rem 0;
	}

	.credit-label {
		font-size: 0.875rem;
		color: var(--color-text-secondary);
	}

	.credit-value {
		font-size: 0.875rem;
		font-weight: 600;
	}

	.credit-value.current {
		color: var(--color-text-primary);
	}
	.credit-value.required {
		color: var(--color-accent-dark);
	}

	.credit-divider {
		height: 1px;
		background: var(--color-border-strong);
		margin: 0.5rem 0;
	}

	.credit-row.shortfall .credit-value {
		color: #dc2626;
		font-weight: 700;
	}

	.upgrade-hint {
		font-size: 0.8125rem;
		color: var(--color-text-tertiary);
		text-align: center;
		font-style: italic;
	}

	.modal-footer {
		display: flex;
		gap: 0.75rem;
		padding: 1.5rem;
		background: var(--color-bg-tertiary);
		border-top: 1px solid var(--color-border);
	}

	.btn-cancel {
		flex: 1;
		padding: 0.75rem 1rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--color-text-secondary);
		background: white;
		border: 1px solid var(--color-border-strong);
		border-radius: 0.5rem;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.btn-cancel:hover {
		background: var(--color-bg-primary);
		border-color: var(--color-border-hover);
	}

	.btn-upgrade {
		flex: 1;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		padding: 0.75rem 1rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: white;
		background: linear-gradient(135deg, #f59e0b, #d97706);
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		transition: all 0.2s ease;
		text-decoration: none;
	}

	.btn-upgrade:hover {
		transform: translateY(-1px);
		box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
	}
</style>
