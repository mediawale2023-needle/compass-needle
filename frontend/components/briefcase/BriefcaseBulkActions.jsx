'use client';

import { STATUS_OPTIONS } from '@/components/briefcase/briefcase-shared';
import { gen2, gen2Fonts } from '@/lib/briefcase-tokens';

// Compact bulk-action bar. Only genuinely-wired actions are exposed:
// Assign owner, Set status, Delete (with confirmation, in the hook).
const C = { ...gen2, cream: gen2.bg };
const SANS = gen2Fonts.sans;
const MONO = gen2Fonts.mono;

export default function BriefcaseBulkActions({ selectedCount, onStatusChange, onAssign, onDelete, onClear, staff }) {
    if (selectedCount === 0) return null;

    const btn = {
        border: '1px solid rgba(243,238,226,0.34)',
        background: 'transparent',
        color: C.cream,
        padding: '5px 10px',
        fontSize: 11.5,
        fontWeight: 600,
        letterSpacing: '0.02em',
        cursor: 'pointer',
        fontFamily: SANS,
    };

    return (
        <div
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                flexWrap: 'wrap',
                padding: '8px 22px',
                background: C.greenDeep,
                color: C.cream,
                borderBottom: '1px solid #E4DECB',
            }}
        >
            <span
                style={{
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    minWidth: 20, height: 20, padding: '0 5px',
                    background: C.rust, color: C.cream,
                    fontFamily: MONO, fontSize: 11, fontWeight: 700,
                }}
            >
                {selectedCount}
            </span>
            <span style={{ fontSize: 12, fontWeight: 600 }}>cases selected</span>
            <span style={{ width: 1, height: 18, background: 'rgba(243,238,226,0.25)' }} />

            <select
                defaultValue=""
                onChange={(event) => {
                    if (event.target.value) {
                        onAssign(event.target.value);
                        event.target.value = '';
                    }
                }}
                style={btn}
            >
                <option value="">Assign owner ▾</option>
                {staff.map((member) => (
                    <option key={member.username} value={member.username}>{member.display_name || member.username}</option>
                ))}
            </select>

            <select
                defaultValue=""
                onChange={(event) => {
                    if (event.target.value) {
                        onStatusChange(event.target.value);
                        event.target.value = '';
                    }
                }}
                style={btn}
            >
                <option value="">Set status ▾</option>
                {STATUS_OPTIONS.map((status) => (
                    <option key={status.value} value={status.value}>{status.label}</option>
                ))}
            </select>

            <button style={btn} type="button" onClick={onDelete}>Delete</button>

            <div style={{ flex: 1 }} />
            <button
                onClick={onClear}
                style={{ ...btn, fontFamily: MONO, fontSize: 10, letterSpacing: '0.06em', textTransform: 'uppercase', padding: '4px 9px' }}
            >
                Clear
            </button>
        </div>
    );
}
