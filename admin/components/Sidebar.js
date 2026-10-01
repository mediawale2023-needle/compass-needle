'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';

const Icon = ({ children }) => <span className="admin-nav-icon" aria-hidden="true">{children}</span>;
const icons = {
  overview: <Icon>⌂</Icon>, customers: <Icon>▣</Icon>, seats: <Icon>◇</Icon>,
  cases: <Icon>◫</Icon>, message: <Icon>◌</Icon>, ops: <Icon>◎</Icon>, admin: <Icon>◈</Icon>,
};

const NAV_GROUPS = [
  { label: null, items: [{ href: '/dashboard', label: 'Overview', sublabel: 'Command Centre', icon: icons.overview, exact: true }] },
  { label: 'Customers', items: [
    { href: '/dashboard/accounts', label: 'Accounts', sublabel: 'Manage political accounts', icon: icons.customers },
    { href: '/dashboard/accounts/new', label: 'Onboarding', sublabel: 'Setup & activation', icon: icons.customers },
  ]},
  { label: 'Constituencies', items: [
    { href: '/dashboard/seats', label: 'Seats & Geography', sublabel: 'Constituency data', icon: icons.seats },
    { href: '/dashboard/seat-maps', label: 'Seat Maps', sublabel: 'Boundaries & maps', icon: icons.seats },
  ]},
  { label: 'Case Operations', items: [
    { href: '/dashboard/cases-intelligence/explorer', label: 'Case Intelligence', sublabel: 'Explore & diagnose', icon: icons.cases },
    { href: '/dashboard/cases-intelligence/knowledge', label: 'Knowledge', sublabel: 'Content & sources', icon: icons.cases },
    { href: '/dashboard/cases-intelligence/engine', label: 'AI Engine', sublabel: 'Models & automation', icon: icons.cases },
    { href: '/dashboard/cases-intelligence/analytics', label: 'Usage Analytics', sublabel: 'Trends & insights', icon: icons.cases },
  ]},
  { label: 'Messaging & Sync', items: [
    { href: '/dashboard/system/whatsapp', label: 'WhatsApp Operations', sublabel: 'Delivery & queues', icon: icons.message },
    { href: '/dashboard/system/whatsapp-inbound', label: 'Inbound', sublabel: 'Incoming messages', icon: icons.message },
    { href: '/dashboard/system/parliament-sync', label: 'Parliament Sync', sublabel: 'Platform data sync', icon: icons.message },
  ]},
  { label: 'Platform Operations', items: [
    { href: '/dashboard/system/health', label: 'System Health', sublabel: 'Live status', icon: icons.ops },
    { href: '/dashboard/system/jobs', label: 'Jobs', sublabel: 'Background processes', icon: icons.ops },
  ]},
  { label: 'Administration', items: [
    { href: '/dashboard/staff-access/users', label: 'Staff & Access', sublabel: 'Users & permissions', icon: icons.admin },
    { href: '/dashboard/staff-access/audit', label: 'Audit Log', sublabel: 'Administrative history', icon: icons.admin },
    { href: '/dashboard/system/announcements', label: 'Announcements', sublabel: 'Operator communication', icon: icons.admin },
    { href: '/dashboard/system/settings', label: 'Settings', sublabel: 'Platform configuration', icon: icons.admin },
  ]},
];

export default function Sidebar({ open = false, onClose }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  return (
    <>
    {open && <button type="button" className="admin-sidebar-backdrop" aria-label="Close navigation" onClick={onClose} />}
    <aside className="admin-sidebar" data-open={open ? 'true' : 'false'}>
      <div className="admin-sidebar-brand">
        <Image src="/needle-logo-cream.svg" alt="Needle" width={58} height={34} priority />
        <div>
          <div className="admin-brand-name">Needle</div>
          <div className="admin-brand-label">Admin Console</div>
        </div>
      </div>
      <nav className="admin-sidebar-nav">
        {NAV_GROUPS.map((group, index) => (
          <section className="admin-nav-group" key={group.label || index}>
            {group.label && <div className="admin-nav-heading">{group.label}</div>}
            {group.items.map((item) => {
              const active = item.exact ? pathname === item.href : (pathname === item.href || pathname.startsWith(item.href + '/'));
              return (
                <Link href={item.href} key={item.href} className={`admin-nav-item ${active ? 'active' : ''}`} onClick={onClose}>
                  {item.icon}
                  <span className="admin-nav-copy">
                    <span className="admin-nav-label">{item.label}</span>
                    <span className="admin-nav-sublabel">{item.sublabel}</span>
                  </span>
                </Link>
              );
            })}
          </section>
        ))}
      </nav>
      <div className="admin-sidebar-footer">
        <div className="admin-user">
          <span className="admin-user-avatar">{(user?.display_name || user?.username || 'A').slice(0,1).toUpperCase()}</span>
          <span className="admin-user-copy"><strong>{user?.display_name || user?.username || 'Administrator'}</strong><small>Platform Admin</small></span>
        </div>
        <button onClick={logout} className="admin-signout">Sign out</button>
      </div>
    </aside>
    </>
  );
}
