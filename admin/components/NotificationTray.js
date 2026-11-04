'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useAdminSignals } from '@/lib/admin-signals';
import { alertDestination, severityFromAlert, sortAlertsBySeverity, SEVERITY_LABEL } from '@/lib/admin-data';
import { Bell } from '@/components/admin-ui/icons';

export default function NotificationTray() {
    const { alerts, status, refresh } = useAdminSignals();
    const [open, setOpen] = useState(false);
    const trayRef = useRef(null);
    const list = Array.isArray(alerts) ? sortAlertsBySeverity(alerts) : [];
    const hasUrgent = list.some((alert) => ['critical', 'warning'].includes(severityFromAlert(alert)));

    useEffect(() => {
        if (!open) return undefined;
        const onPointer = (event) => {
            if (trayRef.current && !trayRef.current.contains(event.target)) setOpen(false);
        };
        const onKey = (event) => { if (event.key === 'Escape') setOpen(false); };
        document.addEventListener('mousedown', onPointer);
        document.addEventListener('keydown', onKey);
        return () => {
            document.removeEventListener('mousedown', onPointer);
            document.removeEventListener('keydown', onKey);
        };
    }, [open]);

    const toggle = () => {
        setOpen((current) => !current);
        if (!open) refresh();
    };

    const label = list.length ? `Notifications, ${list.length} active` : 'Notifications';

    return (
        <div ref={trayRef} className="nx-popover-anchor">
            <button type="button" className="nx-icon-button" aria-label={label} aria-expanded={open} aria-haspopup="dialog" onClick={toggle}>
                <Bell size={18} strokeWidth={1.75} aria-hidden="true" />
                {list.length > 0 && <span className="nx-icon-badge" data-tone={hasUrgent ? 'critical' : 'review'} aria-hidden="true" />}
            </button>

            {open && (
                <div className="nx-popover nx-tray" role="dialog" aria-label="Alerts">
                    <div className="nx-popover-head">
                        <strong>Alerts</strong>
                        <span className="nx-muted">
                            {status === 'error' && !alerts ? 'Unavailable' : `${list.length} active`}
                        </span>
                    </div>
                    <div className="nx-tray-list">
                        {status === 'loading' && !alerts && <div className="nx-tray-empty">Checking…</div>}
                        {status === 'error' && !alerts && <div className="nx-tray-empty">Alerts could not be loaded.</div>}
                        {Array.isArray(alerts) && list.length === 0 && <div className="nx-tray-empty">No active alerts.</div>}
                        {list.map((alert, index) => {
                            const severity = severityFromAlert(alert);
                            return (
                                <Link key={`${alert.type}-${alert.tenant_id ?? 'p'}-${index}`} href={alertDestination(alert)} className="nx-tray-item" onClick={() => setOpen(false)}>
                                    <span className="nx-dot" data-tone={severity} aria-hidden="true" />
                                    <span className="nx-tray-copy">
                                        <strong>{alert.title}</strong>
                                        {alert.description && <small>{alert.description}</small>}
                                    </span>
                                    <span className="nx-badge" data-tone={severity}>{SEVERITY_LABEL[severity]}</span>
                                </Link>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}
