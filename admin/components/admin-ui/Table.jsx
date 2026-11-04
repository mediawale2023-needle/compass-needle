'use client';

import Link from 'next/link';

/**
 * DataTable — semantic table in a focusable scroll region. Each cell carries
 * data-label so it can restyle into stacked rows on narrow screens.
 * columns = [{ key, header, align, render(row), width, hideBelow }].
 */
export function DataTable({ label, columns = [], rows = [], getRowKey = (row, index) => row.id ?? index, selectedKey, onRowSelect, empty }) {
    if (!rows.length && empty) return empty;
    return (
        <div className="nx-table-region" role="region" aria-label={label} tabIndex={0}>
            <table className="nx-table" data-stack="true">
                <thead>
                    <tr>
                        {columns.map((column) => (
                            <th key={column.key} scope="col" style={{ textAlign: column.align || 'left', width: column.width }} data-hide-below={column.hideBelow}>
                                {column.header}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row, index) => {
                        const key = getRowKey(row, index);
                        const selected = selectedKey !== undefined && key === selectedKey;
                        return (
                            <tr
                                key={key}
                                data-selected={selected ? 'true' : undefined}
                                aria-selected={onRowSelect ? selected : undefined}
                                onClick={onRowSelect ? () => onRowSelect(row) : undefined}
                                className={onRowSelect ? 'nx-row-selectable' : undefined}
                            >
                                {columns.map((column) => (
                                    <td key={column.key} data-label={typeof column.header === 'string' ? column.header : undefined} style={{ textAlign: column.align || 'left' }} data-hide-below={column.hideBelow}>
                                        {column.render ? column.render(row) : row[column.key]}
                                    </td>
                                ))}
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

/**
 * ListRow — the non-spreadsheet operational row (attention queue, case list,
 * failures). leading: tile/avatar; aside: impact column; actions: buttons.
 */
export function ListRow({ leading, title, badge, meta, aside, actions, tone, selected = false, onSelect, href }) {
    const content = (
        <>
            {leading && <span className="nx-row-leading">{leading}</span>}
            <span className="nx-row-main">
                <span className="nx-row-title">{title}{badge}</span>
                {meta && <span className="nx-row-meta">{meta}</span>}
            </span>
            {aside && <span className="nx-row-aside">{aside}</span>}
            {actions && <span className="nx-row-actions">{actions}</span>}
        </>
    );
    if (onSelect) {
        return (
            <button type="button" className="nx-row" data-tone={tone} data-selected={selected ? 'true' : undefined} aria-pressed={selected} onClick={onSelect}>
                {content}
            </button>
        );
    }
    if (href) {
        return <Link className="nx-row" href={href} data-tone={tone}>{content}</Link>;
    }
    return <div className="nx-row" data-tone={tone} data-selected={selected ? 'true' : undefined}>{content}</div>;
}
