'use client';

const C = {
    surface: '#FFFEFB',
    hair: '#E4DECB',
    hairSoft: '#D8D0BE',
    ink: '#211F19',
    muted: '#6C6858',
    activeBg: '#F7F2E7',
};

function pageWindow(page, totalPages) {
    // 1 … (p-1) p (p+1) … last  — collapse long ranges with ellipses
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
    const out = [1];
    const start = Math.max(2, page - 1);
    const end = Math.min(totalPages - 1, page + 1);
    if (start > 2) out.push('…');
    for (let i = start; i <= end; i += 1) out.push(i);
    if (end < totalPages - 1) out.push('…');
    out.push(totalPages);
    return out;
}

export default function BriefcasePagination({
    page,
    totalPages,
    totalCases,
    shown = 0,
    pageSize = 25,
    onPageChange,
    onPageSizeChange,
    onPrevious,
    onNext,
}) {
    const goto = (n) => {
        if (onPageChange) return onPageChange(Math.min(Math.max(1, n), totalPages || 1));
        if (n < page && onPrevious) return onPrevious();
        if (n > page && onNext) return onNext();
        return undefined;
    };

    const start = totalCases === 0 ? 0 : (page - 1) * pageSize + 1;
    const end = totalCases === 0 ? 0 : start + Math.max(0, shown) - 1;

    const pageBtn = (label, { active = false, disabled = false, onClick, key } = {}) => (
        <button
            key={key ?? label}
            type="button"
            disabled={disabled}
            onClick={onClick}
            style={{
                minWidth: 32, height: 32, padding: '0 6px',
                border: `1px solid ${active ? C.hairSoft : 'transparent'}`,
                borderRadius: 4,
                background: active ? C.activeBg : 'transparent',
                color: disabled ? '#C7BFAB' : active ? C.ink : C.muted,
                fontSize: 12, fontFamily: 'inherit',
                cursor: disabled ? 'default' : 'pointer',
            }}
        >
            {label}
        </button>
    );

    return (
        <div style={{
            minHeight: 58, padding: '10px 16px',
            display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', gap: 12,
            color: C.muted, fontSize: 11,
            background: C.surface, borderTop: `1px solid ${C.hair}`,
            fontFamily: '"Public Sans", system-ui, sans-serif',
        }}>
            <div>
                Showing {start}–{end} of {(totalCases || 0).toLocaleString()} cases
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'wrap', justifyContent: 'center' }}>
                {pageBtn('‹', { key: 'prev', disabled: page <= 1, onClick: () => goto(page - 1) })}
                {pageWindow(page, totalPages || 1).map((p, i) =>
                    p === '…'
                        ? <span key={`e${i}`} style={{ padding: '0 4px', color: '#B9B19D' }}>…</span>
                        : pageBtn(p, { key: `p${p}`, active: p === page, onClick: () => goto(p) }),
                )}
                {pageBtn('›', { key: 'next', disabled: page >= (totalPages || 1), onClick: () => goto(page + 1) })}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 10 }}>
                Rows per page
                <select
                    value={pageSize}
                    onChange={(e) => onPageSizeChange && onPageSizeChange(Number(e.target.value))}
                    style={{
                        border: `1px solid ${C.hair}`, borderRadius: 4, background: C.surface,
                        color: C.ink, fontSize: 12, fontFamily: 'inherit', padding: '4px 6px', outline: 'none',
                    }}
                >
                    {[25, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
            </div>
        </div>
    );
}
