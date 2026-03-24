'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPatch } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import {
    Search,
    Users,
    Phone,
    MessageSquare,
    MapPin,
    Save,
    X,
    Loader2,
    UserCircle,
} from 'lucide-react';

function ContactCard({ contact, onSelect, selected }) {
    return (
        <div
            className={`p-4 border-b border-border cursor-pointer transition-colors hover:bg-accent/50 ${
                selected ? 'bg-primary/5 border-l-2 border-l-primary' : ''
            }`}
            onClick={() => onSelect(contact)}
        >
            <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-secondary flex items-center justify-center shrink-0">
                    <span className="text-sm font-semibold text-secondary-foreground">
                        {(contact.display_name || contact.phone || '?').charAt(0).toUpperCase()}
                    </span>
                </div>
                <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground truncate">
                        {contact.display_name || contact.phone}
                    </p>
                    <p className="text-xs text-muted-foreground">{contact.phone}</p>
                </div>
                {contact.tags && contact.tags.length > 0 && (
                    <Badge variant="outline" className="text-[10px] shrink-0">
                        {contact.tags[0]}
                    </Badge>
                )}
            </div>
        </div>
    );
}

function ContactDetail({ contact, onSave, saving }) {
    const [name, setName] = useState('');
    const [notes, setNotes] = useState('');
    const [tags, setTags] = useState('');

    useEffect(() => {
        if (contact) {
            setName(contact.display_name || '');
            setNotes(contact.notes || '');
            setTags((contact.tags || []).join(', '));
        }
    }, [contact]);

    if (!contact) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground py-20">
                <Users className="h-12 w-12 mb-3 opacity-30" />
                <p className="text-sm">Select a contact to view details</p>
            </div>
        );
    }

    const handleSave = () => {
        onSave(contact.phone, {
            display_name: name,
            notes,
            tags: tags.split(',').map(t => t.trim()).filter(Boolean),
        });
    };

    return (
        <div className="p-5 space-y-5">
            <div className="flex items-center gap-4">
                <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center">
                    <UserCircle className="h-8 w-8 text-primary" />
                </div>
                <div>
                    <h3 className="font-semibold text-foreground text-lg">{contact.display_name || 'Unknown'}</h3>
                    <p className="text-sm text-muted-foreground flex items-center gap-1">
                        <Phone className="h-3.5 w-3.5" />{contact.phone}
                    </p>
                </div>
            </div>

            <div className="space-y-4">
                <div>
                    <label className="text-xs text-muted-foreground mb-1.5 block">Display Name</label>
                    <Input
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="Enter name"
                    />
                </div>
                <div>
                    <label className="text-xs text-muted-foreground mb-1.5 block">Tags (comma-separated)</label>
                    <Input
                        value={tags}
                        onChange={(e) => setTags(e.target.value)}
                        placeholder="e.g. volunteer, ward-5, active"
                    />
                </div>
                <div>
                    <label className="text-xs text-muted-foreground mb-1.5 block">Notes</label>
                    <Textarea
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        placeholder="Private notes about this contact..."
                        rows={4}
                    />
                </div>
                <Button onClick={handleSave} disabled={saving} className="w-full sm:w-auto">
                    {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                    Save Contact
                </Button>
            </div>

            {/* Message History Summary */}
            {contact.case_count !== undefined && (
                <div className="bg-secondary/30 rounded-lg p-4">
                    <p className="text-xs text-muted-foreground mb-1">Messages from this contact</p>
                    <p className="text-2xl font-bold text-foreground">{contact.case_count || 0}</p>
                </div>
            )}
        </div>
    );
}

export default function ContactsPage() {
    const [contacts, setContacts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [selectedContact, setSelectedContact] = useState(null);
    const [saving, setSaving] = useState(false);

    const fetchContacts = useCallback(async () => {
        setLoading(true);
        try {
            // Use cases endpoint to build contact list (grouped by phone)
            const data = await apiGet('/api/cases?page=1&per_page=200');
            const caseList = data.cases || [];

            // Group by phone to build contact list
            const contactMap = {};
            caseList.forEach(c => {
                const phone = c.user_phone || 'unknown';
                if (!contactMap[phone]) {
                    contactMap[phone] = {
                        phone,
                        display_name: '',
                        tags: [],
                        notes: '',
                        case_count: 0,
                        last_message: c.raw_message,
                        last_location: c.location,
                    };
                }
                contactMap[phone].case_count++;
            });

            // Try to enrich with contact data from API
            const phoneList = Object.keys(contactMap);
            await Promise.all(
                phoneList.slice(0, 50).map(async (phone) => {
                    try {
                        const contact = await apiGet(`/api/contacts/${encodeURIComponent(phone)}`);
                        if (contact) {
                            contactMap[phone].display_name = contact.display_name || '';
                            contactMap[phone].tags = contact.tags || [];
                            contactMap[phone].notes = contact.notes || '';
                        }
                    } catch {
                        // Contact not found — that's fine
                    }
                })
            );

            setContacts(Object.values(contactMap).sort((a, b) => b.case_count - a.case_count));
        } catch {
            setContacts([]);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchContacts(); }, [fetchContacts]);

    const handleSave = async (phone, updates) => {
        setSaving(true);
        try {
            await apiPatch(`/api/contacts/${encodeURIComponent(phone)}`, updates);
            // Update local state
            setContacts(prev => prev.map(c =>
                c.phone === phone ? { ...c, ...updates } : c
            ));
            setSelectedContact(prev => prev?.phone === phone ? { ...prev, ...updates } : prev);
        } catch {
            // Fail silently
        } finally {
            setSaving(false);
        }
    };

    const filtered = search
        ? contacts.filter(c =>
            (c.display_name || '').toLowerCase().includes(search.toLowerCase()) ||
            c.phone.includes(search)
        )
        : contacts;

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h1 className="text-xl font-bold text-foreground">Contacts</h1>
                <Badge variant="outline" className="text-xs">
                    {filtered.length} contacts
                </Badge>
            </div>

            {/* Search */}
            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                    placeholder="Search by name or phone..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="pl-9"
                />
            </div>

            {/* Split View */}
            <div className="grid lg:grid-cols-5 gap-0 border border-border rounded-lg overflow-hidden bg-card min-h-[600px]">
                <div className="lg:col-span-2 border-r border-border overflow-y-auto max-h-[700px]">
                    {loading ? (
                        <div className="p-4 space-y-3">
                            {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
                        </div>
                    ) : filtered.length > 0 ? (
                        filtered.map(c => (
                            <ContactCard
                                key={c.phone}
                                contact={c}
                                onSelect={setSelectedContact}
                                selected={selectedContact?.phone === c.phone}
                            />
                        ))
                    ) : (
                        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
                            <Users className="h-10 w-10 mb-2 opacity-30" />
                            <p className="text-sm">No contacts found</p>
                        </div>
                    )}
                </div>
                <div className="lg:col-span-3 overflow-y-auto max-h-[700px]">
                    <ContactDetail
                        contact={selectedContact}
                        onSave={handleSave}
                        saving={saving}
                    />
                </div>
            </div>
        </div>
    );
}
