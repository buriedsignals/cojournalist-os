<script lang="ts">
	import type { AINewsArticle } from '$lib/types';
	import { ExternalLink, Calendar, CheckCircle } from 'lucide-svelte';
	import * as m from '$lib/paraglide/messages';

	export let article: AINewsArticle;

	/**
	 * Format the published date to a readable format.
	 */
	function formatDate(dateString: string | null | undefined): string {
		if (!dateString) return '';
		try {
			const date = new Date(dateString);
			const now = new Date();
			const diffInMs = now.getTime() - date.getTime();
			const diffInHours = Math.floor(diffInMs / (1000 * 60 * 60));
			const diffInDays = Math.floor(diffInHours / 24);

			if (diffInHours < 1) {
				return m.newsCard_justNow();
			} else if (diffInHours < 24) {
				return m.newsCard_hoursAgo({ count: diffInHours });
			} else if (diffInDays === 1) {
				return m.newsCard_yesterday();
			} else if (diffInDays < 7) {
				return m.newsCard_daysAgo({ count: diffInDays });
			} else {
				return date.toLocaleDateString(undefined, {
					month: 'short',
					day: 'numeric',
					year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
				});
			}
		} catch (error) {
			return dateString;
		}
	}
</script>

<a
	href={article.url}
	target="_blank"
	rel="noopener noreferrer"
	class="news-card group block h-full overflow-hidden"
>
	<div class="card-layout">
		<!-- Article Content -->
		<div class="card-content">
			<!-- Source and Date -->
			<div class="mb-1.5 flex items-center justify-between text-xs text-gray-500">
				<div class="flex items-center gap-2">
					<span class="font-medium text-gray-700">{article.source}</span>
					{#if article.verified}
						<span class="verified-badge">
							<CheckCircle size={10} />
							{m.newsCard_verified()}
						</span>
					{/if}
				</div>
				{#if article.date}
					<div class="flex items-center gap-1">
						<Calendar size={12} />
						<span>{formatDate(article.date)}</span>
					</div>
				{/if}
			</div>

			<!-- Title -->
			<h3 class="mb-1.5 line-clamp-2 font-semibold text-gray-900 group-hover:text-green-600">
				{article.title}
			</h3>

			<!-- AI Summary -->
			{#if article.summary}
				<p class="mb-2 line-clamp-3 text-xs text-gray-600">
					{article.summary}
				</p>
			{/if}

			<!-- Footer -->
			<div class="flex items-center justify-end text-xs text-gray-500">
				<div class="flex items-center gap-1 text-green-600">
					<span>{m.newsCard_readArticle()}</span>
					<ExternalLink size={12} />
				</div>
			</div>
		</div>

		<!-- Article Image (right side) -->
		{#if article.imageUrl}
			<div class="card-image">
				<img
					src={article.imageUrl}
					alt={article.title}
					class="h-full w-full object-cover transition-transform group-hover:scale-105"
					loading="lazy"
				/>
			</div>
		{/if}
	</div>
</a>

<style>
	.news-card {
		border: 1px solid var(--color-border);
		border-radius: var(--radius-lg);
		background: var(--color-bg-secondary);
		box-shadow: var(--shadow-sm);
		transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
		position: relative;
	}

	.news-card::before {
		content: '';
		position: absolute;
		inset: 0;
		border-radius: var(--radius-lg);
		background: linear-gradient(135deg, rgba(16, 185, 129, 0.05), transparent);
		opacity: 0;
		transition: opacity 0.3s ease;
		pointer-events: none;
	}

	.news-card:hover {
		transform: translateY(-2px);
		box-shadow: var(--shadow-lg);
		border-color: rgba(16, 185, 129, 0.2);
	}

	.news-card:hover::before {
		opacity: 1;
	}

	.card-layout {
		display: flex;
		gap: 0.75rem;
		padding: 0.75rem;
	}

	.card-content {
		flex: 1;
		min-width: 0;
	}

	.card-image {
		flex-shrink: 0;
		width: 100px;
		align-self: stretch;
		border-radius: var(--radius-md);
		overflow: hidden;
		background: var(--color-surface);
	}

	.card-image img {
		object-position: center;
	}

	.verified-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.125rem 0.375rem;
		background: linear-gradient(135deg, #d1fae5, #a7f3d0);
		color: #059669;
		border-radius: 9999px;
		font-size: 0.625rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.025em;
	}

	.line-clamp-2 {
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.line-clamp-3 {
		display: -webkit-box;
		-webkit-line-clamp: 3;
		line-clamp: 3;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	h3 {
		line-height: 1.4;
	}

	p {
		line-height: 1.5;
	}
</style>
