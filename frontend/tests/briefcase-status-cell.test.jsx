import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import BriefcaseCasesTable from '@/components/briefcase/BriefcaseCasesTable';

// Minimal row factory — only the fields the STATUS cell + Needle pill read.
function makeCase(overrides = {}) {
    return {
        id: 1,
        raw_message: 'No water supply in Whitefield for three days now.',
        category: 'Infrastructure & Utilities',
        problem_domain: null,
        problem_subdomain: null,
        location: 'Whitefield',
        assembly: 'Mahadevapura',
        status: 'new',
        govt_status: null,
        govt_reference_number: null,
        govt_portal_name: null,
        govt_sync_state: null,
        govt_department: null,
        status_changed_at: null,
        resolved_at: null,
        thread_case_count: 1,
        created_at: '2026-08-01T09:00:00Z',
        ...overrides,
    };
}

function renderTable(cases) {
    return render(
        <BriefcaseCasesTable
            cases={cases}
            loading={false}
            search=""
            statusFilter="all_cases"
            categoryFilter=""
            selectedIds={new Set()}
            setSelectedIds={() => {}}
            onSelectCase={() => {}}
            onOpenContact={() => {}}
            onDeleteCase={() => {}}
        />,
    );
}

describe('Briefcase STATUS cell — government primary layer', () => {
    it('shows "Ready for government portal" ONLY from govt_status = pending_staff_submit', () => {
        renderTable([makeCase({ status: 'in_progress', govt_status: 'pending_staff_submit' })]);
        expect(screen.getByText('Ready for government portal')).toBeInTheDocument();
        expect(screen.getAllByText('NOT FILED').length).toBeGreaterThan(0);
    });

    it('does NOT derive "Ready for government portal" from cases.status = in_progress alone', () => {
        renderTable([makeCase({ status: 'in_progress', govt_status: null })]);
        expect(screen.queryByText('Ready for government portal')).toBeNull();
        expect(screen.getAllByText('NOT FILED').length).toBeGreaterThan(0);
    });

    it('maps cases.status = pending_review to "Review pending"', () => {
        renderTable([makeCase({ status: 'pending_review' })]);
        expect(screen.getByText('Review pending')).toBeInTheDocument();
        expect(screen.queryByText('Ready for government portal')).toBeNull();
    });

    it('maps cases.status = awaiting_location to "Location needed first"', () => {
        renderTable([makeCase({ status: 'awaiting_location' })]);
        expect(screen.getByText('Location needed first')).toBeInTheDocument();
        expect(screen.queryByText('Ready for government portal')).toBeNull();
    });

    it('shows REGISTERED WITH GOVT PORTAL with the portal name and #reference', () => {
        renderTable([makeCase({
            status: 'in_progress',
            govt_status: 'submitted',
            govt_reference_number: 'KAR-9001',
            govt_portal_name: 'Karnataka iPGRS',
        })]);
        expect(screen.getByText('REGISTERED WITH GOVT PORTAL')).toBeInTheDocument();
        expect(screen.getByText('Karnataka iPGRS')).toBeInTheDocument();
        expect(screen.getByText('#KAR-9001')).toBeInTheDocument();
    });

    it('shows SYNC ISSUE / Check required on a failed sync state', () => {
        renderTable([makeCase({
            status: 'in_progress',
            govt_status: 'submitted',
            govt_reference_number: 'KAR-9001',
            govt_sync_state: 'failed',
        })]);
        expect(screen.getByText('SYNC ISSUE')).toBeInTheDocument();
        expect(screen.getByText('Check required')).toBeInTheDocument();
    });
});

// The reference number used to be attached only inside the REGISTERED branch,
// so it disappeared the moment a case advanced to RESOLVED / REJECTED /
// DEPARTMENT ACTION / SYNC ISSUE — the states where staff most need it to
// chase the department.
describe('Briefcase STATUS cell — grievance reference number on filed cases', () => {
    it.each([
        ['RESOLVED', { govt_status: 'resolved', resolved_at: '2026-09-01T10:00:00Z' }],
        ['RESOLVED', { govt_status: 'disposed' }],
        ['REJECTED', { govt_status: 'rejected' }],
        ['DEPARTMENT ACTION', { govt_status: 'under_review', govt_department: 'PWD' }],
        ['DEPARTMENT ACTION', { govt_status: 'escalated' }],
        ['DEPARTMENT ACTION', { govt_status: 'forwarded' }],
    ])('shows #reference on a filed case at stage %s', (stage, overrides) => {
        renderTable([makeCase({
            status: 'in_progress',
            govt_reference_number: 'RAJ-4477',
            ...overrides,
        })]);
        expect(screen.getByText(stage)).toBeInTheDocument();
        expect(screen.getByText('#RAJ-4477')).toBeInTheDocument();
    });

    it('shows #reference alongside the supporting line rather than replacing it', () => {
        renderTable([makeCase({
            status: 'in_progress',
            govt_status: 'under_review',
            govt_department: 'Public Health Engineering',
            govt_reference_number: 'RAJ-4477',
        })]);
        expect(screen.getByText('Public Health Engineering')).toBeInTheDocument();
        expect(screen.getByText('#RAJ-4477')).toBeInTheDocument();
    });

    it('shows #reference on a sync-issue case so staff can still quote it', () => {
        renderTable([makeCase({
            status: 'in_progress',
            govt_status: 'submitted',
            govt_reference_number: 'KAR-9001',
            govt_sync_state: 'failed',
        })]);
        expect(screen.getByText('SYNC ISSUE')).toBeInTheDocument();
        expect(screen.getByText('#KAR-9001')).toBeInTheDocument();
    });

    it('renders the reference exactly once when the case is registered', () => {
        renderTable([makeCase({
            status: 'in_progress',
            govt_status: 'submitted',
            govt_reference_number: 'KAR-9001',
            govt_portal_name: 'Karnataka iPGRS',
        })]);
        expect(screen.getAllByText('#KAR-9001')).toHaveLength(1);
    });

    it('shows no reference line when the case is not filed with government', () => {
        // Note: the CASE / THREAD column renders its own "#<id>", so this
        // asserts on the government reference specifically.
        renderTable([makeCase({ status: 'new', govt_status: null, govt_reference_number: null })]);
        expect(screen.getAllByText('NOT FILED').length).toBeGreaterThan(0);
        expect(screen.queryByText(/^#[A-Z]{2,}-/)).toBeNull();
    });

    it('treats a bare reference number with no govt_status as filed', () => {
        renderTable([makeCase({ status: 'in_progress', govt_status: null, govt_reference_number: 'MH-77' })]);
        expect(screen.getByText('#MH-77')).toBeInTheDocument();
    });
});

describe('Briefcase STATUS cell — Needle secondary layer', () => {
    it('renders the Needle pill from the real cases.status', () => {
        renderTable([makeCase({ status: 'in_progress' })]);
        expect(screen.getByText('In Progress')).toBeInTheDocument();
    });

    it('keeps the Needle pill on the real cases.status even when government status is RESOLVED', () => {
        renderTable([makeCase({ status: 'in_progress', govt_status: 'resolved', resolved_at: '2026-08-20T00:00:00Z' })]);
        expect(screen.getByText('RESOLVED')).toBeInTheDocument();      // government layer
        expect(screen.getByText('In Progress')).toBeInTheDocument();   // Needle layer, unchanged
    });

    it('never renders a Needle "READY" pill', () => {
        renderTable([
            makeCase({ id: 1, status: 'in_progress', govt_status: 'pending_staff_submit' }),
            makeCase({ id: 2, status: 'pending_review' }),
            makeCase({ id: 3, status: 'new' }),
        ]);
        expect(screen.queryByText('READY')).toBeNull();
        expect(screen.queryByText('Ready')).toBeNull();
    });
});

describe('Briefcase STATUS cell — "Since" date', () => {
    it('renders "Since <date>" only when status_changed_at is present', () => {
        renderTable([makeCase({ status: 'in_progress', status_changed_at: '2026-08-15T10:00:00Z' })]);
        expect(screen.getByText(/^Since\s/)).toBeInTheDocument();
    });

    it('omits the "Since" line entirely when status_changed_at is null', () => {
        renderTable([makeCase({
            status: 'in_progress',
            status_changed_at: null,
            updated_at: '2026-08-25T10:00:00Z',
            created_at: '2026-08-01T09:00:00Z',
        })]);
        expect(screen.queryByText(/^Since\s/)).toBeNull();
    });
});
