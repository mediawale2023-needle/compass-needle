'use client';

export default function BriefcaseNewCasesNotice({ onRefresh }) {
    return (
        <div
            className="flex items-center justify-between gap-3 px-4 py-2 rounded-lg text-sm font-medium mb-2"
            style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', color: '#065f46' }}
        >
            <span>New cases arrived since last refresh.</span>
            <button className="text-xs underline" onClick={onRefresh}>
                Refresh now
            </button>
        </div>
    );
}
