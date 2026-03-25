import { Inter } from 'next/font/google';
import { AuthProvider } from '@/lib/auth';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ToastProvider } from '@/components/ui/toast';
import './globals.css';

const inter = Inter({ subsets: ['latin'], display: 'swap' });

export const metadata = {
    title: 'Ambassador — Grievance Intelligence',
    description: 'AI-powered grievance management for political leaders',
    themeColor: '#2563eb',
};

export default function RootLayout({ children }) {
    return (
        <html lang="en" className={inter.className}>
            <body>
                <AuthProvider>
                    <ToastProvider>
                        <TooltipProvider delayDuration={200}>
                            {children}
                        </TooltipProvider>
                    </ToastProvider>
                </AuthProvider>
            </body>
        </html>
    );
}
