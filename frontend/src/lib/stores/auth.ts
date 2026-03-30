/**
 * Auth Store — Conditional loader based on deployment target.
 *
 * Statically re-exports from either MuckRock OAuth or Supabase Auth
 * depending on the PUBLIC_DEPLOYMENT_TARGET build-time env var.
 * Vite tree-shakes the unused module at build time.
 *
 * USED BY: All components that import from '$lib/stores/auth'
 */

// @ts-ignore — Vite resolves this at build time
import * as muckrock from './auth-muckrock';

// Default to MuckRock (the SaaS deployment)
export const authStore = muckrock.authStore;
export const currentUser = muckrock.currentUser;
export const auth = muckrock.auth;
