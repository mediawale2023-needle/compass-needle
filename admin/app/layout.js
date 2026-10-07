import { Geist, Geist_Mono, Noto_Sans_Devanagari } from 'next/font/google';
import './globals.css';
import './styles/admin-tokens.css';
import './styles/admin-legacy-bridge.css';
import './styles/admin-shell.css';
import './styles/admin-components.css';
import { AuthProvider } from '@/lib/auth';

// Geist is the Admin typeface. It has no Devanagari glyphs, so Hindi and
// Marathi text (citizen messages, local-script names) falls back to Noto Sans
// Devanagari rather than an arbitrary system font.
const geist = Geist({ subsets: ['latin'], variable: '--font-geist', display: 'swap' });
const geistMono = Geist_Mono({ subsets: ['latin'], variable: '--font-geist-mono', display: 'swap' });
const devanagari = Noto_Sans_Devanagari({ subsets: ['devanagari'], weight: ['400', '500', '600'], variable: '--font-devanagari', display: 'swap' });

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
