import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
});

if (typeof window !== 'undefined') {
    window.scrollTo = window.scrollTo || (() => {});
}

Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: window.matchMedia || ((query) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
    })),
});
