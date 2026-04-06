'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';
import {
    User, Shield, Info, Lock, LifeBuoy, ExternalLink,
    Users, UserPlus, Trash2, Loader2, CheckCircle2,
    AlertCircle, Phone, Crown, ChevronDown, ChevronUp,
    Eye, EyeOff,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';

/* ── helpers ─────────────────────────────────────────────────────── */

function initials(name) {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
}

function roleLabel(role) {
    if (role === 'mp')    return 'MP';
    if (role === 'admin') return 'Admin';
    return 'PA / Staff';
}

function roleBadgeStyle(role, color) {
    if (role === 'mp') return { background: `${color}20`, color };
    return { background: '#6b728015', color: '#6b7280' };
}

function formatDate(iso) {
    if (!iso) return 'Never';
    return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

/* ── AddMemberForm ───────────────────────────────────────────────── */

function AddMemberForm({ color, onSuccess, onCancel }) {
    const [form, setForm] = useState({
        display_name: '',
        username: '',
        phone: '',
        role: 'user',
        password: '',
        confirm: '',
    });
    const [showPw, setShowPw]   = useState(false);
    const [saving, setSaving]   = useState(false);
    const [error, setError]     = useState('');

    // Auto-suggest username from display name
    const handleNameChange = (val) => {
        const slug = val.toLowerCase().replace(/\s+/g, '.').replace(/[^a-z0-9.]/g, '');
        setForm(f => ({ ...f, display_name: val, username: slug }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        if (form.password !== form.confirm) { setError('Passwords do not match'); return; }
        if (form.password.length < 8) { setError('Password must be at least 8 characters'); return; }
        setSaving(true);
        try {
            await api('/team', {
                method: 'POST',
                body: JSON.stringify({
                    display_name: form.display_name.trim(),
                    username:     form.username.trim().toLowerCase(),
                    phone:        form.phone.trim(),
                    role:         form.role,
                    password:     form.password,
                }),
            });
            onSuccess();
        } catch (err) {
            setError(err.message || 'Could not create member');
        } finally {
            setSaving(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-4 pt-4 border-t border-border mt-4">
            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                    <Label htmlFor="tm-name">Full Name <span className="text-destructive">*</span></Label>
                    <Input
                        id="tm-name"
                        placeholder="e.g. Priya Sharma"
                        value={form.display_name}
                        onChange={e => handleNameChange(e.target.value)}
                        required
                    />
                </div>
                <div className="space-y-1.5">
                    <Label htmlFor="tm-username">
                        Username <span className="text-destructive">*</span>
                        <span className="text-xs text-muted-foreground ml-1">(auto-filled)</span>
                    </Label>
                    <Input
                        id="tm-username"
                        placeholder="priya.sharma"
                        value={form.username}
                        onChange={e => setForm(f => ({ ...f, username: e.target.value.toLowerCase() }))}
                        required
                    />
                </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                    <Label htmlFor="tm-phone">
                        WhatsApp Number
                        <span className="text-xs text-muted-foreground ml-1">(for letter intake)</span>
                    </Label>
                    <div className="relative">
                        <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input
                            id="tm-phone"
                            placeholder="919876543210"
                            className="pl-9"
                            value={form.phone}
                            onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                        />
                    </div>
                </div>
                <div className="space-y-1.5">
                    <Label htmlFor="tm-role">Role</Label>
                    <select
                        id="tm-role"
                        value={form.role}
                        onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                        <option value="user">PA / Staff</option>
                        <option value="mp">MP (Full Access)</option>
                    </select>
                </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                    <Label htmlFor="tm-pw">Password <span className="text-destructive">*</span></Label>
                    <div className="relative">
                        <Input
                            id="tm-pw"
                            type={showPw ? 'text' : 'password'}
                            placeholder="Min 8 characters"
                            className="pr-10"
                            value={form.password}
                            onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                            required
                        />
                        <button
                            type="button"
                            onClick={() => setShowPw(v => !v)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        >
                            {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                    </div>
                </div>
                <div className="space-y-1.5">
                    <Label htmlFor="tm-confirm">Confirm Password <span className="text-destructive">*</span></Label>
                    <Input
                        id="tm-confirm"
                        type={showPw ? 'text' : 'password'}
                        placeholder="Re-enter password"
                        value={form.confirm}
                        onChange={e => setForm(f => ({ ...f, confirm: e.target.value }))}
                        required
                    />
                </div>
            </div>

            {error && (
                <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error}
                </div>
            )}

            <div className="flex gap-2 justify-end">
                <Button type="button" variant="outline" onClick={onCancel} disabled={saving}>
                    Cancel
                </Button>
                <Button type="submit" disabled={saving} style={{ background: color }}>
                    {saving ? <><Loader2 className="h-4 w-4 animate-spin" /> Creating…</> : <><UserPlus className="h-4 w-4" /> Add Member</>}
                </Button>
            </div>
        </form>
    );
}

/* ── MemberRow ───────────────────────────────────────────────────── */

function MemberRow({ member, currentUserId, color, onDelete }) {
    const [confirming, setConfirming] = useState(false);
    const [deleting, setDeleting]     = useState(false);
    const isSelf    = member.id === currentUserId;
    const isPrimary = member.role === 'mp';

    const handleDelete = async () => {
        setDeleting(true);
        try {
            await api(`/team/${member.id}`, { method: 'DELETE' });
            onDelete(member.id);
        } catch (err) {
            alert(err.message || 'Could not remove member');
        } finally {
            setDeleting(false);
            setConfirming(false);
        }
    };

    return (
        <div className="flex items-center gap-4 py-3">
            <Avatar className="h-9 w-9 shrink-0">
                <AvatarFallback
                    className="text-sm font-semibold text-white"
                    style={{ background: isPrimary ? color : '#94a3b8' }}
                >
                    {initials(member.display_name || member.username)}
                </AvatarFallback>
            </Avatar>

            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-foreground truncate">
                        {member.display_name || member.username}
                    </span>
                    {isPrimary && <Crown className="h-3.5 w-3.5 shrink-0" style={{ color }} />}
                    {isSelf && (
                        <Badge variant="outline" className="text-xs py-0 h-5">You</Badge>
                    )}
                </div>
                <div className="flex items-center gap-3 mt-0.5">
                    <span className="text-xs text-muted-foreground">@{member.username}</span>
                    {member.phone && (
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                            <Phone className="h-3 w-3" />{member.phone}
                        </span>
                    )}
                </div>
            </div>

            <div className="flex items-center gap-3 shrink-0">
                <div className="hidden sm:block text-right">
                    <Badge className="text-xs" style={roleBadgeStyle(member.role, color)}>
                        {roleLabel(member.role)}
                    </Badge>
                    <p className="text-xs text-muted-foreground mt-1">
                        Last login {formatDate(member.last_login)}
                    </p>
                </div>

                {!isSelf && !isPrimary && (
                    confirming ? (
                        <div className="flex items-center gap-1.5">
                            <span className="text-xs text-destructive font-medium">Remove?</span>
                            <Button
                                size="sm"
                                variant="destructive"
                                className="h-7 text-xs px-2"
                                onClick={handleDelete}
                                disabled={deleting}
                            >
                                {deleting ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Yes'}
                            </Button>
                            <Button
                                size="sm"
                                variant="outline"
                                className="h-7 text-xs px-2"
                                onClick={() => setConfirming(false)}
                                disabled={deleting}
                            >
                                No
                            </Button>
                        </div>
                    ) : (
                        <Button
                            size="sm"
                            variant="ghost"
                            className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                            onClick={() => setConfirming(true)}
                            title="Remove member"
                        >
                            <Trash2 className="h-4 w-4" />
                        </Button>
                    )
                )}
            </div>
        </div>
    );
}

/* ── TeamCard ────────────────────────────────────────────────────── */

function TeamCard({ user, color }) {
    const [members, setMembers]     = useState([]);
    const [loading, setLoading]     = useState(true);
    const [showForm, setShowForm]   = useState(false);
    const [toast, setToast]         = useState('');

    const loadTeam = useCallback(async () => {
        setLoading(true);
        try {
            const data = await api('/team');
            setMembers(data.members || []);
        } catch {
            // silent — non-critical
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { loadTeam(); }, [loadTeam]);

    const handleAdded = () => {
        setShowForm(false);
        setToast('Team member added successfully.');
        setTimeout(() => setToast(''), 3500);
        loadTeam();
    };

    const handleDeleted = (id) => {
        setMembers(ms => ms.filter(m => m.id !== id));
        setToast('Member removed.');
        setTimeout(() => setToast(''), 3000);
    };

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Users className="h-5 w-5 text-muted-foreground" />
                        <CardTitle>Team</CardTitle>
                        {!loading && (
                            <Badge variant="secondary" className="text-xs">
                                {members.length} member{members.length !== 1 ? 's' : ''}
                            </Badge>
                        )}
                    </div>
                    <Button
                        size="sm"
                        onClick={() => setShowForm(v => !v)}
                        style={showForm ? {} : { background: color }}
                        variant={showForm ? 'outline' : 'default'}
                        className="gap-1.5"
                    >
                        {showForm
                            ? <><ChevronUp className="h-4 w-4" /> Cancel</>
                            : <><UserPlus className="h-4 w-4" /> Add Member</>
                        }
                    </Button>
                </div>
                <CardDescription>
                    Manage who has access to this dashboard. PAs and staff can view and update cases.
                    Only the MP account can add or remove members.
                </CardDescription>
            </CardHeader>

            <CardContent>
                {toast && (
                    <div className="flex items-center gap-2 text-sm text-green-700 dark:text-green-400 bg-green-500/10 border border-green-500/20 rounded-lg px-3 py-2 mb-4">
                        <CheckCircle2 className="h-4 w-4 shrink-0" />
                        {toast}
                    </div>
                )}

                {loading ? (
                    <div className="flex items-center justify-center py-8 text-muted-foreground gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span className="text-sm">Loading team…</span>
                    </div>
                ) : (
                    <div className="divide-y divide-border">
                        {members.map(m => (
                            <MemberRow
                                key={m.id}
                                member={m}
                                currentUserId={user?.id}
                                color={color}
                                onDelete={handleDeleted}
                            />
                        ))}
                        {members.length === 0 && (
                            <p className="text-sm text-muted-foreground py-4 text-center">
                                No team members yet.
                            </p>
                        )}
                    </div>
                )}

                {showForm && (
                    <AddMemberForm
                        color={color}
                        onSuccess={handleAdded}
                        onCancel={() => setShowForm(false)}
                    />
                )}
            </CardContent>
        </Card>
    );
}

/* ── Main Settings Page ──────────────────────────────────────────── */

export default function SettingsPage() {
    const { user } = useAuth();
    const [currentPw, setCurrentPw] = useState('');
    const [newPw, setNewPw]         = useState('');
    const [confirmPw, setConfirmPw] = useState('');
    const [pwSaving, setPwSaving]   = useState(false);
    const [pwMsg, setPwMsg]         = useState({ type: '', text: '' });
    const color = user?.theme_color || '#006a4d';

    const userInitials = user?.display_name?.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() || 'CN';

    const handlePasswordSubmit = async (e) => {
        e.preventDefault();
        setPwMsg({ type: '', text: '' });
        if (newPw !== confirmPw) {
            setPwMsg({ type: 'error', text: 'New passwords do not match' });
            return;
        }
        if (newPw.length < 8) {
            setPwMsg({ type: 'error', text: 'Password must be at least 8 characters' });
            return;
        }
        setPwSaving(true);
        try {
            await api('/auth/change-password', {
                method: 'POST',
                body: JSON.stringify({ current_password: currentPw, new_password: newPw }),
            });
            setPwMsg({ type: 'success', text: 'Password changed successfully.' });
            setCurrentPw(''); setNewPw(''); setConfirmPw('');
        } catch (err) {
            setPwMsg({ type: 'error', text: err.message || 'Failed to change password' });
        } finally {
            setPwSaving(false);
        }
    };

    const isMp = user?.role === 'mp' || user?.role === 'admin';

    return (
        <div className="space-y-6 max-w-2xl">
            <div>
                <h1 className="text-2xl font-bold text-foreground">Settings</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Manage your account and preferences
                </p>
            </div>

            {/* Profile Card */}
            <Card>
                <CardHeader>
                    <div className="flex items-center gap-2">
                        <User className="h-5 w-5 text-muted-foreground" />
                        <CardTitle>Profile</CardTitle>
                    </div>
                    <CardDescription>Your account information</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex items-start gap-6">
                        <Avatar className="h-16 w-16 border-4" style={{ borderColor: color }}>
                            <AvatarFallback
                                className="text-lg font-bold text-white"
                                style={{ background: color }}
                            >
                                {userInitials}
                            </AvatarFallback>
                        </Avatar>
                        <div className="flex-1 space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                {[
                                    ['Name',         user?.display_name],
                                    ['Username',     user?.username],
                                    ['Constituency', user?.constituency],
                                    ['House',        user?.house],
                                ].map(([label, value]) => (
                                    <div key={label}>
                                        <p className="text-xs text-muted-foreground uppercase font-medium">{label}</p>
                                        <p className="text-sm font-medium text-foreground mt-0.5">{value || '—'}</p>
                                    </div>
                                ))}
                            </div>
                            <div>
                                <p className="text-xs text-muted-foreground uppercase font-medium">Role</p>
                                <Badge variant="secondary" className="mt-1" style={{ background: `${color}15`, color }}>
                                    {user?.role || 'Member'}
                                </Badge>
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Team Management — MP-only */}
            {isMp && <TeamCard user={user} color={color} />}

            {/* Security Card */}
            <Card>
                <CardHeader>
                    <div className="flex items-center gap-2">
                        <Shield className="h-5 w-5 text-muted-foreground" />
                        <CardTitle>Security</CardTitle>
                    </div>
                    <CardDescription>Change your password</CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handlePasswordSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="currentPw">Current Password</Label>
                            <Input
                                id="currentPw"
                                type="password"
                                value={currentPw}
                                onChange={e => setCurrentPw(e.target.value)}
                                placeholder="Enter current password"
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="newPw">New Password</Label>
                            <Input
                                id="newPw"
                                type="password"
                                value={newPw}
                                onChange={e => setNewPw(e.target.value)}
                                placeholder="Min 8 characters"
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="confirmPw">Confirm New Password</Label>
                            <Input
                                id="confirmPw"
                                type="password"
                                value={confirmPw}
                                onChange={e => setConfirmPw(e.target.value)}
                                placeholder="Re-enter new password"
                                required
                            />
                        </div>

                        {pwMsg.text && (
                            <div className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg border ${
                                pwMsg.type === 'error'
                                    ? 'text-destructive bg-destructive/10 border-destructive/20'
                                    : 'text-green-700 dark:text-green-400 bg-green-500/10 border-green-500/20'
                            }`}>
                                {pwMsg.type === 'error'
                                    ? <AlertCircle className="h-4 w-4 shrink-0" />
                                    : <CheckCircle2 className="h-4 w-4 shrink-0" />
                                }
                                {pwMsg.text}
                            </div>
                        )}

                        <Button type="submit" disabled={pwSaving} style={{ background: color }}>
                            {pwSaving
                                ? <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</>
                                : <><Lock className="h-4 w-4" /> Change Password</>
                            }
                        </Button>
                    </form>
                </CardContent>
            </Card>

            {/* Support Card */}
            <Card>
                <CardHeader>
                    <div className="flex items-center gap-2">
                        <LifeBuoy className="h-5 w-5 text-muted-foreground" />
                        <CardTitle>Support</CardTitle>
                    </div>
                    <CardDescription>Report an issue to the Needle team</CardDescription>
                </CardHeader>
                <CardContent>
                    <p className="text-sm text-muted-foreground mb-4">
                        Found a bug or need help? Click below to send a pre-filled report with your account details.
                    </p>
                    <Button variant="outline" className="gap-2" asChild>
                        <a href={`mailto:support@needle.in?subject=${encodeURIComponent(`Issue from ${user?.constituency || 'MP Office'}`)}&body=${encodeURIComponent(`Hi Needle Team,\n\nI'm writing from the ${user?.constituency || ''} office.\n\nUsername: ${user?.username || ''}\nConstituency: ${user?.constituency || ''}\nHouse: ${user?.house || ''}\n\nIssue:\n[Please describe here]\n\nThank you`)}`}>
                            <ExternalLink className="h-4 w-4" />
                            Report an Issue
                        </a>
                    </Button>
                </CardContent>
            </Card>

            {/* System Info */}
            <Card>
                <CardHeader>
                    <div className="flex items-center gap-2">
                        <Info className="h-5 w-5 text-muted-foreground" />
                        <CardTitle>System Information</CardTitle>
                    </div>
                </CardHeader>
                <CardContent>
                    <div className="space-y-3">
                        {[
                            ['Version',      'Compass Needle v1.0.0'],
                            ['Last Updated', 'April 6, 2026'],
                            ['Environment',  'Production'],
                        ].map(([label, value]) => (
                            <div key={label} className="flex items-center justify-between">
                                <span className="text-sm text-muted-foreground">{label}</span>
                                <span className="text-sm font-medium text-foreground">{value}</span>
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
