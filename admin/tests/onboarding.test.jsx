import React from 'react';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { vi } from 'vitest';
import {
    applyRole, buildCreatePayload, buildLaunchChecklist, formReadiness, INITIAL_ACCOUNT_FORM, launchSummary, roleValue,
    validateForCreate, validateStep,
} from '@/lib/admin-data';

const { apiGetMock, apiPostMock, pushMock } = vi.hoisted(() => ({ apiGetMock: vi.fn(), apiPostMock: vi.fn(), pushMock: vi.fn() }));
vi.mock('@/lib/api', () => ({ apiGet: (p) => apiGetMock(p), apiPost: (p, b) => apiPostMock(p, b) }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: pushMock }) }));
vi.mock('next/link', () => ({ default: ({ href, children, ...props }) => <a href={href} {...props}>{children}</a> }));

import CreateAccountPage from '@/components/admin-domains/accounts/CreateAccountPage';

describe('onboarding rules', () => {
    it('keeps the PR #146 step validation exactly', () => {
        expect(validateStep(INITIAL_ACCOUNT_FORM, 1)).toBe('Name and State are required before continuing');
        expect(validateStep({ ...INITIAL_ACCOUNT_FORM, name: 'A', state: 'K' }, 1)).toBe('');
        expect(validateStep(INITIAL_ACCOUNT_FORM, 2)).toBe('Username and Password are required before continuing');
        expect(validateStep(INITIAL_ACCOUNT_FORM, 3)).toBe('');
        expect(validateForCreate({ ...INITIAL_ACCOUNT_FORM, name: 'A', state: 'K', username: 'u' })).toBe('Name, Username, Password and State are required');
    });

    it('builds the same POST payload as before', () => {
        const form = { ...INITIAL_ACCOUNT_FORM, name: 'Shri A', state: 'Karnataka', username: 'a', password: 'p', languages: 'English, Kannada ,', key_facts: 'one\n\n two ', alt_names: 'Belagavi, Belgaum', account_stage: 'aspirant' };
        expect(buildCreatePayload(form)).toEqual({
            name: 'Shri A', username: 'a', password: 'p', tenant_type: 'aspirant', account_stage: 'aspirant', seat_type: 'mp',
            constituency: 'India', whatsapp_number: '', house: 'Lok Sabha', display_name: 'Shri A', state: 'Karnataka', party: 'Independent',
            languages: ['English', 'Kannada'], key_facts: ['one', 'two'], alt_names: ['Belagavi', 'Belgaum'],
        });
        expect(buildCreatePayload({ ...form, languages: '' }).languages).toEqual(['English', 'Hindi']);
    });

    it('maps role cards onto seat_type and house', () => {
        expect(roleValue(INITIAL_ACCOUNT_FORM)).toBe('mp-ls');
        expect(applyRole(INITIAL_ACCOUNT_FORM, 'mla')).toMatchObject({ seat_type: 'mla', house: 'Vidhan Sabha' });
        expect(applyRole(INITIAL_ACCOUNT_FORM, 'mp-rs')).toMatchObject({ seat_type: 'mp', house: 'Rajya Sabha' });
    });

    it('reports readiness from form state only, never post-creation checks as done', () => {
        const items = formReadiness({ ...INITIAL_ACCOUNT_FORM, name: 'A' });
        expect(items.find((i) => i.key === 'identity').state).toBe('progress');
        expect(items.find((i) => i.key === 'access').state).toBe('todo');
        for (const key of ['geography', 'staff']) expect(items.find((i) => i.key === key).state).toBe('optional');
        expect(JSON.stringify(items)).not.toMatch(/blocked|draft saved|another draft|token/i);
    });

    it('computes launch blockers from real tenant data', () => {
        const checklist = buildLaunchChecklist(7, { profile: { mp_name: 'A', constituency: 'B', state: 'K', house: 'Lok Sabha', key_facts: ['x'], whatsapp_number: '+91', phone_number_id: '' }, staff: [{ is_active: true }] }, {}, { assemblies: { X: ['a'] } });
        const summary = launchSummary(checklist, {});
        expect(summary.blockers.map((b) => b.key)).toEqual(['whatsapp', 'test_sent']);
        expect(summary).toMatchObject({ completed: 4, required: 6, canGoLive: false, isLive: false });
    });
});

describe('Create account flow', () => {
    beforeEach(() => {
        vi.useRealTimers();
        apiGetMock.mockReset();
        apiPostMock.mockReset();
        pushMock.mockReset();
        apiGetMock.mockResolvedValue({ constituencies: ['Bangalore North', 'Mumbai South'] });
    });

    const fill = (label, value) => fireEvent.change(screen.getByLabelText(label, { exact: false }), { target: { value } });

    it('guides through four stages, blocks invalid steps and creates with the real payload', async () => {
        apiPostMock.mockResolvedValue({ tenant_id: 7 });
        render(<CreateAccountPage />);

        expect(screen.getByRole('heading', { name: 'Identity' })).toBeInTheDocument();
        expect(screen.queryByText(/draft saved|another draft/i)).not.toBeInTheDocument();
        expect(screen.queryByText(/Former/)).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: /Continue to Seat & Access/ }));
        expect(screen.getByText('Name and State are required before continuing')).toBeInTheDocument();

        fill('MP full name', 'Shri Jagdish Shettar');
        fill('State', 'Karnataka');
        fireEvent.click(screen.getByRole('radio', { name: /MLA/ }));
        fireEvent.click(screen.getByRole('radio', { name: /MP\s*Lok Sabha/ }));
        fireEvent.click(screen.getByRole('button', { name: /Continue to Seat & Access/ }));

        expect(screen.getByRole('heading', { name: 'Seat & Access' })).toBeInTheDocument();
        const constituency = await screen.findByLabelText('Parliamentary constituency', { exact: false });
        await within(constituency).findByRole('option', { name: 'Bangalore North' });
        fireEvent.change(constituency, { target: { value: 'Bangalore North' } });
        fill('Username', 'j_shettar');
        fill('Temporary password', 'ValidPass1!');
        fireEvent.click(screen.getByRole('button', { name: /Continue to Configure/ }));

        expect(screen.getByRole('heading', { name: 'Configure' })).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: /Continue to Review & Create/ }));

        expect(screen.getByRole('heading', { name: 'Review & Create' })).toBeInTheDocument();
        expect(within(screen.getByRole('region', { name: 'Identity' })).getByText('Shri Jagdish Shettar')).toBeInTheDocument();
        expect(within(screen.getByRole('region', { name: 'Seat & Access' })).getByText('Bangalore North')).toBeInTheDocument();

        vi.useFakeTimers();
        await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Create account and continue setup' })); });
        expect(apiPostMock).toHaveBeenCalledWith('/api/admin/mps', expect.objectContaining({
            name: 'Shri Jagdish Shettar', username: 'j_shettar', constituency: 'Bangalore North', state: 'Karnataka',
            account_stage: 'elected', seat_type: 'mp', house: 'Lok Sabha',
        }));
        expect(screen.getByText(/Created Shri Jagdish Shettar/)).toBeInTheDocument();
        await act(async () => { vi.advanceTimersByTime(1600); });
        expect(pushMock).toHaveBeenCalledWith('/dashboard/mps/7/setup');
        vi.useRealTimers();
    });

    it('lets operators return to a completed step from the stepper', () => {
        render(<CreateAccountPage />);
        fill('MP full name', 'A');
        fill('State', 'K');
        fireEvent.click(screen.getByRole('button', { name: /Continue to Seat & Access/ }));
        fireEvent.click(screen.getByRole('button', { name: 'Back to Identity (complete)' }));
        expect(screen.getByRole('heading', { name: 'Identity' })).toBeInTheDocument();
        expect(screen.getByLabelText('MP full name', { exact: false })).toHaveValue('A');
    });

    it('surfaces creation errors without leaving the review', async () => {
        apiPostMock.mockRejectedValue(new Error('Username already exists'));
        render(<CreateAccountPage />);
        fill('MP full name', 'A'); fill('State', 'K');
        fireEvent.click(screen.getByRole('button', { name: /Continue to Seat & Access/ }));
        fill('Username', 'u'); fill('Temporary password', 'p');
        fireEvent.click(screen.getByRole('button', { name: /Continue to Configure/ }));
        fireEvent.click(screen.getByRole('button', { name: /Continue to Review & Create/ }));
        await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Create account and continue setup' })); });
        expect(screen.getByText('Username already exists')).toBeInTheDocument();
        expect(pushMock).not.toHaveBeenCalled();
    });

    it('never creates the account when arriving at the review step', async () => {
        render(<CreateAccountPage />);
        fill('MP full name', 'A'); fill('State', 'K');
        fireEvent.click(screen.getByRole('button', { name: /Continue to Seat & Access/ }));
        fill('Username', 'u'); fill('Temporary password', 'p');
        fireEvent.click(screen.getByRole('button', { name: /Continue to Configure/ }));
        const toReview = screen.getByRole('button', { name: /Continue to Review & Create/ });
        await act(async () => { fireEvent.click(toReview); });
        expect(screen.getByRole('heading', { name: 'Review & Create' })).toBeInTheDocument();
        expect(toReview).not.toBeInTheDocument();
        expect(apiPostMock).not.toHaveBeenCalled();
    });
});
