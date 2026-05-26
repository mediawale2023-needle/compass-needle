'use client';

import { useEffect, useState } from 'react';
import { Loader2, User, Tag, FileText } from 'lucide-react';
import { apiGet, apiPatch } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';
import { getStatusBadge } from '@/components/briefcase/briefcase-shared';

export default function BriefcaseContactPanel({ phone, color, onClose }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [form, setForm] = useState({ display_name: '', tags: '', notes: '' });
    const [saved, setSaved] = useState(false);

    useEffect(() => {
        if (!phone) {
            return;
        }
        setLoading(true);
        apiGet(`/api/contacts/${encodeURIComponent(phone)}`)
            .then((result) => {
                setData(result);
                setForm({
                    display_name: result.contact?.display_name || '',
                    tags: Array.isArray(result.contact?.tags)
                        ? result.contact.tags.join(', ')
                        : (result.contact?.tags || ''),
                    notes: result.contact?.notes || '',
                });
            })
            .catch(() => setData(null))
            .finally(() => setLoading(false));
    }, [phone]);

    const handleSave = async () => {
        setSaving(true);
        setSaved(false);
        try {
            const tags = form.tags
                ? form.tags.split(',').map((tag) => tag.trim()).filter(Boolean)
                : [];
            await apiPatch(`/api/contacts/${encodeURIComponent(phone)}`, {
                display_name: form.display_name || null,
                tags,
                notes: form.notes || null,
            });
            setSaved(true);
            setTimeout(() => setSaved(false), 2000);
        } catch (error) {
            console.error('Contact save failed:', error);
        } finally {
            setSaving(false);
        }
    };

    return (
        <Dialog open={!!phone} onOpenChange={onClose}>
            <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                <DialogHeader className="p-0 -m-6 mb-0">
                    <div className="p-6 text-white rounded-t-xl" style={{ background: color }}>
                        <DialogDescription className="text-white/80 text-xs uppercase tracking-widest font-semibold mb-1">
                            Constituent Profile
                        </DialogDescription>
                        <DialogTitle className="text-lg font-bold text-white font-mono">
                            {phone}
                        </DialogTitle>
                    </div>
                </DialogHeader>

                {loading ? (
                    <div className="py-12 flex items-center justify-center">
                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                ) : (
                    <div className="space-y-5 pt-6">
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="contact-name" className="flex items-center gap-1.5">
                                    <User className="h-3.5 w-3.5" /> Display Name
                                </Label>
                                <Input
                                    id="contact-name"
                                    value={form.display_name}
                                    onChange={(event) => setForm((current) => ({ ...current, display_name: event.target.value }))}
                                    placeholder="Enter constituent's name"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="contact-tags" className="flex items-center gap-1.5">
                                    <Tag className="h-3.5 w-3.5" /> Tags
                                    <span className="text-xs text-muted-foreground font-normal">(comma-separated)</span>
                                </Label>
                                <Input
                                    id="contact-tags"
                                    value={form.tags}
                                    onChange={(event) => setForm((current) => ({ ...current, tags: event.target.value }))}
                                    placeholder="e.g. Ward Councillor, Farmer, Repeat Caller"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="contact-notes" className="flex items-center gap-1.5">
                                    <FileText className="h-3.5 w-3.5" /> Notes
                                </Label>
                                <Textarea
                                    id="contact-notes"
                                    value={form.notes}
                                    onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
                                    placeholder="Internal staff notes about this constituent"
                                    className="min-h-[80px]"
                                />
                            </div>
                        </div>

                        <Button
                            onClick={handleSave}
                            disabled={saving}
                            style={{ background: color }}
                            className="w-full"
                        >
                            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                            {saved ? 'Saved!' : saving ? 'Saving…' : 'Save Contact'}
                        </Button>

                        <Separator />

                        <div>
                            <p className="text-xs text-muted-foreground uppercase font-medium mb-3">
                                Case History ({data?.cases?.length || 0})
                            </p>
                            {!data?.cases || data.cases.length === 0 ? (
                                <p className="text-sm text-muted-foreground text-center py-6">No cases found for this number.</p>
                            ) : (
                                <div className="divide-y divide-border border rounded-lg overflow-hidden">
                                    {data.cases.map((item) => (
                                        <div key={item.id} className="px-4 py-3 flex items-start justify-between gap-3 hover:bg-accent/30 transition-colors">
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-0.5">
                                                    <span className="text-xs font-mono text-muted-foreground">#{item.id}</span>
                                                    <span className="text-xs font-medium text-foreground">{item.category || 'General'}</span>
                                                </div>
                                                <p className="text-xs text-muted-foreground truncate">{item.raw_message || '—'}</p>
                                            </div>
                                            <div className="shrink-0 text-right">
                                                {getStatusBadge(item.status)}
                                                <p className="text-xs text-muted-foreground mt-1">
                                                    {item.created_at
                                                        ? new Date(item.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
                                                        : '—'}
                                                </p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>Close</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
