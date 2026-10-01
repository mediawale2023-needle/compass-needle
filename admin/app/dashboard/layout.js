'use client';
import {useEffect,useState} from 'react';
import {useRouter,usePathname} from 'next/navigation';
import {useAuth} from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import NotificationTray from '@/components/NotificationTray';
const TITLES={'/dashboard/accounts':['Accounts','Manage political accounts, setup progress, access, and launch readiness'],'/dashboard/seats':['Seats & Geography','Manage constituency identity, geography, readiness, and account usage'],'/dashboard/cases-intelligence':['Case Operations','Investigate cases, knowledge readiness, AI diagnostics, and usage insight'],'/dashboard/system':['Platform Operations','Monitor messaging, sync, platform health, jobs, and configuration'],'/dashboard/staff-access':['Administration','Manage platform staff, permissions, and administrative history']};
export default function DashboardLayout({children}){
 const {user,loading}=useAuth(); const router=useRouter(); const pathname=usePathname(); const [open,setOpen]=useState(false);
 useEffect(()=>{if(!loading&&!user)router.push('/')},[user,loading,router]);
 if(loading)return <div className="ref-loading">Loading…</div>; if(!user)return null;
 const meta=Object.entries(TITLES).find(([r])=>pathname===r||pathname.startsWith(r+'/'))?.[1];
 return <div className="admin-shell ref-shell"><Sidebar open={open} onClose={()=>setOpen(false)}/><main className="admin-main ref-main">
  <header className="ref-topbar"><button className="admin-mobile-nav-button" aria-label="Open navigation" onClick={()=>setOpen(true)}>☰</button><div className="ref-search">⌕ <span>Search accounts, cases, seats, logs, or anything…</span><kbd>⌘ K</kbd></div><div className="ref-top-user"><NotificationTray/><span className="ref-avatar">{(user?.display_name||user?.username||'A').slice(0,2).toUpperCase()}</span><span><b>{user?.display_name||user?.username||'Administrator'}</b><small>Super Admin</small></span><span>⌄</span></div></header>
  {pathname!=='/dashboard'&&meta&&<div className="ref-page-head"><h1>{meta[0]}</h1><p>{meta[1]}</p></div>}
  <div className="admin-content ref-content">{children}</div>
 </main></div>;
}