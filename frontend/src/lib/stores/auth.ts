/**
 * Auth Store — Supabase Auth (self-hosted deployment).
 *
 * Re-exports from auth-supabase for email/password authentication.
 *
 * USED BY: All components that import from '$lib/stores/auth'
 */
import * as supabase from './auth-supabase';

export const authStore = supabase.authStore;
export const currentUser = supabase.currentUser;
export const auth = supabase.auth;
