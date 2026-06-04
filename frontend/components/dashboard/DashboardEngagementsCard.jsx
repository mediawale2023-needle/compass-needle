'use client';

import { useEffect, useState } from 'react';
import { apiDelete, apiGet, apiPost } from '@/lib/api';
import { dashboardFonts, dashboardPalette as P } from '@/lib/dashboard-theme';

const { serif: SERIF, mono: MONO } = dashboardFonts;

const ACTION_LABELS = {
    schedule: 'Add schedule',
    note: 'Add note',
    calendar: 'Add calendar',
};

const TYPE_LABELS = {
    schedule: 'Schedule',
    note: 'Note',
    calendar: 'Calendar',
};

function getTodayDateValue() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function formatTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleTimeString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
    });
}

function getItemMeta(item) {
    if (item.entry_type === 'note') return item.notes || 'Internal note';
    const parts = [];
    if (item.is_all_day) parts.push('All day');
    else if (item.starts_at) {
        parts.push(formatTime(item.starts_at));
        if (item.ends_at) parts.push(`- ${formatTime(item.ends_at)}`);
    }
    if (item.location) parts.push(item.location);
    if (item.calendar_url) parts.push('Calendar link');
    if (item.notes && item.entry_type !== 'note') parts.push(item.notes);
    return parts.filter(Boolean).join(' · ');
}

export default function DashboardEngagementsCard() {
    const todayLabel = new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' });
    const todayValue = getTodayDateValue();

    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [composerType, setComposerType] = useState('');
    const [form, setForm] = useState({
        title: '',
        notes: '',
        location: '',
        scheduled_for: todayValue,
        start_time: '',
        end_time: '',
        is_all_day: false,
        calendar_url: '',
    });

    const loadItems = async () => {
        setLoading(true);
        try {
            const response = await apiGet(`/api/dashboard/engagements?date=${todayValue}`);
            setItems(Array.isArray(response?.items) ? response.items : []);
            setError('');
        } catch (err) {
            setError(err.message || 'Failed to load schedule');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadItems();
    }, []);

    const resetComposer = (nextType = '') => {
        setComposerType(nextType);
        setForm({
            title: '',
            notes: '',
            location: '',
            scheduled_for: todayValue,
            start_time: '',
            end_time: '',
            is_all_day: false,
            calendar_url: '',
        });
    };

    const openComposer = (nextType) => {
        resetComposer(nextType);
        setError('');
    };

    const submitItem = async () => {
        setSaving(true);
        try {
            await apiPost('/api/dashboard/engagements', {
                entry_type: composerType,
                ...form,
            });
            resetComposer('');
            await loadItems();
        } catch (err) {
            setError(err.message || 'Failed to save schedule item');
        } finally {
            setSaving(false);
        }
    };

    const removeItem = async (itemId) => {
        try {
            await apiDelete(`/api/dashboard/engagements/${itemId}`);
            setItems((current) => current.filter((item) => item.id !== itemId));
        } catch (err) {
            setError(err.message || 'Failed to delete schedule item');
        }
    };

    return (
        <section style={{ background: P.surface, border: `1px solid ${P.hair}`, padding: 14, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
                <div>
                    <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 15, color: P.ink }}>Today · Schedule</div>
                    <div style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.12em', color: P.ink3, marginTop: 2, textTransform: 'uppercase' }}>{todayLabel}</div>
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                    {Object.entries(ACTION_LABELS).map(([type, label]) => (
                        <button
                            key={type}
                            type="button"
                            onClick={() => openComposer(type)}
                            style={{
                                border: `1px solid ${composerType === type ? P.green : P.hair}`,
                                background: composerType === type ? 'rgba(17, 112, 68, 0.08)' : P.paper,
                                color: composerType === type ? P.green : P.ink2,
                                fontFamily: MONO,
                                fontSize: 9.5,
                                letterSpacing: '0.08em',
                                textTransform: 'uppercase',
                                padding: '6px 8px',
                                cursor: 'pointer',
                            }}
                        >
                            {label}
                        </button>
                    ))}
                </div>
            </div>

            {composerType && (
                <div style={{ border: `1px solid ${P.hair}`, background: P.paper, padding: 10, display: 'grid', gap: 8, marginBottom: 10 }}>
                    <div style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.1em', color: P.ink3, textTransform: 'uppercase' }}>
                        {TYPE_LABELS[composerType]}
                    </div>
                    <input
                        value={form.title}
                        onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                        placeholder={composerType === 'note' ? 'Short note title' : 'Title'}
                        style={{ border: `1px solid ${P.hair}`, padding: '8px 10px', fontSize: 12, background: '#fff' }}
                    />
                    {composerType !== 'note' && (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                            <input
                                type="time"
                                value={form.start_time}
                                onChange={(event) => setForm((current) => ({ ...current, start_time: event.target.value }))}
                                disabled={form.is_all_day}
                                style={{ border: `1px solid ${P.hair}`, padding: '8px 10px', fontSize: 12, background: '#fff' }}
                            />
                            <input
                                type="time"
                                value={form.end_time}
                                onChange={(event) => setForm((current) => ({ ...current, end_time: event.target.value }))}
                                disabled={form.is_all_day}
                                style={{ border: `1px solid ${P.hair}`, padding: '8px 10px', fontSize: 12, background: '#fff' }}
                            />
                        </div>
                    )}
                    {composerType !== 'note' && (
                        <input
                            value={form.location}
                            onChange={(event) => setForm((current) => ({ ...current, location: event.target.value }))}
                            placeholder="Location"
                            style={{ border: `1px solid ${P.hair}`, padding: '8px 10px', fontSize: 12, background: '#fff' }}
                        />
                    )}
                    {composerType === 'calendar' && (
                        <input
                            value={form.calendar_url}
                            onChange={(event) => setForm((current) => ({ ...current, calendar_url: event.target.value }))}
                            placeholder="Calendar or meeting link"
                            style={{ border: `1px solid ${P.hair}`, padding: '8px 10px', fontSize: 12, background: '#fff' }}
                        />
                    )}
                    <textarea
                        value={form.notes}
                        onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
                        placeholder={composerType === 'note' ? 'Write the note…' : 'Optional note'}
                        rows={composerType === 'note' ? 3 : 2}
                        style={{ border: `1px solid ${P.hair}`, padding: '8px 10px', fontSize: 12, background: '#fff', resize: 'vertical' }}
                    />
                    {composerType !== 'note' && (
                        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: P.ink2 }}>
                            <input
                                type="checkbox"
                                checked={form.is_all_day}
                                onChange={(event) => setForm((current) => ({ ...current, is_all_day: event.target.checked }))}
                            />
                            All day
                        </label>
                    )}
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                        <button
                            type="button"
                            onClick={() => resetComposer('')}
                            style={{ border: `1px solid ${P.hair}`, background: P.paper, color: P.ink2, padding: '7px 10px', fontSize: 11, cursor: 'pointer' }}
                        >
                            Cancel
                        </button>
                        <button
                            type="button"
                            onClick={submitItem}
                            disabled={saving || !form.title.trim()}
                            style={{ border: `1px solid ${P.green}`, background: P.green, color: '#fff', padding: '7px 10px', fontSize: 11, cursor: 'pointer', opacity: saving || !form.title.trim() ? 0.7 : 1 }}
                        >
                            {saving ? 'Saving…' : 'Save'}
                        </button>
                    </div>
                </div>
            )}

            {error && (
                <div style={{ marginBottom: 10, fontSize: 11, color: P.red }}>{error}</div>
            )}

            <div style={{ flex: 1, overflow: 'auto' }}>
                {loading ? (
                    <div style={{ fontFamily: MONO, fontSize: 10, letterSpacing: '0.08em', color: P.ink3, textTransform: 'uppercase' }}>
                        Loading schedule…
                    </div>
                ) : items.length === 0 ? (
                    <div style={{ fontSize: 11.5, color: P.ink3, lineHeight: 1.5 }}>
                        No schedule items for today yet. Use <strong>Add schedule</strong>, <strong>Add note</strong>, or <strong>Add calendar</strong> to start planning the day.
                    </div>
                ) : (
                    items.map((item, index) => (
                        <div
                            key={item.id}
                            style={{
                                display: 'grid',
                                gridTemplateColumns: '64px 1fr auto',
                                gap: 10,
                                padding: '8px 0',
                                borderBottom: index < items.length - 1 ? `1px solid ${P.hair}` : 'none',
                                alignItems: 'start',
                            }}
                        >
                            <div style={{ fontFamily: MONO, fontSize: 10.5, color: P.ink2, fontWeight: 600 }}>
                                {item.entry_type === 'note' ? 'NOTE' : item.is_all_day ? 'DAY' : (formatTime(item.starts_at) || 'OPEN')}
                            </div>
                            <div>
                                <div style={{ fontSize: 11.5, color: P.ink, fontWeight: 600, lineHeight: 1.3 }}>{item.title}</div>
                                <div style={{ fontSize: 10, color: P.ink3, marginTop: 2, lineHeight: 1.4 }}>{getItemMeta(item) || TYPE_LABELS[item.entry_type]}</div>
                                {item.calendar_url && (
                                    <a href={item.calendar_url} target="_blank" rel="noreferrer" style={{ display: 'inline-block', marginTop: 4, fontSize: 10.5, color: P.blue }}>
                                        Open link
                                    </a>
                                )}
                            </div>
                            <button
                                type="button"
                                onClick={() => removeItem(item.id)}
                                style={{ border: 'none', background: 'transparent', color: P.ink3, fontFamily: MONO, fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', cursor: 'pointer', padding: 0 }}
                            >
                                Remove
                            </button>
                        </div>
                    ))
                )}
            </div>
        </section>
    );
}
