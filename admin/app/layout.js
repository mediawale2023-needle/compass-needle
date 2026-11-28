import localFont from 'next/font/local';
import './globals.css';
import './styles/admin-tokens.css';
import './styles/admin-legacy-bridge.css';
import './styles/admin-shell.css';
import './styles/admin-components.css';
import { AuthProvider } from '@/lib/auth';

// Geist is the Admin typeface. It has no Devanagari glyphs, so Hindi and
// Marathi text (citizen messages, local-script names) falls back to Noto Sans
// Devanagari rather than an arbitrary system font.
// The files are self-hosted (app/fonts, OFL-1.1, from Fontsource) so the
// production build never depends on reaching Google Fonts — that fetch was the
// main cause of red CI builds, and red builds now block deploys.
const geist = localFont({
    src: './fonts/geist-latin-wght.woff2',
    weight: '100 900',
    variable: '--font-geist',
    display: 'swap',
});
const geistMono = localFont({
    src: './fonts/geist-mono-latin-wght.woff2',
    weight: '100 900',
    variable: '--font-geist-mono',
    display: 'swap',
});
const devanagari = localFont({
    src: [
        { path: './fonts/noto-sans-devanagari-400.woff2', weight: '400', style: 'normal' },
        { path: './fonts/noto-sans-devanagari-500.woff2', weight: '500', style: 'normal' },
        { path: './fonts/noto-sans-devanagari-600.woff2', weight: '600', style: 'normal' },
    ],
    variable: '--font-devanagari',
    display: 'swap',
});

export const metadata = {
    title: 'Needle Command Center',
    description: 'Administrative Control Panel — Multi-tenant MP management',
};

export default function RootLayout({ children }) {
    return (
        <html lang="en" className={`${geist.variable} ${geistMono.variable} ${devanagari.variable}`}>
            <body>
                <AuthProvider>{children}</AuthProvider>
            </body>
        </html>
    );
}
