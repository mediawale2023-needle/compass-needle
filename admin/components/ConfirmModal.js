'use client';
import { useState, useEffect, useRef } from 'react';

export default function ConfirmModal({ 
    title, 
    description, 
    confirmLabel = 'Confirm', 
    cancelLabel = 'Cancel',
    variant = 'danger', // 'danger' | 'warning'
    requireTypedConfirmation = '', // text user must type to confirm
    onConfirm, 
    onCancel 
}) {
    const [typed, setTyped] = useState('');
    const inputRef = useRef(null);

    useEffect(() => {
        if (requireTypedConfirmation && inputRef.current) {
            inputRef.current.focus();
        }
    }, [requireTypedConfirmation]);

    const canConfirm = requireTypedConfirmation 
        ? typed.trim().toLowerCase() === requireTypedConfirmation.toLowerCase()
        : true;

    const confirmColor = variant === 'danger' 
        ? 'linear-gradient(135deg, #dc2626, #ef4444)'
        : 'linear-gradient(135deg, #d97706, #f59e0b)';
    
    const confirmShadow = variant === 'danger'
        ? '0 4px 12px rgba(220, 38, 38, 0.25)'
        : '0 4px 12px rgba(217, 119, 6, 0.25)';

    return (
        <div className="modal-overlay" onClick={onCancel}>
            <div className="modal-card" onClick={e => e.stopPropagation()} style={{ maxWidth: 420 }}>
                {/* Icon */}
                <div style={{ 
                    display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 
                }}>
                    <div style={{
                        width: 40, height: 40, borderRadius: 10,
                        background: variant === 'danger' ? '#fff1f2' : '#fffbeb',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        flexShrink: 0,
                    }}>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" 
                            stroke={variant === 'danger' ? '#dc2626' : '#d97706'} 
                            strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                            <line x1="12" y1="9" x2="12" y2="13"/>
                            <line x1="12" y1="17" x2="12.01" y2="17"/>
                        </svg>
                    </div>
                    <div>
                        <h3 style={{ margin: 0, fontSize: '0.95rem' }}>{title}</h3>
                    </div>
                </div>

                {/* Description */}
                <p style={{ 
                    color: '#6b7f76', fontSize: '0.84rem', lineHeight: 1.6,
                    margin: '0 0 1rem', padding: '0 0 0 52px'
                }}>
                    {description}
                </p>

                {/* Typed confirmation */}
                {requireTypedConfirmation && (
                    <div style={{ margin: '0 0 1rem', padding: '0 0 0 52px' }}>
                        <label style={{ 
                            display: 'block', fontSize: '0.75rem', fontWeight: 600,
                            color: '#4a635a', marginBottom: 6 
                        }}>
                            Type <strong style={{ color: variant === 'danger' ? '#dc2626' : '#d97706' }}>
                                {requireTypedConfirmation}
                            </strong> to confirm
                        </label>
                        <input
                            ref={inputRef}
                            className="form-input"
                            value={typed}
                            onChange={e => setTyped(e.target.value)}
                            placeholder={requireTypedConfirmation}
                            style={{ fontSize: '0.84rem' }}
                        />
                    </div>
                )}

                {/* Actions */}
                <div className="modal-footer" style={{ paddingLeft: 52 }}>
                    <button className="btn-secondary" onClick={onCancel}>
                        {cancelLabel}
                    </button>
                    <button 
                        onClick={onConfirm}
                        disabled={!canConfirm}
                        style={{
                            background: confirmColor,
                            color: 'white',
                            border: 'none',
                            borderRadius: 'var(--radius-md)',
                            padding: '9px 20px',
                            fontWeight: 600,
                            fontSize: '0.84rem',
                            cursor: canConfirm ? 'pointer' : 'not-allowed',
                            fontFamily: 'inherit',
                            opacity: canConfirm ? 1 : 0.5,
                            transition: 'all 0.15s ease',
                            flex: 1,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                        }}
                        onMouseEnter={e => { if (canConfirm) e.currentTarget.style.boxShadow = confirmShadow; }}
                        onMouseLeave={e => { e.currentTarget.style.boxShadow = 'none'; }}
                    >
                        {confirmLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}
