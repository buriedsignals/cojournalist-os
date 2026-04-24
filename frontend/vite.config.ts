import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

const backendTarget = process.env.BACKEND_URL || 'http://localhost:8000';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	envPrefix: ['VITE_', 'PUBLIC_'],
	// Note: envDir only affects import.meta.env (build-time)
	// For $env/dynamic/public, vars must be in process.env (set via docker-compose)
	server: {
		port: 5173,
		proxy: {
			// Proxy API requests to backend during development
			'/api': {
				target: backendTarget,
				changeOrigin: true
			}
		}
	}
});
