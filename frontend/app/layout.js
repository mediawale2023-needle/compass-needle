import './globals.css';
import { AuthProvider } from '@/lib/auth';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ToastProvider } from '@/components/ui/toast';

export const metadata = {
    title: 'Compass Needle',
    description: 'AI-powered grievance management and constituency operations platform',
};

export const viewport = {
    width: 'device-width',
    initialScale: 1,
    themeColor: '#006a4d',
};

export default function RootLayout({ children }) {
    return (
        <html lang="en">
            <head>
                <link rel="preconnect" href="https://fonts.googleapis.com" />
                <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
            </head>
            <body className="min-h-screen bg-background font-sans antialiased">
                <TooltipProvider>
                    <AuthProvider>
                        <ToastProvider>{children}</ToastProvider>
                    </AuthProvider>
                </TooltipProvider>
            </body>
        </html>
    );
}
