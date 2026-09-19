import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

// Government portal contact number in MP Settings.
//
// Regression pin for a real production dead end: a tenant with no
// govt_contact_primary_number saw "Send OTP", clicked it, and got a 400
// ("No portal contact number on file for this tenant") with no way to fix
// it anywhere in the MP app — the number was only writable through an
// admin-only endpoint that has no UI. These tests hold the escape hatch
// open: the input must appear by itself when nothing is on file, and
// "Send OTP" must not be clickable until a number exists.
//
// PHONE NUMBERS HERE ARE SYNTHETIC — never a real tenant's.

const SYNTHETIC = '9876543210';
const SYNTHETIC_ALT = '8123456780';

const { apiMock, apiGetMock, apiPostMock, apiPatchMock, pushMock } = vi.hoisted(() => ({
    apiMock: vi.fn(),
    apiGetMock: vi.fn(),
    apiPostMock: vi.fn(),
    apiPatchMock: vi.fn(),
    pushMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
    api: apiMock,
    apiGet: apiGetMock,
    apiPost: apiPostMock,
    apiPatch: apiPatchMock,
}));

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: pushMock }) }));

let mockUser = { username: 'owner_one', role: 'owner', constituency: 'Seat One', house: 'Lok Sabha' };
vi.mock('@/lib/auth', () => ({
    useAuth: () => ({ user: mockUser, logout: vi.fn() }),
}));

import SettingsPage from '@/app/dashboard/settings/page';

/** /api/govt-portal payload for an OTP-gated portal (Rajasthan-shaped). */
function portalPayload(contactNumber) {
    return {
        state: 'Rajasthan',
        supported: true,
        portal_contact_number: contactNumber,
        portal: {
            id: 1,
            portal_name: 'Rajasthan Sampark',
            otp_verification: { status: 'not_started', mobile_no: null, verified_at: null },
        },
    };
}

/** Routes every apiGet the settings page makes; only govt-portal matters here. */
function routeApiGet(contactNumber) {
    apiGetMock.mockImplementation((path) => {
        if (path === '/api/govt-portal') return Promise.resolve(portalPayload(contactNumber));
        if (path.includes('/staff')) return Promise.resolve({ staff: [] });
        return Promise.resolve({});
    });
}

async function renderSettings() {
    render(<SettingsPage />);
    await screen.findByText('Government Portal');
}

beforeEach(() => {
    vi.clearAllMocks();
    mockUser = { username: 'owner_one', role: 'owner', constituency: 'Seat One', house: 'Lok Sabha' };
    // The rest of the settings page (profile, team) is out of scope here —
    // resolve it quietly so only the portal card drives these assertions.
    apiMock.mockImplementation((path) => {
        if (path === '/api/profile') return Promise.resolve({ state: 'Rajasthan', party: '' });
        if (path === '/api/team') return Promise.resolve({ team: [], members: [] });
        return Promise.resolve({});
    });
});

describe('Government portal contact number — missing number', () => {
    it('auto-exposes the input when no number is on file', async () => {
        routeApiGet(null);
        await renderSettings();

        // The input is present without the operator having to find a control.
        expect(await screen.findByPlaceholderText('10-digit mobile number')).toBeTruthy();
        expect(screen.getByText(/Add the office number to use on this portal/i)).toBeTruthy();
    });

    it('disables Send OTP until a number exists', async () => {
        routeApiGet(null);
        await renderSettings();

        const sendBtn = await screen.findByRole('button', { name: /Send OTP/i });
        expect(sendBtn.disabled).toBe(true);

        fireEvent.click(sendBtn);
        // The dead-end 400 can no longer be triggered from the UI.
        expect(apiPostMock).not.toHaveBeenCalledWith('/api/govt/otp/send', expect.anything());
    });
});

describe('Government portal contact number — saving', () => {
    it('persists the number and updates the display without a page refresh', async () => {
        routeApiGet(null);
        apiPatchMock.mockResolvedValue({ success: true, contact_number: SYNTHETIC });
        await renderSettings();

        fireEvent.change(await screen.findByPlaceholderText('10-digit mobile number'), {
            target: { value: SYNTHETIC },
        });

        // Re-fetch after save returns the newly stored number.
        routeApiGet(SYNTHETIC);
        fireEvent.click(screen.getByRole('button', { name: 'Save' }));

        await waitFor(() => {
            expect(apiPatchMock).toHaveBeenCalledWith('/api/govt-portal/contact-number', {
                contact_number: SYNTHETIC,
            });
        });

        // Displayed value updates in place — no reload required.
        expect(await screen.findByText(SYNTHETIC)).toBeTruthy();
        expect(await screen.findByText(/Portal contact number saved/i)).toBeTruthy();
    });

    it('enables Send OTP once a number is on file', async () => {
        routeApiGet(SYNTHETIC);
        await renderSettings();

        const sendBtn = await screen.findByRole('button', { name: /Send OTP/i });
        expect(sendBtn.disabled).toBe(false);
    });

    it('surfaces a save error inline without losing what was typed', async () => {
        routeApiGet(null);
        apiPatchMock.mockRejectedValue(new Error('Enter a valid 10-digit Indian mobile number'));
        await renderSettings();

        const input = await screen.findByPlaceholderText('10-digit mobile number');
        fireEvent.change(input, { target: { value: '12345' } });
        fireEvent.click(screen.getByRole('button', { name: 'Save' }));

        expect(await screen.findByText(/Enter a valid 10-digit Indian mobile number/i)).toBeTruthy();
        // Still editable, entry preserved — the operator can correct it.
        expect(screen.getByPlaceholderText('10-digit mobile number').value).toBe('12345');
    });

    it('does not submit an empty number', async () => {
        routeApiGet(null);
        await renderSettings();
        await screen.findByPlaceholderText('10-digit mobile number');

        const saveBtn = screen.getByRole('button', { name: 'Save' });
        expect(saveBtn.disabled).toBe(true);
        fireEvent.click(saveBtn);
        expect(apiPatchMock).not.toHaveBeenCalled();
    });
});

describe('Government portal contact number — editing an existing number', () => {
    it('shows the saved number read-only, then reveals the input on edit', async () => {
        routeApiGet(SYNTHETIC);
        await renderSettings();

        // Read-only by default — not an always-open form.
        expect(await screen.findByText(SYNTHETIC)).toBeTruthy();
        expect(screen.queryByPlaceholderText('10-digit mobile number')).toBeNull();

        // The pencil is the only icon-only button in this card.
        const editBtn = screen
            .getAllByRole('button')
            .find((b) => b.querySelector('svg') && !b.textContent.trim());
        fireEvent.click(editBtn);

        expect(await screen.findByPlaceholderText('10-digit mobile number')).toBeTruthy();
    });

    it('replaces an existing number', async () => {
        routeApiGet(SYNTHETIC);
        apiPatchMock.mockResolvedValue({ success: true, contact_number: SYNTHETIC_ALT });
        await renderSettings();
        await screen.findByText(SYNTHETIC);

        const editBtn = screen
            .getAllByRole('button')
            .find((b) => b.querySelector('svg') && !b.textContent.trim());
        fireEvent.click(editBtn);

        fireEvent.change(await screen.findByPlaceholderText('10-digit mobile number'), {
            target: { value: SYNTHETIC_ALT },
        });
        routeApiGet(SYNTHETIC_ALT);
        fireEvent.click(screen.getByRole('button', { name: 'Save' }));

        await waitFor(() => {
            expect(apiPatchMock).toHaveBeenCalledWith('/api/govt-portal/contact-number', {
                contact_number: SYNTHETIC_ALT,
            });
        });
        expect(await screen.findByText(SYNTHETIC_ALT)).toBeTruthy();
    });

    it('cancel restores the saved number and closes the editor', async () => {
        routeApiGet(SYNTHETIC);
        await renderSettings();
        await screen.findByText(SYNTHETIC);

        const editBtn = screen
            .getAllByRole('button')
            .find((b) => b.querySelector('svg') && !b.textContent.trim());
        fireEvent.click(editBtn);

        fireEvent.change(await screen.findByPlaceholderText('10-digit mobile number'), {
            target: { value: '999' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

        expect(screen.queryByPlaceholderText('10-digit mobile number')).toBeNull();
        expect(await screen.findByText(SYNTHETIC)).toBeTruthy();
        expect(apiPatchMock).not.toHaveBeenCalled();
    });
});

describe('Government portal contact number — non-primary staff', () => {
    beforeEach(() => {
        mockUser = { username: 'staff_one', role: 'staff', constituency: 'Seat One', house: 'Lok Sabha' };
    });

    it('cannot edit and sees the workspace-lead message when nothing is on file', async () => {
        routeApiGet(null);
        await renderSettings();

        expect(await screen.findByText(/Ask the workspace lead to add the portal contact number/i)).toBeTruthy();
        expect(screen.queryByPlaceholderText('10-digit mobile number')).toBeNull();
        expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
    });

    it('sees an existing number but is given no edit control', async () => {
        routeApiGet(SYNTHETIC);
        await renderSettings();

        expect(await screen.findByText(SYNTHETIC)).toBeTruthy();
        expect(screen.queryByPlaceholderText('10-digit mobile number')).toBeNull();
        // No icon-only (pencil) button is rendered for non-primary staff.
        const iconOnly = screen
            .getAllByRole('button')
            .filter((b) => b.querySelector('svg') && !b.textContent.trim());
        expect(iconOnly.length).toBe(0);
    });
});
