import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import {
    GovernmentPortalHistoryPanel,
    ResolutionReviewCard,
    govtPollSuccessMessage,
} from '@/components/briefcase/BriefcaseCaseModal';

afterEach(cleanup);

const EVENTS = [
    { id: 5, occurred_at: '2026-09-19T10:30:00Z', event_type: 'resolution', status: 'resolved', to_display: 'Urban Improvement Trust', comment: 'Necessary action has been taken.', documents: [{ source_document_id: '7812' }] },
    { id: 4, occurred_at: '2026-09-12T16:15:00Z', event_type: 'department_remark', comment: 'Work has been completed.', documents: [] },
    { id: 3, occurred_at: '2026-09-04T09:00:00Z', event_type: 'department_remark', comment: 'Road-cutting permission is under process.', documents: [] },
    { id: 2, occurred_at: null, event_type: 'routing_update', from_display: 'Public Works Department', to_display: 'Urban Improvement Trust', documents: [] },
];

describe('Government Portal History', () => {
    it('does not render when no persisted events exist', () => {
        const { container } = render(<GovernmentPortalHistoryPanel history={{ availability: 'unavailable', events: [] }} />);
        expect(container).toBeEmptyDOMElement();
        expect(screen.queryByText('Government portal history')).not.toBeInTheDocument();
    });

    it('shows three newest events first and expands older updates accessibly', () => {
        render(<GovernmentPortalHistoryPanel history={{ availability: 'available', events: EVENTS }} />);
        expect(screen.getByRole('heading', { name: 'Government portal history' })).toBeVisible();
        expect(screen.getByText('Updates reported by the government portal')).toBeVisible();
        expect(screen.getByText('Necessary action has been taken.')).toBeVisible();
        expect(screen.getByText('Road-cutting permission is under process.')).toBeVisible();
        expect(screen.queryByText('Routing update')).not.toBeInTheDocument();
        expect(screen.getByText('Document listed on portal')).toBeVisible();

        const expand = screen.getByRole('button', { name: 'Show 1 older update' });
        expect(expand).toHaveAttribute('aria-expanded', 'false');
        expect(expand).toHaveStyle({ minHeight: '44px' });
        fireEvent.click(expand);
        expect(expand).toHaveAttribute('aria-expanded', 'true');
        expect(screen.getByText('Routing update')).toBeVisible();
        expect(screen.getByText('Date unavailable')).toBeVisible();
    });

    it('distinguishes meaningful comment updates from status changes', () => {
        expect(govtPollSuccessMessage({
            changed: true,
            status_changed: false,
            change_types: ['portal_history_event_added', 'government_remark_added'],
            govt_status: 'under_review',
        })).toBe('Government portal added a new remark.');
        expect(govtPollSuccessMessage({ changed: true, govt_status: 'resolved' })).toMatch(/^Status updated:/);
    });
});

describe('Resolution Review final government remark', () => {
    it('shows immutable portal wording and still requires an explicit decision', () => {
        render(<ResolutionReviewCard
            open
            followingUp={false}
            updating={false}
            data={{
                resolvedOn: '19 Sep 2026',
                department: 'Urban Improvement Trust',
                portal: 'Rajasthan Sampark',
                grievanceId: 'RJ/ONE/40',
                finalRemark: {
                    comment: '  Necessary action has been taken.  ',
                    occurredAt: '2026-09-19T10:30:00Z',
                    routing: 'Urban Improvement Trust',
                    documentCount: 1,
                },
            }}
            onOpen={() => {}}
            onCollapse={() => {}}
            onViewPortalDetail={() => {}}
            onMarkResolved={() => {}}
            onContinueFollowUp={() => {}}
        />);
        expect(screen.getByText('Government’s final remark')).toBeVisible();
        expect(screen.getByText(/Necessary action has been taken/)).toBeVisible();
        expect(screen.getByRole('button', { name: 'Accept & mark resolved' })).toBeVisible();
        expect(screen.getByRole('button', { name: 'Continue follow-up' })).toBeVisible();
    });
});
