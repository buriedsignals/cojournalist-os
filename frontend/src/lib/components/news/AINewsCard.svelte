<script lang="ts">
	import type { AINewsArticle } from '$lib/types';
	import { ExternalLink, Calendar, CheckCircle2 } from 'lucide-svelte';
	import * as m from '$lib/paraglide/messages';

	export let article: AINewsArticle;

	function formatDate(dateString: string | null | undefined): string {
		if (!dateString) return '';
		try {
			const date = new Date(dateString);
			const now = new Date();
			const diffInMs = now.getTime() - date.getTime();
			const diffInHours = Math.floor(diffInMs / (1000 * 60 * 60));
			const diffInDays = Math.floor(diffInHours / 24);

			if (diffInHours < 1) return m.newsCard_justNow();
			if (diffInHours < 24) return m.newsCard_hoursAgo({ count: diffInHours });
			if (diffInDays === 1) return m.newsCard_yesterday();
			if (diffInDays < 7) return m.newsCard_daysAgo({ count: diffInDays });

			return date.toLocaleDateString(undefined, {
				month: 'short',
				day: 'numeric',
				year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
			});
		} catch {
			return dateString;
		}
	}
</script>

<a
	href={article.url}
	target="_blank"
	rel="noopener noreferrer"
	class="news-card"
>
	<div class="news-card__body">
		<div class="news-card__meta">
			<div class="news-card__eyebrow-row">
				<span class="news-card__source">{article.source}</span>
				{#if article.verified}
					<span class="news-card__verified">
						<CheckCircle2 size={12} />
						{m.newsCard_verified()}
					</span>
				{/if}
			</div>
			{#if article.date}
				<div class="news-card__date">
					<Calendar size={12} />
					<span>{formatDate(article.date)}</span>
				</div>
			{/if}
		</div>

		<div class="news-card__content">
			<h3 class="news-card__title">{article.title}</h3>
			{#if article.summary}
				<p class="news-card__summary">{article.summary}</p>
			{/if}
		</div>

		<div class="news-card__footer">
			<span class="news-card__link">
				{m.newsCard_readArticle()}
				<ExternalLink size={12} />
			</span>
		</div>
	</div>

	{#if article.imageUrl}
		<div class="news-card__image">
			<img
				src={article.imageUrl}
				alt={article.title}
				loading="lazy"
			/>
		</div>
	{/if}
</a>

<style>
	.news-card {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border);
		color: inherit;
		text-decoration: none;
		transition: border-color 150ms ease, background 150ms ease;
	}

	.news-card:hover {
		border-color: var(--color-border-strong);
		background: var(--color-bg);
	}

	.news-card__body {
		display: flex;
		flex-direction: column;
		gap: 0.875rem;
		padding: 1rem;
		min-width: 0;
	}

	.news-card__meta {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.75rem;
	}

	.news-card__eyebrow-row {
		display: inline-flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.375rem;
	}

	.news-card__source,
	.news-card__date {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 500;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--color-ink-muted);
	}

	.news-card__verified {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.125rem 0.5rem;
		background: var(--color-primary-soft);
		border: 1px solid var(--color-primary);
		border-radius: var(--radius-pill);
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--color-primary-deep);
	}

	.news-card__content {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		min-width: 0;
	}

	.news-card__title {
		margin: 0;
		font-family: var(--font-display);
		font-size: 1.125rem;
		font-weight: 600;
		line-height: 1.2;
		letter-spacing: -0.01em;
		color: var(--color-ink);
	}

	.news-card__summary {
		margin: 0;
		font-family: var(--font-body);
		font-size: 0.875rem;
		line-height: 1.55;
		color: var(--color-ink-muted);
	}

	.news-card__footer {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		padding-top: 0.75rem;
		border-top: 1px solid var(--color-border);
	}

	.news-card__link {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 500;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--color-primary);
	}

	.news-card__image {
		border-top: 1px solid var(--color-border);
		background: var(--color-surface);
		aspect-ratio: 16 / 8;
		overflow: hidden;
	}

	.news-card__image img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	@media (min-width: 900px) {
		.news-card {
			grid-template-columns: minmax(0, 1fr) 140px;
		}

		.news-card__image {
			border-top: none;
			border-left: 1px solid var(--color-border);
			aspect-ratio: auto;
		}
	}
</style>
