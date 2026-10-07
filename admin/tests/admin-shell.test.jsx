import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock, pathnameRef, logoutMock, pushMock } = vi.hoisted(() => ({
    apiGetMock: vi.fn(),
    pathnameRef: { current: '/dashboard/system/whatsapp' },
    logoutMock: vi.fn(),
    pushMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({ apiGet: (path) => apiGetMock(path) }));
vi.mock('next/navigation', () => ({
    usePathname: () => pathnameRef.current,
    useRouter: () => ({ push: pushMock }),
}));
vi.mock('next/image', () => ({ default: ({ priority, ...props }) => <img {...props} /> }));
vi.mock('next/link', () => ({
    default: ({ href, children, ...props }) => <a href={typeof href === 'string' ? href : '#'} {...props}>{children}</a>,
}));
vi.mock('@/lib/auth', () => ({
    useAuth: () => ({ user: { username: 'ananya', display_name: 'Ananya Rao' }, loading: false, logout: logoutMock }),
}));

import DashboardLayout from '@/app/dashboard/layout';

const ALERTS = [
    { type: 'whatsapp_health', severity: 'critical', title: 'WhatsApp is degraded', description: 'Meta access token is invalid or missing.' },
    { type: 'setup_incomplete', severity: 'info', tenant_id: 3, title: 'Belgaum — setup incomplete' },
];

function renderShell() {
    return render(<DashboardLayout><div>Page body</div></DashboardLayout>);
}

describe('Admin shell', () => {
    beforeEach(() => {
        pathnameRef.current = '/dashboard/system/whatsapp';
        apiGetMock.mockReset();
        logoutMock.mockReset();
        apiGetMock.mockImplementation(async (path) => {
            if (path === '/api/admin/alerts') return { alerts: ALERTS, count: ALERTS.length };
            if (path === '/api/admin/mps') return { mps: [{ tenant_id: 7, display_name: 'Avichal Dubey', profile: { constituency: 'Udaipur Rural', state: 'Rajasthan' } }] };
            throw new Error(`unexpected ${path}`);
        });
    });

    it('renders the grouped sidebar with exactly one active destination', async () => {
        renderShell();
        const nav = screen.getByRole('navigation', { name: 'Primary' });
        expect(within(nav).getByRole('link', { name: /Messaging/ })).toHaveAttribute('aria-current', 'page');
        expect(within(nav).getByRole('link', { name: /^System/ })).not.toHaveAttribute('aria-current');
        expect(nav.querySelectorAll('[aria-current="page"]')).toHaveLength(1);
        expect(screen.getByText('Page body')).toBeInTheDocument();
    });

    it('shows sidebar counts derived from real alerts and nothing else', async () => {
        renderShell();
        const nav = screen.getByRole('navigation', { name: 'Primary' });
        await waitFor(() => expect(within(nav).getByRole('link', { name: 'Messaging, 1 critical' })).toBeInTheDocument());
        expect(within(nav).getByRole('link', { name: 'Onboarding, 1 to review' })).toBeInTheDocument();
        expect(within(nav).getByRole('link', { name: 'Command Centre, 1 critical' })).toBeInTheDocument();
        expect(within(nav).getByRole('link', { name: /^Cases$/ })).toBeInTheDocument();
        expect(screen.getByText('1 platform alert')).toBeInTheDocument();
    });

    it('shows no counts or health claims when alerts fail to load', async () => {
        apiGetMock.mockImplementation(async () => { throw new Error('down'); });
        renderShell();
        await waitFor(() => expect(apiGetMock).toHaveBeenCalledWith('/api/admin/alerts'));
        expect(screen.queryByText(/platform alert/)).not.toBeInTheDocument();
        expect(screen.queryByText('No platform alerts')).not.toBeInTheDocument();
    });

    it('renders a route-derived breadcrumb', () => {
        pathnameRef.current = '/dashboard/mps/7';
        renderShell();
        const crumbs = screen.getByRole('navigation', { name: 'Breadcrumb' });
        expect(within(crumbs).getByText('Customers')).toBeInTheDocument();
        expect(within(crumbs).getByRole('link', { name: 'Accounts' })).toHaveAttribute('href', '/dashboard/accounts');
        expect(within(crumbs).getByText('Account 360')).toHaveAttribute('aria-current', 'page');
    });

    it('opens and closes the mobile navigation drawer', () => {
        renderShell();
        const sidebar = screen.getByRole('complementary', { name: 'Needle Admin' });
        expect(sidebar).toHaveAttribute('data-open', 'false');
        fireEvent.click(screen.getByRole('button', { name: 'Open navigation' }));
        expect(sidebar).toHaveAttribute('data-open', 'true');
        fireEvent.keyDown(document, { key: 'Escape' });
        expect(sidebar).toHaveAttribute('data-open', 'false');
    });

    it('keeps sign-out reachable from the account menu', () => {
        renderShell();
        fireEvent.click(screen.getByRole('button', { name: 'Account menu for Ananya Rao' }));
        fireEvent.click(screen.getByRole('menuitem', { name: 'Sign out' }));
        expect(logoutMock).toHaveBeenCalledTimes(1);
    });

    it('searches real accounts and pages, then navigates', async () => {
        renderShell();
        const box = screen.getByRole('combobox', { name: 'Search accounts and pages' });
        fireEvent.focus(box);
        await waitFor(() => expect(apiGetMock).toHaveBeenCalledWith('/api/admin/mps'));
        fireEvent.change(box, { target: { value: 'udaipur' } });
        const option = await screen.findByRole('option', { name: /Avichal Dubey/ });
        await act(async () => { fireEvent.click(option); });
        expect(pushMock).toHaveBeenCalledWith('/dashboard/mps/7');
    });

    it('lists real alerts in the notification tray with destinations', async () => {
        renderShell();
        await waitFor(() => expect(screen.getByRole('button', { name: 'Notifications, 2 active' })).toBeInTheDocument());
        fireEvent.click(screen.getByRole('button', { name: 'Notifications, 2 active' }));
        const tray = screen.getByRole('dialog', { name: 'Alerts' });
        expect(within(tray).getByRole('link', { name: /WhatsApp is degraded/ })).toHaveAttribute('href', '/dashboard/system/whatsapp');
        expect(within(tray).getByRole('link', { name: /Belgaum — setup incomplete/ })).toHaveAttribute('href', '/dashboard/mps/3/setup');
    });
});
