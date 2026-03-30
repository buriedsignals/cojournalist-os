/**
 * i18n Constants -- supported language registry for UI localization.
 *
 * USED BY: OnboardingModal.svelte, PreferencesModal.svelte, i18n/locale.ts
 * DEPENDS ON: (none)
 *
 * Defines the 12 supported languages and provides type guards and label
 * lookups. Adding or removing a language here requires matching changes
 * in messages/*.json files and the Paraglide compile step.
 */
export const SUPPORTED_LANGUAGES = [
	{ code: 'en', label: 'English' },
	{ code: 'de', label: 'Deutsch' },
	{ code: 'fr', label: 'Français' },
	{ code: 'es', label: 'Español' },
	{ code: 'it', label: 'Italiano' },
	{ code: 'pt', label: 'Português' },
	{ code: 'nl', label: 'Nederlands' },
	{ code: 'no', label: 'Norsk' },
	{ code: 'sv', label: 'Svenska' },
	{ code: 'da', label: 'Dansk' },
	{ code: 'fi', label: 'Suomi' },
	{ code: 'pl', label: 'Polski' }
] as const;

export type SupportedLanguageCode = (typeof SUPPORTED_LANGUAGES)[number]['code'];

/**
 * Type guard to check if a language code is supported.
 */
export function isSupported(code: string): code is SupportedLanguageCode {
	return SUPPORTED_LANGUAGES.some((l) => l.code === code);
}

/**
 * Get the label for a language code.
 */
export function getLanguageLabel(code: string): string {
	return SUPPORTED_LANGUAGES.find((l) => l.code === code)?.label || code;
}
