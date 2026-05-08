const path = require('path');
const { transformSync } = require('esbuild');
const { defineConfig } = require('vitest/config');
const react = require('@vitejs/plugin-react').default;

module.exports = defineConfig({
    plugins: [
        {
            name: 'treat-js-files-as-jsx',
            enforce: 'pre',
            transform(code, id) {
                if (!id.includes('/admin/')) return null;
                if (!/\.(js|jsx)$/.test(id)) return null;
                if (!/(\/app\/|\/components\/|\/lib\/)/.test(id)) return null;
                return transformSync(code, {
                    loader: 'jsx',
                    jsx: 'automatic',
                    format: 'esm',
                    sourcefile: id,
                });
            },
        },
        react({ include: /\.(js|jsx)$/ }),
    ],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, '.'),
        },
    },
    test: {
        environment: 'jsdom',
        globals: true,
        setupFiles: ['./test/setup.js'],
        include: ['tests/**/*.test.{js,jsx}'],
        exclude: ['e2e/**'],
    },
});
