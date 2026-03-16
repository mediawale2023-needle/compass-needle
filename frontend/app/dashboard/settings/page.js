'use client';

import { useState } from 'react';
import { useAuth } from '@/lib/auth';
import { User, Shield, Info, Lock, LifeBuoy, ExternalLink } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';

export default function SettingsPage() {
    const { user } = useAuth();
    const [currentPw, setCurrentPw] = useState('');
    const [newPw, setNewPw] = useState('');
    const [confirmPw, setConfirmPw] = useState('');
    const [message, setMessage] = useState('');
    const color = user?.theme_color || '#006a4d';

    const initials = user?.display_name?.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() || 'CN';

    const handleSubmit = (e) => {
        e.preventDefault();
        if (newPw !== confirmPw) { 
            setMessage('Passwords do not match'); 
            return; 
        }
        setMessage('Password update coming soon.');
    };

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
                                {initials}
                            </AvatarFallback>
                        </Avatar>
                        <div className="flex-1 space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                {[
                                    ['Name', user?.display_name],
                                    ['Username', user?.username],
                                    ['Constituency', user?.constituency],
                                    ['House', user?.house],
                                ].map(([label, value]) => (
                                    <div key={label}>
                                        <p className="text-xs text-muted-foreground uppercase font-medium">
                                            {label}
                                        </p>
                                        <p className="text-sm font-medium text-foreground mt-0.5">
                                            {value || '-'}
                                        </p>
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
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="currentPw">Current Password</Label>
                            <Input
                                id="currentPw"
                                type="password"
                                value={currentPw}
                                onChange={e => setCurrentPw(e.target.value)}
                                placeholder="Enter current password"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="newPw">New Password</Label>
                            <Input
                                id="newPw"
                                type="password"
                                value={newPw}
                                onChange={e => setNewPw(e.target.value)}
                                placeholder="Enter new password"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="confirmPw">Confirm New Password</Label>
                            <Input
                                id="confirmPw"
                                type="password"
                                value={confirmPw}
                                onChange={e => setConfirmPw(e.target.value)}
                                placeholder="Confirm new password"
                            />
                        </div>
                        
                        {message && (
                            <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 px-3 py-2 rounded-lg">
                                {message}
                            </div>
                        )}
                        
                        <Button type="submit" style={{ background: color }}>
                            <Lock className="h-4 w-4" />
                            Change Password
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
                    <Button
                        variant="outline"
                        className="gap-2"
                        asChild
                    >
                        <a
                            href={`mailto:support@needle.in?subject=${encodeURIComponent(`Issue from ${user?.constituency || 'MP Office'}`)}&body=${encodeURIComponent(`Hi Needle Team,\n\nI'm writing from the ${user?.constituency || ''} office.\n\nUsername: ${user?.username || ''}\nConstituency: ${user?.constituency || ''}\nHouse: ${user?.house || ''}\n\nIssue description:\n[Please describe the issue here]\n\nThank you`)}`}
                        >
                            <ExternalLink className="h-4 w-4" />
                            Report an Issue
                        </a>
                    </Button>
                </CardContent>
            </Card>

            {/* System Info Card */}
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
                            ['Version', 'Compass Needle v1.0.0'],
                            ['Last Updated', 'March 9, 2026'],
                            ['Environment', 'Production'],
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
