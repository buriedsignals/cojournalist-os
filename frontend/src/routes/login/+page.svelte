<script lang="ts">
	import { createClient } from '@supabase/supabase-js';
	import { goto } from '$app/navigation';

	const SUPABASE_URL = import.meta.env.PUBLIC_SUPABASE_URL ?? '';
	const SUPABASE_ANON_KEY = import.meta.env.PUBLIC_SUPABASE_ANON_KEY ?? '';

	const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

	let email = '';
	let password = '';
	let error = '';
	let loading = false;
	let mode: 'login' | 'signup' | 'magic' = 'login';
	let magicLinkSent = false;

	async function handleLogin() {
		loading = true;
		error = '';

		try {
			if (mode === 'magic') {
				const { error: authError } = await supabase.auth.signInWithOtp({
					email
				});
				if (authError) {
					error = authError.message;
				} else {
					magicLinkSent = true;
				}
			} else if (mode === 'signup') {
				const { error: authError } = await supabase.auth.signUp({
					email,
					password
				});
				if (authError) {
					error = authError.message;
				} else {
					magicLinkSent = true;
					error = '';
				}
			} else {
				const { error: authError } = await supabase.auth.signInWithPassword({
					email,
					password
				});
				if (authError) {
					error = authError.message;
				} else {
					goto('/');
				}
			}
		} catch (e) {
			error = 'An unexpected error occurred';
		} finally {
			loading = false;
		}
	}
</script>

<div class="flex min-h-screen items-center justify-center bg-gray-50">
	<div class="w-full max-w-md space-y-8 rounded-lg bg-white p-8 shadow-md">
		<div class="text-center">
			<h1 class="text-2xl font-bold text-gray-900">coJournalist</h1>
			<p class="mt-2 text-sm text-gray-600">
				{#if mode === 'login'}
					Sign in to your account
				{:else if mode === 'signup'}
					Create a new account
				{:else}
					Sign in with magic link
				{/if}
			</p>
		</div>

		{#if magicLinkSent}
			<div class="rounded-md bg-green-50 p-4">
				<p class="text-sm text-green-800">
					{#if mode === 'signup'}
						Check your email to confirm your account.
					{:else}
						Check your email for a magic link to sign in.
					{/if}
				</p>
			</div>
		{:else}
			<form on:submit|preventDefault={handleLogin} class="space-y-6">
				{#if error}
					<div class="rounded-md bg-red-50 p-4">
						<p class="text-sm text-red-800">{error}</p>
					</div>
				{/if}

				<div>
					<label for="email" class="block text-sm font-medium text-gray-700">
						Email address
					</label>
					<input
						id="email"
						type="email"
						bind:value={email}
						required
						class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-blue-500"
						placeholder="you@newsroom.org"
					/>
				</div>

				{#if mode !== 'magic'}
					<div>
						<label for="password" class="block text-sm font-medium text-gray-700">
							Password
						</label>
						<input
							id="password"
							type="password"
							bind:value={password}
							required
							minlength="6"
							class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-blue-500"
						/>
					</div>
				{/if}

				<button
					type="submit"
					disabled={loading}
					class="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
				>
					{#if loading}
						...
					{:else if mode === 'login'}
						Sign in
					{:else if mode === 'signup'}
						Create account
					{:else}
						Send magic link
					{/if}
				</button>
			</form>

			<div class="flex flex-col items-center space-y-2 text-sm">
				{#if mode === 'login'}
					<button
						on:click={() => (mode = 'signup')}
						class="text-blue-600 hover:text-blue-500"
					>
						Create a new account
					</button>
					<button
						on:click={() => (mode = 'magic')}
						class="text-blue-600 hover:text-blue-500"
					>
						Sign in with magic link
					</button>
				{:else}
					<button
						on:click={() => {
							mode = 'login';
							magicLinkSent = false;
						}}
						class="text-blue-600 hover:text-blue-500"
					>
						Back to sign in
					</button>
				{/if}
			</div>
		{/if}
	</div>
</div>
