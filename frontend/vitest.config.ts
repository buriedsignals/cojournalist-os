import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
	resolve: {
		alias: {
			$lib: path.resolve(__dirname, 'src/lib'),
			'$app/environment': path.resolve(__dirname, 'src/tests/mocks/app-environment.ts'),
			'$app/stores': path.resolve(__dirname, 'src/tests/mocks/app-stores.ts'),
			'$env/dynamic/public': path.resolve(__dirname, 'src/tests/mocks/env-dynamic-public.ts')
		}
	},
	test: {
		include: ['src/**/*.test.ts'],
		environment: 'jsdom',
		globals: true,
		setupFiles: ['src/tests/setup.ts']
	}
});
