<script lang="ts">
	export let size: number | string = 16;
	export let strokeWidth: number | string = 2;
</script>

<svg
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width={strokeWidth}
	aria-hidden="true"
	{...$$restProps}
>
	<path d="M4 12h16" />
	<path d="M12 4v16" />
</svg>
