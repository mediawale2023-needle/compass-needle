import './globals.css';
import { AuthProvider } from '@/lib/auth';

export const metadata = {
    title: 'Needle Command Center',
    description: 'Administrative Control Panel — Multi-tenant MP management',
};

export default function RootLayout({ children }) {
    return (
        <html lang="en">
            <body>
                <AuthProvider>{children}</AuthProvider>
            </body>
        </html>
    );
}
