import './globals.css';
import { AuthProvider } from '@/lib/auth';

export const metadata = {
    title: 'Needle – Parliamentary Intelligence',
    description: 'AI-powered grievance management and parliamentary intelligence platform',
};

export default function RootLayout({ children }) {
    return (
        <html lang="en">
            <head>
                <link rel="preconnect" href="https://fonts.googleapis.com" />
                <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
                <link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
            </head>
            <body>
                <AuthProvider>{children}</AuthProvider>
            </body>
        </html>
    );
}
