'use client';

import { Button } from '@/components/ui/button';
import { STATUS_OPTIONS } from '@/components/briefcase/briefcase-shared';

export default function BriefcaseBulkActions({ selectedCount, onStatusChange, onAssign, onClear, staff }) {
    if (selectedCount === 0) {
        return null;
    }

    return (
        <div className="px-6 py-3 border-b bg-primary/5 flex items-center gap-4">
            <span className="text-sm font-medium">{selectedCount} selected</span>
            <select className="text-sm border rounded px-2 py-1" value="" onChange={(e) => { if (e.target.value) { onStatusChange(e.target.value); e.target.value = ''; } }}>
                <option value="">Bulk Status...</option>
                {STATUS_OPTIONS.map((status) => (
                    <option key={status.value} value={status.value}>{status.label}</option>
                ))}
            </select>
            <select className="text-sm border rounded px-2 py-1" value="" onChange={(e) => { if (e.target.value) { onAssign(e.target.value); e.target.value = ''; } }}>
                <option value="">Bulk Assign...</option>
                {staff.map((member) => (
                    <option key={member.username} value={member.username}>{member.display_name || member.username}</option>
                ))}
            </select>
            <Button variant="ghost" size="sm" onClick={onClear}>Clear</Button>
        </div>
    );
}
