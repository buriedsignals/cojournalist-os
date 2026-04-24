export const IS_LOCAL_DEMO_MODE =
	(import.meta.env.PUBLIC_LOCAL_DEMO_MODE ?? '').trim().toLowerCase() === 'true';
