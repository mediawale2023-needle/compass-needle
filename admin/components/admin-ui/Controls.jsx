'use client';

import { useId } from 'react';
import { ChevronDown, Search, X } from 'lucide-react';

/** Segmented control. options = [{ value, label, count }]. */
export function SegmentedControl({ label, options = [], value, onChange }) {
    return (
        <div className="nx-seg" role="tablist" aria-label={label}>
            {options.map((option) => (
                <button
                    key={option.value}
                    type="button"
                    role="tab"
                    aria-selected={option.value === value}
                    className="nx-seg-option"
                    onClick={() => onChange?.(option.value)}
                >
                    {option.dot && <i data-tone={option.dot} aria-hidden="true" />}
                    {option.label}
                    {option.count !== undefined && option.count !== null && <span className="nx-seg-count">{option.count}</span>}
                </button>
            ))}
        </div>
    );
}

/** Compact filter chip; active chips show a clear (×) control. */
export function FilterChip({ label, active = false, onClick, onClear, hasMenu = true }) {
    return (
        <span className="nx-chip" data-active={active ? 'true' : undefined}>
            <button type="button" className="nx-chip-main" onClick={onClick} aria-haspopup={hasMenu ? 'listbox' : undefined}>
                {label}
                {hasMenu && !active && <ChevronDown size={14} strokeWidth={2} aria-hidden="true" />}
            </button>
            {active && onClear && (
                <button type="button" className="nx-chip-clear" aria-label={`Clear ${label}`} onClick={onClear}>
                    <X size={14} strokeWidth={2.2} aria-hidden="true" />
                </button>
            )}
        </span>
    );
}

export function SearchInput({ label, value, onChange, placeholder, width }) {
    return (
        <label className="nx-input-search" style={width ? { width } : undefined}>
            <Search size={15} strokeWidth={1.9} aria-hidden="true" />
            <input type="search" aria-label={label} value={value} placeholder={placeholder} onChange={(event) => onChange?.(event.target.value)} />
        </label>
    );
}

/** Field wrapper with label, required/optional marker, help and error text. */
export function Field({ label, required = false, optional = false, help, error, children, id }) {
    const autoId = useId();
    const fieldId = id || autoId;
    const helpId = `${fieldId}-help`;
    const child = typeof children === 'function'
        ? children({ id: fieldId, 'aria-describedby': help || error ? helpId : undefined, 'aria-invalid': error ? true : undefined })
        : children;
    return (
        <div className="nx-field" data-invalid={error ? 'true' : undefined}>
            <label htmlFor={fieldId} className="nx-label">
                {label}
                {required && <span className="nx-req" aria-hidden="true">*</span>}
                {optional && <span className="nx-tag">Optional</span>}
            </label>
            {child}
            {(error || help) && <div id={helpId} className={error ? 'nx-field-error' : 'nx-field-help'}>{error || help}</div>}
        </div>
    );
}

export function TextInput(props) {
    return <input className="nx-input" {...props} />;
}

export function Select({ options = [], placeholder, ...props }) {
    return (
        <span className="nx-select">
            <select className="nx-input" {...props}>
                {placeholder && <option value="">{placeholder}</option>}
                {options.map((option) => {
                    const value = typeof option === 'string' ? option : option.value;
                    const text = typeof option === 'string' ? option : option.label;
                    return <option key={value} value={value}>{text}</option>;
                })}
            </select>
            <ChevronDown size={14} strokeWidth={2} aria-hidden="true" />
        </span>
    );
}

/** Radio cards. options = [{ value, label, detail }]. */
export function RadioCards({ name, label, options = [], value, onChange, columns }) {
    const labelId = useId();
    return (
        <div className="nx-radio-cards" role="radiogroup" aria-labelledby={labelId} style={columns ? { '--nx-cols': columns } : undefined}>
            <span id={labelId} className="nx-sr-only">{label}</span>
            {options.map((option) => (
                <label key={option.value} className="nx-radio-card" data-checked={option.value === value ? 'true' : undefined}>
                    <input type="radio" name={name} value={option.value} checked={option.value === value} onChange={() => onChange?.(option.value)} />
                    <span>
                        <span className="nx-radio-title">{option.label}</span>
                        {option.detail && <span className="nx-radio-detail">{option.detail}</span>}
                    </span>
                </label>
            ))}
        </div>
    );
}

/** Inline callout. tone: warning | critical | info | ok. */
export function Callout({ tone = 'info', title, children, action }) {
    return (
        <div className="nx-callout" data-tone={tone} role={tone === 'critical' ? 'alert' : 'status'}>
            <div className="nx-callout-body">
                {title && <strong>{title} </strong>}
                {children}
            </div>
            {action && <div className="nx-callout-action">{action}</div>}
        </div>
    );
}
