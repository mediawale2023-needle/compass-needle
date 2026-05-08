import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

const { loginMock, pushMock } = vi.hoisted(() => ({
    loginMock: vi.fn(),
    pushMock: vi.fn(),
}));

vi.mock('@/lib/auth', () => ({
    useAuth: () => ({
        user: null,
        login: loginMock,
    }),
}));

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        push: pushMock,
    }),
}));

import LoginPage from '@/app/page';

describe('MP login page', () => {
    beforeEach(() => {
        loginMock.mockReset();
        pushMock.mockReset();
        vi.spyOn(global, 'fetch').mockResolvedValue({ ok: true });
    });

    it('submits credentials and redirects on success', async () => {
        loginMock.mockResolvedValue({
            username: 'mp_arun',
            display_name: 'Arun Kumar',
        });

        render(<LoginPage />);

        fireEvent.change(screen.getByPlaceholderText('Enter your username'), { target: { value: 'mp_arun' } });
        fireEvent.change(screen.getByPlaceholderText('Enter your password'), { target: { value: 'ValidPass1!' } });
        fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

        await waitFor(() => {
            expect(loginMock).toHaveBeenCalledWith('mp_arun', 'ValidPass1!');
        });
        await waitFor(() => {
            expect(pushMock).toHaveBeenCalledWith('/dashboard');
        });
    });

    it('shows a friendly error when login fails', async () => {
        loginMock.mockRejectedValue(new Error('Invalid credentials'));

        render(<LoginPage />);

        fireEvent.change(screen.getByPlaceholderText('Enter your username'), { target: { value: 'mp_arun' } });
        fireEvent.change(screen.getByPlaceholderText('Enter your password'), { target: { value: 'wrong-pass' } });
        fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

        expect(await screen.findByText('Invalid credentials')).toBeInTheDocument();
        expect(pushMock).not.toHaveBeenCalled();
    });
});
