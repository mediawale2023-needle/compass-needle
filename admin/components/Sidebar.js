'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';

const I=({children})=><span className="ref-nav-icon" aria-hidden="true">{children}</span>;
const groups=[
 {items:[['/dashboard','⌂','Overview','Command Centre',true]]},
 {label:'Customers',items:[['/dashboard/accounts','▣','Accounts','Manage political accounts'],['/dashboard/accounts/new','⇥','Onboarding','Setup & activation']]},
 {label:'Constituencies',items:[['/dashboard/seats','⊙','Seats & Geography','Constituency data'],['/dashboard/seat-maps','▧','Seat Maps','Boundaries & maps']]},
 {label:'Case Operations',items:[['/dashboard/cases-intelligence/explorer','♙','Case Intelligence','Explore & diagnose'],['/dashboard/cases-intelligence/knowledge','▢','Knowledge','Content & sources'],['/dashboard/cases-intelligence/engine','⚙','AI Engine','Models & automation'],['/dashboard/cases-intelligence/analytics','▥','Usage Analytics','Trends & insights']]},
 {label:'Messaging & Sync',items:[['/dashboard/system/whatsapp','◉','WhatsApp Operations','Delivery & queues'],['/dashboard/system/whatsapp-inbound','▱','Inbound','Incoming messages'],['/dashboard/system/parliament-sync','♜','Parliament Sync','Parliament data sync']]},
 {label:'Platform Operations',items:[['/dashboard/system/health','◈','System Health','Live status'],['/dashboard/system/jobs','▧','Jobs','Background processes'],['/dashboard/staff-access/audit','▤','Operational Logs','Events & audit']]},
 {label:'Administration',items:[['/dashboard/staff-access/users','♙','Staff & Access','Users & permissions'],['/dashboard/system/announcements','◌','Announcements','Operator communication'],['/dashboard/system/settings','⚙','Settings','Platform configuration']]}
];
export default function Sidebar({open=false,onClose}){
 const pathname=usePathname(); const {logout}=useAuth();
 return <>{open&&<button className="admin-sidebar-backdrop" aria-label="Close navigation" onClick={onClose}/>}
 <aside className="admin-sidebar ref-sidebar" data-open={open?'true':'false'}>
  <div className="ref-brand"><div className="ref-mark">◢</div><div><strong>Needle</strong><small>ADMIN CONSOLE</small></div></div>
  <nav className="ref-nav">{groups.map((g,i)=><section key={g.label||i}>{g.label&&<div className="ref-nav-heading">{g.label}</div>}{g.items.map(([href,icon,label,sub,exact])=>{const active=exact?pathname===href:(pathname===href||pathname.startsWith(href+'/'));return <Link key={href} href={href} className={`ref-nav-item ${active?'active':''}`} onClick={onClose}><I>{icon}</I><span><b>{label}</b><small>{sub}</small></span></Link>})}</section>)}</nav>
  <div className="ref-sidebar-foot"><div className="ref-motto"><span>◌</span><div><b>Needle</b><small>Better Governance.<br/>Closer to People.</small></div></div><button onClick={logout}>Sign out</button></div>
 </aside></>;
}