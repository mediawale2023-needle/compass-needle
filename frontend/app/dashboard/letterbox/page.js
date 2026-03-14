'use client';

import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import { apiGet } from '@/lib/api';
import { Upload, Mail, Send, X, PenTool, Loader2, Inbox, MailOpen } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

const URGENCY_VARIANTS = {
    High: 'destructive',
    Normal: 'success',
    Low: 'secondary',
};

const STATUS_VARIANTS = {
    'Pending-Intake': 'info',
    'Drafted': 'warning',
    'Resolved': 'success',
    'Sent': 'success',
};

function ScanBtn({ onUpload, direction }) {
    const [uploading, setUploading] = useState(false);
    const ref = useRef(null);
    
    const handle = async (file) => {
        if (!file) return;
        setUploading(true);
        try { await onUpload(file); }
        catch (e) { alert('Upload failed: ' + e.message); }
        finally { setUploading(false); }
    };
    
    return (
        <>
            <input 
                type="file" 
                ref={ref} 
                className="hidden" 
                accept=".pdf,image/*"
                onChange={e => handle(e.target.files[0])} 
            />
            <Button 
                onClick={() => ref.current?.click()} 
                disabled={uploading}
                className="gap-2"
            >
                {uploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                    <Upload className="h-4 w-4" />
                )}
                {uploading ? 'Scanning...' : direction === 'inbox' ? 'Scan Letter' : 'Upload Letter'}
            </Button>
        </>
    );
}

function LetterModal({ item, onClose, onDraft }) {
    if (!item) return null;
    
    return (
        <Dialog open={!!item} onOpenChange={onClose}>
            <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                <DialogHeader className="p-0 -m-6 mb-0">
                    <div className="p-6 text-primary-foreground rounded-t-xl bg-primary">
                        <DialogDescription className="text-primary-foreground/80 text-xs uppercase tracking-widest font-semibold mb-1">
                            {item.direction === 'inbox' ? 'Incoming Grievance' : 'Outgoing Letter'} · #{item.id}
                        </DialogDescription>
                        <DialogTitle className="text-lg font-bold text-primary-foreground">
                            {item.issue_summary && item.issue_summary !== '[NOT FOUND]'
                                ? item.issue_summary : 'No Subject'}
                        </DialogTitle>
                    </div>
                </DialogHeader>
                
                <div className="space-y-4 pt-6">
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                        {[
                            ['From / To', item.citizen_name],
                            ['Phone', item.phone_number],
                            ['Village', item.village],
                            ['Urgency', item.urgency_level],
                            ['Status', item.status],
                            ['Date', item.created_at ? new Date(item.created_at).toLocaleDateString('en-CA') : '-'],
                        ].map(([label, value]) => (
                            <div key={label} className="border rounded-lg p-3">
                                <div className="text-xs text-muted-foreground uppercase font-medium">{label}</div>
                                <div className="text-sm font-medium text-foreground mt-0.5">{value || '-'}</div>
                            </div>
                        ))}
                    </div>
                    
                    <div>
                        <div className="text-xs text-muted-foreground uppercase font-medium mb-2">Full Letter Content</div>
                        <div className="bg-muted/50 border rounded-lg p-4 text-sm text-foreground whitespace-pre-wrap leading-relaxed min-h-[100px]">
                            {item.ocr_raw_text && !item.ocr_raw_text.startsWith('[Gemini Vision')
                                ? item.ocr_raw_text
                                : item.issue_summary || 'No content available.'}
                        </div>
                    </div>
                </div>
                
                {item.direction === 'inbox' && (
                    <DialogFooter className="gap-2 sm:gap-0">
                        <Button variant="outline" onClick={onClose}>
                            Close
                        </Button>
                        <Button onClick={() => onDraft(item)} className="gap-2">
                            <PenTool className="h-4 w-4" />
                            Draft Response
                        </Button>
                    </DialogFooter>
                )}
            </DialogContent>
        </Dialog>
    );
}

export default function LetterboxPage() {
    const { user } = useAuth();
    const router = useRouter();
    const color = user?.theme_color || '#006a4d';

    const [tab, setTab] = useState('inbox');
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState(null);

    const fetchItems = async (dir) => {
        setLoading(true);
        try {
            const data = await apiGet(`/api/letterbox?direction=${dir}`);
            setItems(data.items || []);
        } catch (e) { console.error(e); }
        finally { setLoading(false); }
    };

    useEffect(() => { fetchItems(tab); }, [tab]);

    const handleUpload = async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('direction', tab);
        const token = localStorage.getItem('needle_token');
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/letterbox/upload`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
            throw new Error(err.detail || 'Upload failed');
        }
        fetchItems(tab);
    };

    const draftResponse = (item) => {
        const params = new URLSearchParams({
            subject: `Re: ${item.issue_summary}`,
            recipient: item.citizen_name !== '[NOT FOUND]' ? item.citizen_name : '',
            context: `From: ${item.citizen_name} (${item.village})\nPhone: ${item.phone_number}\n\nGrievance:\n${item.issue_summary}`,
        });
        router.push(`/dashboard/drafter?${params.toString()}`);
    };

    const getUrgencyBadge = (urgency) => {
        const variant = URGENCY_VARIANTS[urgency] || 'secondary';
        return (
            <Badge variant="secondary" className={cn(
                urgency === 'High' ? 'bg-red-100 text-red-700' :
                urgency === 'Normal' ? 'bg-green-100 text-green-700' :
                'bg-slate-100 text-slate-600'
            )}>
                {urgency || 'Normal'}
            </Badge>
        );
    };

    const getStatusBadge = (status) => {
        return (
            <Badge variant="secondary" className={cn(
                status === 'Pending-Intake' ? 'bg-blue-100 text-blue-700' :
                status === 'Drafted' ? 'bg-amber-100 text-amber-700' :
                status === 'Resolved' || status === 'Sent' ? 'bg-green-100 text-green-700' :
                'bg-slate-100 text-slate-600'
            )}>
                {status || '-'}
            </Badge>
        );
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-foreground">Letterbox</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Manage incoming and outgoing constituency correspondence
                    </p>
                </div>
            </div>

            <Card>
                <CardHeader className="pb-0">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                        <Tabs value={tab} onValueChange={setTab} className="w-full sm:w-auto">
                            <TabsList>
                                <TabsTrigger value="inbox" className="gap-2">
                                    <Inbox className="h-4 w-4" />
                                    Inbox
                                </TabsTrigger>
                                <TabsTrigger value="outbox" className="gap-2">
                                    <Send className="h-4 w-4" />
                                    Outbox
                                </TabsTrigger>
                            </TabsList>
                        </Tabs>
                        <ScanBtn onUpload={handleUpload} direction={tab} />
                    </div>
                </CardHeader>

                <CardContent className="pt-6">
                    {loading ? (
                        <div className="space-y-3">
                            {[1, 2, 3, 4, 5].map(i => (
                                <div key={i} className="flex items-center gap-4">
                                    <Skeleton className="h-4 w-8" />
                                    <Skeleton className="h-4 w-32" />
                                    <Skeleton className="h-4 w-24" />
                                    <Skeleton className="h-4 w-20" />
                                    <Skeleton className="h-4 flex-1" />
                                    <Skeleton className="h-6 w-16" />
                                    <Skeleton className="h-6 w-20" />
                                </div>
                            ))}
                        </div>
                    ) : items.length === 0 ? (
                        <div className="text-center py-16">
                            <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
                                {tab === 'inbox' ? (
                                    <Inbox className="h-8 w-8 text-muted-foreground" />
                                ) : (
                                    <Send className="h-8 w-8 text-muted-foreground" />
                                )}
                            </div>
                            <p className="text-muted-foreground">No letters in {tab} yet.</p>
                            <p className="text-sm text-muted-foreground mt-1">
                                Upload a letter to get started
                            </p>
                        </div>
                    ) : (
                        <div className="overflow-x-auto -mx-6">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="w-12">#</TableHead>
                                        <TableHead>{tab === 'inbox' ? 'Sender' : 'Recipient'}</TableHead>
                                        <TableHead>Village</TableHead>
                                        <TableHead>Phone</TableHead>
                                        <TableHead className="max-w-[200px]">Summary</TableHead>
                                        <TableHead>Urgency</TableHead>
                                        <TableHead>Status</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {items.map((item, idx) => (
                                        <TableRow 
                                            key={item.id} 
                                            onClick={() => setSelected(item)} 
                                            className="cursor-pointer"
                                        >
                                            <TableCell className="text-muted-foreground font-medium">
                                                {idx + 1}
                                            </TableCell>
                                            <TableCell className="font-semibold">
                                                {item.citizen_name || '-'}
                                            </TableCell>
                                            <TableCell>{item.village || '-'}</TableCell>
                                            <TableCell className="font-mono text-xs">
                                                {item.phone_number || '-'}
                                            </TableCell>
                                            <TableCell className="max-w-[200px] truncate text-muted-foreground">
                                                {item.issue_summary || '-'}
                                            </TableCell>
                                            <TableCell>{getUrgencyBadge(item.urgency_level)}</TableCell>
                                            <TableCell>{getStatusBadge(item.status)}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    )}
                </CardContent>
            </Card>

            <LetterModal 
                item={selected} 
                onClose={() => setSelected(null)} 
                onDraft={draftResponse} 
            />
        </div>
    );
}
