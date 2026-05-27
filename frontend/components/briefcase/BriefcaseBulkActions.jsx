'use client';

import { briefcasePalette as P, BriefcaseIcon, STATUS_OPTIONS } from '@/components/briefcase/briefcase-shared';

export default function BriefcaseBulkActions({ selectedCount, onStatusChange, onAssign, onClear, staff }) {
    if (selectedCount === 0) {
        return null;
    }

    const buttonStyle = {
        background: 'transparent',
        border: '1px solid rgba(245,239,224,0.3)',
        color: '#F5EFE0',
        padding: '5px 10px',
        fontSize: 11.5,
        fontWeight: 600,
        letterSpacing: '0.02em',
        cursor: 'pointer',
        fontFamily: 'inherit',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
    };

    return (
        <div
            style={{
                padding: '10px 22px',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                flexWrap: 'wrap',
                background: P.greenDeep,
                color: '#F5EFE0',
                borderBottom: `1px solid ${P.hair}`,
            }}
        >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, fontWeight: 600 }}>
                <span
                    style={{
                        width: 18,
                        height: 18,
                        background: P.saffron,
                        color: P.greenDeep,
                        fontFamily: '"JetBrains Mono", monospace',
                        fontSize: 10,
                        fontWeight: 700,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}
                >
                    {selectedCount}
                </span>
                cases selected
            </div>
            <span style={{ width: 1, height: 18, background: 'rgba(245,239,224,0.2)' }} />

            <select
                defaultValue=""
                onChange={(event) => {
                    if (event.target.value) {
                        onAssign(event.target.value);
                        event.target.value = '';
                    }
                }}
                style={{ ...buttonStyle, background: P.saffron, border: 'none' }}
            >
                <option value="">Assign owner</option>
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
                style={buttonStyle}
            >
                <option value="">Set status</option>
                {STATUS_OPTIONS.map((status) => (
                    <option key={status.value} value={status.value}>{status.label}</option>
                ))}
            </select>

            <button style={buttonStyle} type="button">
                <BriefcaseIcon name="briefcase" size={12} color="#F5EFE0" /> Categorise
            </button>
            <button style={buttonStyle} type="button">
                <BriefcaseIcon name="drafter" size={12} color="#F5EFE0" /> Add to letter draft
            </button>
            <button style={buttonStyle} type="button">
                <BriefcaseIcon name="cluster" size={12} color="#F5EFE0" /> Group as cluster
            </button>

            <div style={{ flex: 1 }} />
            <button
                onClick={onClear}
                style={{
                    background: 'transparent',
                    border: '1px solid rgba(245,239,224,0.3)',
                    color: '#F5EFE0',
                    padding: '5px 9px',
                    fontSize: 11,
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                }}
            >
                <BriefcaseIcon name="x" size={11} color="#F5EFE0" /> Clear
            </button>
        </div>
    );
}
