'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { initials } from '@/lib/partnerTheme';
import { Icon, PartnerChromeContext } from './ui';

const NAV = [
    { href: '/partner/dashboard', label: 'Overview', icon: 'home', match: (p) => p === '/partner/dashboard' },
    { href: '/partner/dashboard/clients', label: 'Clients', icon: 'clients', match: (p) => p.startsWith('/partner/dashboard/clients') },
    { href: '/partner/dashboard/reports', label: 'Reports', icon: 'report', match: (p) => p.startsWith('/partner/dashboard/reports') },
];
const ORG_NAV = [
    { href: '/partner/dashboard/settings', label: 'Settings', icon: 'settings', match: (p) => p.startsWith('/partner/dashboard/settings') },
];

/** Session expiry from the token's own `exp` claim (display only; the server remains the authority). */
function sessionEndsAt(token) {
    try {
        const payload = JSON.parse(atob(String(token).split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
        if (!payload.exp) return null;
        return new Date(payload.exp * 1000).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
    } catch {
        return null;
    }
}

export function BrandMark({ partner, size = 34 }) {
    if (partner?.brand_logo_url) {
        // eslint-disable-next-line @next/next/no-img-element
        return <img src={partner.brand_logo_url} alt="" style={{ height: size }} />;
    }
    return <span className="pd-mark" style={{ width: size, height: size }} aria-hidden="true">{initials(partner?.brand_name)}</span>;
}

export default function PartnerShell({ partner, me, token, onSignOut, children }) {
    const pathname = usePathname() || '';
    const [crumbs, setCrumbs] = useState([]);
    const [drawer, setDrawer] = useState(false);
    const [menu, setMenu] = useState(false);
    const menuRef = useRef(null);
    const chrome = useMemo(() => ({ setCrumbs }), []);
    const brandName = partner?.brand_name || 'Partner workspace';
    const who = me?.display_name || me?.email || 'Signed in';

    useEffect(() => { setDrawer(false); setMenu(false); }, [pathname]);

    // Partner identity in the browser tab, so clients never see the platform's name there.
    useEffect(() => {
        const page = crumbs.length ? crumbs[crumbs.length - 1].label : 'Partner workspace';
        const wanted = `${page} · ${brandName}`;
        document.title = wanted;
        // Next applies the app-wide metadata title after hydration; keep the partner's title in place.
        const observer = new MutationObserver(() => { if (document.title !== wanted) document.title = wanted; });
        observer.observe(document.head, { subtree: true, childList: true, characterData: true });
        return () => observer.disconnect();
    }, [crumbs, brandName]);
    useEffect(() => {
        if (!partner?.brand_logo_url) return;
        let link = document.querySelector('link[data-partner-icon]');
        if (!link) {
            link = document.createElement('link');
            link.rel = 'icon';
            link.setAttribute('data-partner-icon', '');
            document.head.appendChild(link);
        }
        link.href = partner.brand_logo_url;
    }, [partner?.brand_logo_url]);

    useEffect(() => {
        if (!menu) return undefined;
        const close = (e) => { if (menuRef.current && !menuRef.current.contains(e.target)) setMenu(false); };
        const esc = (e) => { if (e.key === 'Escape') setMenu(false); };
        document.addEventListener('mousedown', close);
        document.addEventListener('keydown', esc);
        return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc); };
    }, [menu]);

    const ends = sessionEndsAt(token);
    const navLink = (n) => {
        const on = n.match(pathname);
        return (
            <Link key={n.href} href={n.href} className={on ? 'on' : ''} aria-current={on ? 'page' : undefined} title={n.label}>
                <Icon name={n.icon} /><span>{n.label}</span>
            </Link>
        );
    };

    return (
        <PartnerChromeContext.Provider value={chrome}>
            <div className={`pd-app ${drawer ? 'pd-drawer' : ''}`}>
                <div className="pd-scrim" onClick={() => setDrawer(false)} aria-hidden="true" />
                <aside className="pd-side" aria-label="Main navigation">
                    <div className="pd-brand">
                        <BrandMark partner={partner} />
                        <div className="pd-wm"><div className="pd-wm-name">{brandName}</div><div className="pd-wm-sub">Partner workspace</div></div>
                    </div>
                    <nav className="pd-nav">
                        <div className="pd-navlabel">Portfolio</div>
                        {NAV.map(navLink)}
                        <div className="pd-navlabel">Organisation</div>
                        {ORG_NAV.map(navLink)}
                    </nav>
                    <div className="pd-sidefoot">
                        <div className="pd-me">
                            <span className="pd-avatar" aria-hidden="true">{initials(who)}</span>
                            <span className="who"><div className="pd-me-name">{who}</div><div className="pd-me-role">{brandName}</div></span>
                        </div>
                        {partner?.show_powered_by ? <div className="pd-powered">Powered by Needle</div> : null}
                    </div>
                </aside>
                <div className="pd-main">
                    <header className="pd-top">
                        <button type="button" className="pd-iconbtn pd-menubtn" onClick={() => setDrawer(true)} aria-label="Open navigation"><Icon name="menu" /></button>
                        <span className="pd-mbrand"><BrandMark partner={partner} size={26} /></span>
                        <nav className="pd-crumbs" aria-label="Breadcrumb">
                            {crumbs.map((c, i) => (i < crumbs.length - 1 ? (
                                <span key={c.label} className="hide-m" style={{ display: 'inline-flex', gap: 8 }}>
                                    {c.href ? <Link href={c.href}>{c.label}</Link> : <span>{c.label}</span>}<span aria-hidden="true">/</span>
                                </span>
                            ) : <span key={c.label} className="cur" aria-current="page">{c.label}</span>))}
                        </nav>
                        <span className="pd-grow" />
                        <div className="pd-dd" ref={menuRef}>
                            <button type="button" className="pd-iconbtn" onClick={() => setMenu((m) => !m)} aria-haspopup="menu" aria-expanded={menu} aria-label="Account menu">
                                <span className="pd-avatar" style={{ width: 28, height: 28, fontSize: 11 }}>{initials(who)}</span>
                            </button>
                            {menu ? (
                                <div className="pd-pop" role="menu">
                                    <div className="hd">
                                        <div style={{ fontWeight: 600 }}>{me?.display_name || brandName}</div>
                                        {me?.email ? <div className="muted" style={{ fontSize: 12 }}>{me.email}</div> : null}
                                    </div>
                                    <Link className="item" role="menuitem" href="/partner/dashboard/settings"><Icon name="settings" size={16} /> Organisation settings</Link>
                                    {ends ? <div className="foot"><Icon name="clock" size={13} /> Session ends at {ends}</div> : null}
                                    <button type="button" className="item" role="menuitem" onClick={onSignOut}><Icon name="out" size={16} /> Sign out</button>
                                </div>
                            ) : null}
                        </div>
                    </header>
                    <main className="pd-content">{children}</main>
                </div>
            </div>
        </PartnerChromeContext.Provider>
    );
}
