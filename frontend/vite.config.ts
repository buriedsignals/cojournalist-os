import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	envPrefix: ['VITE_', 'PUBLIC_'],
	// Note: envDir only affects import.meta.env (build-time)
	// For $env/dynamic/public, vars must be in process.env (set via docker-compose)
	server: {
		port: 5173,
		proxy: {
			// Proxy API requests to backend during development
			'/api': {
				target: process.env.BACKEND_URL || 'http://localhost:8000',
				changeOrigin: true
			}
		}
	}
});
