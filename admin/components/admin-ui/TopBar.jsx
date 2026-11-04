'use client';

import { Fragment, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { breadcrumbFor } from '@/lib/admin-nav';
import { initialsFor } from '@/lib/admin-data';
import NotificationTray from '@/components/NotificationTray';
import CommandSearch from './CommandSearch';
import { ChevronDown, ChevronRight, LogOut, Menu } from './icons';

function Breadcrumb({ pathname }) {
    const trail = breadcrumbFor(pathname);
    return (
        <nav className="nx-breadcrumb" aria-label="Breadcrumb">
            <ol>
                {trail.map((crumb, index) => {
                    const last = index === trail.length - 1;
                    return (
                        <Fragment key={`${crumb.label}-${index}`}>
                            {index > 0 && <li aria-hidden="true" className="nx-crumb-sep"><ChevronRight size={14} strokeWidth={2} /></li>}
                            <li className={last ? 'nx-crumb nx-crumb-current' : 'nx-crumb'} aria-current={last ? 'page' : undefined}>
                                {crumb.href && !last ? <Link href={crumb.href}>{crumb.label}</Link> : crumb.label}
                            </li>
                        </Fragment>
                    );
                })}
            </ol>
        </nav>
    );
}

function UserMenu() {
    const { user, logout } = useAuth();
    const [open, setOpen] = useState(false);
    const ref = useRef(null);
    const name = user?.display_name || user?.username || 'Administrator';

    useEffect(() => {
        if (!open) return undefined;
        const onPointer = (event) => { if (ref.current && !ref.current.contains(event.target)) setOpen(false); };
        const onKey = (event) => { if (event.key === 'Escape') setOpen(false); };
        document.addEventListener('mousedown', onPointer);
        document.addEventListener('keydown', onKey);
        return () => {
            document.removeEventListener('mousedown', onPointer);
            document.removeEventListener('keydown', onKey);
        };
    }, [open]);

    return (
        <div className="nx-popover-anchor" ref={ref}>
            <button type="button" className="nx-user-button" aria-haspopup="menu" aria-expanded={open} aria-label={`Account menu for ${name}`} onClick={() => setOpen((v) => !v)}>
                <span className="nx-avatar nx-avatar-md" data-tint="forest" aria-hidden="true">{initialsFor(name)}</span>
                <span className="nx-user-copy">
                    <strong>{name}</strong>
                    <small>Platform admin</small>
                </span>
                <ChevronDown className="nx-user-caret" size={14} strokeWidth={2} aria-hidden="true" />
            </button>
            {open && (
                <div className="nx-popover nx-menu" role="menu" aria-label="Account">
                    <div className="nx-menu-head">
                        <strong>{name}</strong>
                        {user?.username && <small>{user.username}</small>}
                    </div>
                    <button type="button" role="menuitem" className="nx-menu-item" onClick={() => { setOpen(false); logout(); }}>
                        <LogOut size={16} strokeWidth={1.75} aria-hidden="true" />
                        Sign out
                    </button>
                </div>
            )}
        </div>
    );
}

export default function TopBar({ onOpenNavigation, navigationOpen = false }) {
    const pathname = usePathname();
    return (
        <header className="nx-topbar">
            <button
                type="button"
                className="nx-icon-button nx-menu-button"
                aria-label="Open navigation"
                aria-expanded={navigationOpen}
                onClick={onOpenNavigation}
            >
                <Menu size={18} strokeWidth={1.9} aria-hidden="true" />
            </button>
            <Breadcrumb pathname={pathname} />
            <CommandSearch />
            <div className="nx-topbar-actions">
                <NotificationTray />
                <span className="nx-topbar-divider" aria-hidden="true" />
                <UserMenu />
            </div>
        </header>
    );
}
