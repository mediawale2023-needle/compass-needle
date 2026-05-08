import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

const { loginMock, pushMock, apiPostMock } = vi.hoisted(() => ({
    loginMock: vi.fn(),
    pushMock: vi.fn(),
    apiPostMock: vi.fn(),
}));

vi.mock('@/lib/auth', () => ({
    useAuth: () => ({
        user: null,
        login: loginMock,
    }),
}));

vi.mock('@/lib/api', () => ({
    apiPost: (path, body) => apiPostMock(path, body),
}));

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        push: pushMock,
    }),
}));

import AdminLoginPage from '@/app/page';

describe('Admin login page', () => {
    beforeEach(() => {
        loginMock.mockReset();
        pushMock.mockReset();
        apiPostMock.mockReset();
        vi.spyOn(global, 'fetch').mockResolvedValue({ ok: true });
    });

    it('stores the admin session and redirects after login', async () => {
        apiPostMock.mockResolvedValue({
            token: 'admin-token-123',
            user: {
                username: 'sysadmin',
                display_name: 'System Admin',
                role: 'sysadmin',
            },
        });

        render(<AdminLoginPage />);

        fireEvent.change(screen.getByPlaceholderText('Enter your username'), { target: { value: 'sysadmin' } });
        fireEvent.change(screen.getByPlaceholderText('Enter your password'), { target: { value: 'AdminPass1!' } });
        fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

        await waitFor(() => {
            expect(apiPostMock).toHaveBeenCalledWith('/api/admin/auth/login', {
                username: 'sysadmin',
                password: 'AdminPass1!',
            });
        });
        await waitFor(() => {
            expect(loginMock).toHaveBeenCalledWith('admin-token-123', expect.objectContaining({ username: 'sysadmin' }));
        });
        await waitFor(() => {
            expect(pushMock).toHaveBeenCalledWith('/dashboard');
        });
    });
});
