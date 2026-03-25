'use client';

import { useState } from 'react';
import { useAuth } from '@/lib/auth';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
    Settings as SettingsIcon,
    User,
    Phone,
    MapPin,
    Shield,
    MessageSquare,
    Zap,
    Copy,
    Check,
    ExternalLink,
} from 'lucide-react';

export default function SettingsPage() {
    const { user } = useAuth();
    const [copied, setCopied] = useState(false);

    const whatsappNumber = user?.whatsapp_number || 'Not configured';

    const handleCopy = (text) => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="space-y-6 max-w-2xl">
            <div>
                <h1 className="text-xl font-bold text-foreground">Settings</h1>
                <p className="text-sm text-muted-foreground mt-0.5">Manage your account and preferences.</p>
            </div>

            {/* Profile */}
            <Card>
                <CardContent className="p-5">
                    <h2 className="font-semibold text-foreground flex items-center gap-2 mb-4">
                        <User className="h-5 w-5 text-primary" />
                        Profile
                    </h2>
                    <div className="grid sm:grid-cols-2 gap-4">
                        <div>
                            <label className="text-xs text-muted-foreground">Display Name</label>
                            <p className="text-sm font-medium text-foreground mt-0.5">
                                {user?.display_name || user?.username || '—'}
                            </p>
                        </div>
                        <div>
                            <label className="text-xs text-muted-foreground">Username</label>
                            <p className="text-sm font-medium text-foreground mt-0.5">
                                {user?.username || '—'}
                            </p>
                        </div>
                        <div>
                            <label className="text-xs text-muted-foreground">Constituency</label>
                            <p className="text-sm font-medium text-foreground mt-0.5 flex items-center gap-1">
                                <MapPin className="h-3.5 w-3.5 text-muted-foreground" />
                                {user?.constituency || '—'}
                            </p>
                        </div>
                        <div>
                            <label className="text-xs text-muted-foreground">Role</label>
                            <div className="mt-0.5">
                                <Badge variant="outline" className="text-xs">
                                    {user?.role || 'user'}
                                </Badge>
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* WhatsApp */}
            <Card>
                <CardContent className="p-5">
                    <h2 className="font-semibold text-foreground flex items-center gap-2 mb-4">
                        <MessageSquare className="h-5 w-5 text-emerald-500" />
                        WhatsApp Integration
                    </h2>
                    <div className="bg-secondary/50 rounded-lg p-4">
                        <label className="text-xs text-muted-foreground">Connected Number</label>
                        <div className="flex items-center gap-2 mt-1">
                            <p className="text-sm font-mono font-medium text-foreground">{whatsappNumber}</p>
                            {whatsappNumber !== 'Not configured' && (
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7"
                                    onClick={() => handleCopy(whatsappNumber)}
                                >
                                    {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                                </Button>
                            )}
                        </div>
                        <p className="text-xs text-muted-foreground mt-2">
                            Citizens message this number. Grievances are auto-classified by AI and appear in your Messages tab.
                        </p>
                    </div>
                </CardContent>
            </Card>

            {/* Subscription */}
            <Card>
                <CardContent className="p-5">
                    <h2 className="font-semibold text-foreground flex items-center gap-2 mb-4">
                        <Zap className="h-5 w-5 text-primary" />
                        Subscription
                    </h2>
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-foreground">Current Plan</p>
                            <p className="text-xs text-muted-foreground mt-0.5">AI grievance classification, dashboard, WhatsApp integration</p>
                        </div>
                        <Badge className="bg-primary text-primary-foreground">
                            Active
                        </Badge>
                    </div>
                </CardContent>
            </Card>

            {/* Support */}
            <Card>
                <CardContent className="p-5">
                    <h2 className="font-semibold text-foreground flex items-center gap-2 mb-4">
                        <Shield className="h-5 w-5 text-muted-foreground" />
                        Support
                    </h2>
                    <p className="text-sm text-muted-foreground">
                        Need help? Contact our support team for assistance with your Ambassador account.
                    </p>
                    <Button variant="outline" className="mt-3" asChild>
                        <a href="mailto:support@needleai.in">
                            <ExternalLink className="h-4 w-4 mr-2" />
                            Contact Support
                        </a>
                    </Button>
                </CardContent>
            </Card>
        </div>
    );
}
