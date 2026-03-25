'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost, apiDelete } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import {
    Shield,
    Plus,
    Trash2,
    Loader2,
    Mail,
    Phone,
    MapPin,
    Building2,
    X,
} from 'lucide-react';

const CATEGORY_OPTIONS = [
    'External Affairs', 'Railways', 'Infrastructure', 'Telecom',
    'Postal Services', 'Education (Central)', 'Banking & Finance',
    'Labor & Employment', 'Law & Order', 'Energy',
    'Infrastructure (State)', 'Food Supply', 'Transport',
    'Revenue & Land', 'Sanitation', 'Water', 'Civic Amenities',
    'Public Health', 'Civic Admin', 'Private/Legal',
];

export default function OfficersPage() {
    const toast = useToast();
    const [officers, setOfficers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showAdd, setShowAdd] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [deleting, setDeleting] = useState(null);

    const [form, setForm] = useState({
        name: '',
        designation: '',
        department: '',
        email: '',
        phone: '',
        jurisdiction: '',
        categories: [],
    });

    const fetchOfficers = useCallback(async () => {
        setLoading(true);
        try {
            const data = await apiGet('/api/officers');
            setOfficers(data.officers || []);
        } catch {
            toast.error('Failed to load officers');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchOfficers(); }, [fetchOfficers]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!form.name || !form.designation || !form.email) {
            toast.error('Name, designation, and email are required');
            return;
        }
        setSubmitting(true);
        try {
            await apiPost('/api/officers', form);
            toast.success('Officer added successfully');
            setForm({ name: '', designation: '', department: '', email: '', phone: '', jurisdiction: '', categories: [] });
            setShowAdd(false);
            await fetchOfficers();
        } catch (err) {
            toast.error('Failed to add officer: ' + (err.message || 'Unknown error'));
        } finally {
            setSubmitting(false);
        }
    };

    const handleDelete = async (id, name) => {
        if (!window.confirm(`Remove ${name} from officer directory?`)) return;
        setDeleting(id);
        try {
            await apiDelete(`/api/officers/${id}`);
            toast.success('Officer removed');
            await fetchOfficers();
        } catch {
            toast.error('Failed to remove officer');
        } finally {
            setDeleting(null);
        }
    };

    const toggleCategory = (cat) => {
        setForm(f => ({
            ...f,
            categories: f.categories.includes(cat)
                ? f.categories.filter(c => c !== cat)
                : [...f.categories, cat],
        }));
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-xl font-bold text-foreground">Officer Directory</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Manage government officers for case escalation
                    </p>
                </div>
                <Button onClick={() => setShowAdd(!showAdd)}>
                    {showAdd ? <X className="h-4 w-4 mr-2" /> : <Plus className="h-4 w-4 mr-2" />}
                    {showAdd ? 'Cancel' : 'Add Officer'}
                </Button>
            </div>

            {/* Add Officer Form */}
            {showAdd && (
                <Card>
                    <CardContent className="pt-6">
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="name">Name *</Label>
                                    <Input
                                        id="name"
                                        value={form.name}
                                        onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                                        placeholder="e.g. Shri R.K. Sharma"
                                        required
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="designation">Designation *</Label>
                                    <Input
                                        id="designation"
                                        value={form.designation}
                                        onChange={e => setForm(f => ({ ...f, designation: e.target.value }))}
                                        placeholder="e.g. District Collector"
                                        required
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="department">Department</Label>
                                    <Input
                                        id="department"
                                        value={form.department}
                                        onChange={e => setForm(f => ({ ...f, department: e.target.value }))}
                                        placeholder="e.g. Revenue & Land"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="email">Email *</Label>
                                    <Input
                                        id="email"
                                        type="email"
                                        value={form.email}
                                        onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                                        placeholder="officer@gov.in"
                                        required
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="phone">Phone</Label>
                                    <Input
                                        id="phone"
                                        value={form.phone}
                                        onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                                        placeholder="+91 98765 43210"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="jurisdiction">Jurisdiction</Label>
                                    <Input
                                        id="jurisdiction"
                                        value={form.jurisdiction}
                                        onChange={e => setForm(f => ({ ...f, jurisdiction: e.target.value }))}
                                        placeholder="e.g. Belgaum District"
                                    />
                                </div>
                            </div>

                            <div className="space-y-2">
                                <Label>Categories (click to select)</Label>
                                <div className="flex flex-wrap gap-2">
                                    {CATEGORY_OPTIONS.map(cat => (
                                        <Badge
                                            key={cat}
                                            variant={form.categories.includes(cat) ? 'default' : 'outline'}
                                            className="cursor-pointer text-xs"
                                            onClick={() => toggleCategory(cat)}
                                        >
                                            {cat}
                                        </Badge>
                                    ))}
                                </div>
                                {form.categories.length > 0 && (
                                    <p className="text-xs text-muted-foreground">
                                        Selected: {form.categories.join(', ')}
                                    </p>
                                )}
                            </div>

                            <Button type="submit" disabled={submitting} className="w-full sm:w-auto">
                                {submitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Shield className="h-4 w-4 mr-2" />}
                                Add Officer
                            </Button>
                        </form>
                    </CardContent>
                </Card>
            )}

            <Separator />

            {/* Officer List */}
            {loading ? (
                <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
            ) : officers.length === 0 ? (
                <div className="text-center py-12">
                    <Shield className="h-12 w-12 mx-auto text-muted-foreground/30 mb-3" />
                    <p className="text-sm text-muted-foreground">No officers added yet</p>
                    <p className="text-xs text-muted-foreground mt-1">
                        Add government officers to enable case escalation via email
                    </p>
                </div>
            ) : (
                <div className="grid gap-3">
                    {officers.map(o => (
                        <Card key={o.id}>
                            <CardContent className="py-4 px-5">
                                <div className="flex items-start justify-between gap-4">
                                    <div className="space-y-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <p className="font-semibold text-foreground">{o.name}</p>
                                            <Badge variant="outline" className="text-[10px]">{o.designation}</Badge>
                                        </div>
                                        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                                            {o.department && (
                                                <span className="flex items-center gap-1">
                                                    <Building2 className="h-3 w-3" />{o.department}
                                                </span>
                                            )}
                                            {o.email && (
                                                <span className="flex items-center gap-1">
                                                    <Mail className="h-3 w-3" />{o.email}
                                                </span>
                                            )}
                                            {o.phone && (
                                                <span className="flex items-center gap-1">
                                                    <Phone className="h-3 w-3" />{o.phone}
                                                </span>
                                            )}
                                            {o.jurisdiction && (
                                                <span className="flex items-center gap-1">
                                                    <MapPin className="h-3 w-3" />{o.jurisdiction}
                                                </span>
                                            )}
                                        </div>
                                        {o.categories && (() => {
                                            let cats = o.categories;
                                            if (typeof cats === 'string') {
                                                try { cats = JSON.parse(cats); } catch { cats = []; }
                                            }
                                            return cats.length > 0 ? (
                                                <div className="flex flex-wrap gap-1 mt-1">
                                                    {cats.map(c => (
                                                        <Badge key={c} variant="secondary" className="text-[10px]">{c}</Badge>
                                                    ))}
                                                </div>
                                            ) : null;
                                        })()}
                                    </div>
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="text-destructive hover:bg-destructive/10 shrink-0"
                                        disabled={deleting === o.id}
                                        onClick={() => handleDelete(o.id, o.name)}
                                    >
                                        {deleting === o.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
