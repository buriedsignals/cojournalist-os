/**
 * Tooltip Action -- custom Svelte action for hover tooltips.
 *
 * USED BY: active workspace controls that need delayed hover tooltips
 * DEPENDS ON: (none)
 *
 * Creates a positioned tooltip DOM element on mouseenter with a 400ms delay.
 * Auto-flips from right to left if it would overflow the viewport.
 * Usage: <button use:tooltip={"Tooltip text"}>
 */
export function tooltip(node: HTMLElement, text: string) {
	let el: HTMLDivElement | null = null;
	let arrow: HTMLDivElement | null = null;
	let showTimeout: ReturnType<typeof setTimeout>;
	let hideTimeout: ReturnType<typeof setTimeout>;

	function show() {
		clearTimeout(hideTimeout);
		if (el) return;

		showTimeout = setTimeout(() => {
			el = document.createElement('div');
			el.className = 'custom-tooltip';
			el.textContent = text;

			arrow = document.createElement('div');
			arrow.className = 'custom-tooltip-arrow';
			el.appendChild(arrow);

			document.body.appendChild(el);
			position();

			requestAnimationFrame(() => {
				if (el) el.classList.add('visible');
			});
		}, 400);
	}

	function hide() {
		clearTimeout(showTimeout);
		if (!el) return;

		el.classList.remove('visible');
		const ref = el;
		hideTimeout = setTimeout(() => {
			ref.remove();
		}, 120);
		el = null;
		arrow = null;
	}

	function position() {
		if (!el) return;
		const rect = node.getBoundingClientRect();

		// Position to the right of the element
		const top = rect.top + rect.height / 2;
		const left = rect.right + 8;

		el.style.top = `${top}px`;
		el.style.left = `${left}px`;
		el.style.transform = 'translateY(-50%)';

		// If tooltip overflows viewport right, flip to left
		const elRect = el.getBoundingClientRect();
		if (elRect.right > window.innerWidth - 8) {
			el.style.left = `${rect.left - 8}px`;
			el.style.transform = 'translateX(-100%) translateY(-50%)';
			if (arrow) arrow.classList.add('right');
		}
	}

	node.addEventListener('mouseenter', show);
	node.addEventListener('mouseleave', hide);
	node.addEventListener('click', hide);

	// Remove native title to prevent double tooltip
	const originalTitle = node.getAttribute('title');
	if (originalTitle) node.removeAttribute('title');

	return {
		update(newText: string) {
			text = newText;
			if (el && arrow) {
				el.textContent = newText;
				el.appendChild(arrow);
			}
		},
		destroy() {
			clearTimeout(showTimeout);
			clearTimeout(hideTimeout);
			if (el) el.remove();
			node.removeEventListener('mouseenter', show);
			node.removeEventListener('mouseleave', hide);
			node.removeEventListener('click', hide);
			if (originalTitle) node.setAttribute('title', originalTitle);
		}
	};
}
