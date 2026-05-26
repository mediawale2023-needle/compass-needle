'use client';

import { Badge } from '@/components/ui/badge';

export const TABS = [
    { key: 'All', label: 'All Cases' },
    { key: 'new', label: 'New' },
    { key: 'awaiting_location', label: 'Needs Location' },
    { key: 'pending_review', label: 'Needs Review' },
    { key: 'in_progress', label: 'In Progress' },
    { key: 'resolved', label: 'Resolved' },
    { key: 'escalated', label: 'Escalated' },
    { key: 'other', label: 'Other' },
    { key: 'clusters', label: 'Related Clusters' },
    { key: 'deleted', label: 'Deleted' },
];

export const STATUS_OPTIONS = [
    { value: 'new', label: 'New', className: 'bg-blue-100 text-blue-700' },
    { value: 'awaiting_location', label: 'Needs Location', className: 'bg-orange-100 text-orange-700' },
    { value: 'pending_review', label: 'Needs Review', className: 'bg-purple-100 text-purple-700' },
    { value: 'in_progress', label: 'In Progress', className: 'bg-amber-100 text-amber-700' },
    { value: 'resolved', label: 'Resolved', className: 'bg-green-100 text-green-700' },
    { value: 'escalated', label: 'Escalated', className: 'bg-red-100 text-red-700' },
    { value: 'closed', label: 'Closed', className: 'bg-slate-100 text-slate-600' },
    { value: 'irrelevant', label: 'Irrelevant', className: 'bg-slate-100 text-slate-500' },
];

export const OTHER_CATEGORIES = ['Request', 'Greetings', 'Spam', 'Spam (Offensive)'];
export const OTHER_STATUSES = ['offensive', 'irrelevant'];

export function getStatusBadge(status) {
    const option = STATUS_OPTIONS.find((item) => item.value === (status || '').toLowerCase());
    if (option) {
        return (
            <Badge variant="secondary" className={option.className}>
                {option.label}
            </Badge>
        );
    }
    return <Badge variant="secondary">{status}</Badge>;
}
