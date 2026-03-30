<script lang="ts">
	export let badge: string = '';
	export let badgeVariant: 'purple' | 'blue' | 'amber' = 'purple';
	export let title: string = '';
	export let subtitle: string = '';
</script>

<section class="form-panel">
	{#if badge || title || subtitle}
		<header class="form-panel__header">
			{#if badge}
				<span class="form-panel__badge" class:form-panel__badge--blue={badgeVariant === 'blue'} class:form-panel__badge--amber={badgeVariant === 'amber'}>{badge}</span>
			{/if}
			{#if title}
				<h2 class="form-panel__title">{title}</h2>
			{/if}
			{#if subtitle}
				<p class="form-panel__subtitle">{subtitle}</p>
			{/if}
		</header>
	{/if}

	<div class="form-panel__content">
		<slot />
	</div>

	{#if $$slots.footer}
		<footer class="form-panel__footer">
			<slot name="footer" />
		</footer>
	{/if}
</section>

<style>
	.form-panel {
		width: 480px;
		background: white;
		border: 1px solid #e5e7eb;
		border-radius: 0.75rem;
		padding: 1.5rem;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
		transition: box-shadow 0.15s ease;
	}

	.form-panel:hover {
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
	}

	.form-panel__header {
		margin-bottom: 1.25rem;
	}

	.form-panel__badge {
		display: inline-flex;
		align-items: center;
		font-family: 'DM Sans', sans-serif;
		font-size: 0.75rem;
		font-weight: 500;
		color: #6d28d9;
		background: #ede9fe;
		padding: 0.125rem 0.625rem;
		border-radius: 9999px;
		margin-bottom: 0.5rem;
	}

	.form-panel__badge--blue {
		color: #2563eb;
		background: #dbeafe;
	}

	.form-panel__badge--amber {
		color: #92400e;
		background: #fef3c7;
	}

	.form-panel__title {
		font-family: 'Crimson Pro', Georgia, serif;
		font-size: 1.5rem;
		font-weight: 600;
		color: #111827;
		margin: 0 0 0.375rem 0;
		line-height: 1.2;
	}

	.form-panel__subtitle {
		font-size: 0.875rem;
		color: #6b7280;
		margin: 0;
		line-height: 1.5;
	}

	.form-panel__footer {
		margin-top: 1.5rem;
		padding-top: 1.25rem;
		border-top: 1px solid #f3f4f6;
	}
</style>
