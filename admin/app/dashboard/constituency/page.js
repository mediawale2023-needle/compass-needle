'use client';

import { useState, useEffect, useRef } from 'react';
import { apiGet, apiPost } from '@/lib/api';

// ── helpers ──────────────────────────────────────────────────────────────────
const PARTY_COLORS = {
    BJP: 'bg-orange-100 text-orange-800 border-orange-200',
    INC: 'bg-blue-100 text-blue-800 border-blue-200',
    JDU: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    SP:  'bg-red-100 text-red-800 border-red-200',
    BSP: 'bg-purple-100 text-purple-800 border-purple-200',
    AAP: 'bg-sky-100 text-sky-800 border-sky-200',
};
function PartyBadge({ party }) {
    const cls = PARTY_COLORS[party] || 'bg-gray-100 text-gray-700 border-gray-200';
    return (
        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${cls}`}>
            {party}
        </span>
    );
}

function Stat({ label, value, sub }) {
    return (
        <div className="flex flex-col gap-0.5">
            <span className="text-xs text-gray-500 uppercase tracking-wide">{label}</span>
            <span className="text-lg font-bold text-gray-900">{value ?? '—'}</span>
            {sub && <span className="text-xs text-gray-400">{sub}</span>}
        </div>
    );
}

function SectionCard({ title, icon, children }) {
    return (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 border-b border-gray-100 bg-gray-50">
                <span className="text-base">{icon}</span>
                <h3 className="text-sm font-semibold text-gray-800 uppercase tracking-wide">{title}</h3>
            </div>
            <div className="p-5">{children}</div>
        </div>
    );
}

function Tag({ children, color = 'gray' }) {
    const colors = {
        gray:   'bg-gray-100 text-gray-700',
        green:  'bg-emerald-100 text-emerald-800',
        red:    'bg-red-100 text-red-700',
        blue:   'bg-blue-100 text-blue-800',
        orange: 'bg-orange-100 text-orange-700',
        purple: 'bg-purple-100 text-purple-700',
    };
    return (
        <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[color] || colors.gray}`}>
            {children}
        </span>
    );
}

function ProgressBar({ value, max = 100, color = 'bg-emerald-500' }) {
    const pct = Math.min(100, Math.round((value / max) * 100));
    return (
        <div className="w-full bg-gray-100 rounded-full h-1.5">
            <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
        </div>
    );
}

// ── AI Generate Modal ─────────────────────────────────────────────────────────
const PROGRESS_STEPS = [
    'Starting Claude agent…',
    'Searching for constituency geography and demographics…',
    'Researching political history and election results…',
    'Gathering economic and infrastructure data…',
    'Compiling cultural profile and key challenges…',
    'Generating structured JSON profile…',
    'Saving constituency profile…',
];

function GenerateModal({ onClose, onGenerated }) {
    const [form, setForm]           = useState({ constituency_name: '', state: '', tenant_id: '', constituency_type: 'Lok Sabha' });
    const [jobId, setJobId]         = useState(null);
    const [status, setStatus]       = useState(null); // null | 'running' | 'done' | 'error'
    const [progress, setProgress]   = useState('');
    const [error, setError]         = useState('');
    const [stepIdx, setStepIdx]     = useState(0);
    const pollRef                   = useRef(null);

    // Animate progress steps while running
    useEffect(() => {
        if (status !== 'running') return;
        const t = setInterval(() => setStepIdx(i => Math.min(i + 1, PROGRESS_STEPS.length - 1)), 7000);
        return () => clearInterval(t);
    }, [status]);

    // Poll job status
    useEffect(() => {
        if (!jobId) return;
        pollRef.current = setInterval(async () => {
            try {
                const d = await apiGet(`/api/admin/constituency-profiles/generate/${jobId}`);
                setProgress(d.progress || '');
                if (d.status === 'done') {
                    clearInterval(pollRef.current);
                    setStatus('done');
                    onGenerated(d.slug);
                } else if (d.status === 'error') {
                    clearInterval(pollRef.current);
                    setStatus('error');
                    setError(d.error || 'Unknown error');
                }
            } catch {
                clearInterval(pollRef.current);
                setStatus('error');
                setError('Lost connection while polling. Please check the backend.');
            }
        }, 3000);
        return () => clearInterval(pollRef.current);
    }, [jobId]);

    async function handleGenerate() {
        if (!form.constituency_name.trim() || !form.state.trim() || !form.tenant_id) {
            setError('Please fill in all fields.');
            return;
        }
        const tid = parseInt(form.tenant_id, 10);
        if (isNaN(tid) || tid < 1) {
            setError('Tenant ID must be a positive integer.');
            return;
        }
        setError('');
        setStatus('running');
        setStepIdx(0);
        try {
            const d = await apiPost('/api/admin/constituency-profiles/generate', {
                constituency_name: form.constituency_name.trim(),
                state: form.state.trim(),
                tenant_id: tid,
                constituency_type: form.constituency_type,
            });
            setJobId(d.job_id);
        } catch (e) {
            setStatus('error');
            setError(e?.message || 'Failed to start generation job.');
        }
    }

    const displayStep = PROGRESS_STEPS[stepIdx];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 bg-gradient-to-r from-violet-600 to-indigo-600 text-white">
                    <div className="flex items-center gap-2">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        <h2 className="text-base font-semibold">Generate Constituency Profile with AI</h2>
                    </div>
                    {status !== 'running' && (
                        <button onClick={onClose} className="text-white/70 hover:text-white transition-colors">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    )}
                </div>

                <div className="px-6 py-5">
                    {/* Success state */}
                    {status === 'done' && (
                        <div className="text-center py-4">
                            <div className="w-14 h-14 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-3">
                                <svg className="w-7 h-7 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                            </div>
                            <p className="text-base font-semibold text-gray-900 mb-1">Profile Generated!</p>
                            <p className="text-sm text-gray-500 mb-5">The constituency profile has been saved and is now available in the viewer.</p>
                            <button
                                onClick={onClose}
                                className="px-6 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors"
                            >
                                View Profile
                            </button>
                        </div>
                    )}

                    {/* Running state */}
                    {status === 'running' && (
                        <div className="py-2">
                            <div className="flex items-center gap-3 mb-4">
                                <div className="w-8 h-8 border-3 border-violet-600 border-t-transparent rounded-full animate-spin shrink-0" style={{borderWidth: '3px'}} />
                                <div>
                                    <p className="text-sm font-medium text-gray-900">Claude is researching…</p>
                                    <p className="text-xs text-gray-500">This takes 1–3 minutes. Please wait.</p>
                                </div>
                            </div>

                            {/* Progress bar */}
                            <div className="w-full bg-gray-100 rounded-full h-1.5 mb-3">
                                <div
                                    className="h-1.5 rounded-full bg-violet-500 transition-all duration-1000"
                                    style={{ width: `${Math.round(((stepIdx + 1) / PROGRESS_STEPS.length) * 100)}%` }}
                                />
                            </div>

                            <p className="text-xs text-violet-700 font-medium">{progress || displayStep}</p>

                            <div className="mt-4 space-y-1.5">
                                {PROGRESS_STEPS.slice(0, stepIdx + 1).map((s, i) => (
                                    <div key={i} className="flex items-center gap-2 text-xs">
                                        {i < stepIdx
                                            ? <svg className="w-3.5 h-3.5 text-emerald-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg>
                                            : <div className="w-3.5 h-3.5 border-2 border-violet-400 border-t-transparent rounded-full animate-spin shrink-0" />
                                        }
                                        <span className={i < stepIdx ? 'text-gray-400 line-through' : 'text-violet-700 font-medium'}>{s}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Input form (idle or error) */}
                    {(status === null || status === 'error') && (
                        <>
                            <p className="text-sm text-gray-500 mb-4">
                                Claude will use web search to research the constituency and generate a comprehensive intelligence profile automatically.
                            </p>

                            {error && (
                                <div className="mb-4 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">{error}</div>
                            )}

                            <div className="space-y-3">
                                <div>
                                    <label className="block text-xs font-medium text-gray-700 mb-1">Constituency Name</label>
                                    <input
                                        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-400"
                                        placeholder="e.g. Aligarh, Varanasi, Pune"
                                        value={form.constituency_name}
                                        onChange={e => setForm(f => ({ ...f, constituency_name: e.target.value }))}
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-medium text-gray-700 mb-1">State</label>
                                    <input
                                        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-400"
                                        placeholder="e.g. Uttar Pradesh, Maharashtra"
                                        value={form.state}
                                        onChange={e => setForm(f => ({ ...f, state: e.target.value }))}
                                    />
                                </div>
                                <div className="flex gap-3">
                                    <div className="flex-1">
                                        <label className="block text-xs font-medium text-gray-700 mb-1">Tenant ID</label>
                                        <input
                                            type="number"
                                            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-400"
                                            placeholder="e.g. 3"
                                            value={form.tenant_id}
                                            onChange={e => setForm(f => ({ ...f, tenant_id: e.target.value }))}
                                        />
                                    </div>
                                    <div className="flex-1">
                                        <label className="block text-xs font-medium text-gray-700 mb-1">Type</label>
                                        <select
                                            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-400 bg-white"
                                            value={form.constituency_type}
                                            onChange={e => setForm(f => ({ ...f, constituency_type: e.target.value }))}
                                        >
                                            <option>Lok Sabha</option>
                                            <option>Vidhan Sabha</option>
                                        </select>
                                    </div>
                                </div>
                            </div>

                            <div className="flex gap-3 mt-5">
                                <button
                                    onClick={onClose}
                                    className="flex-1 px-4 py-2 text-sm border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleGenerate}
                                    className="flex-1 px-4 py-2 text-sm bg-violet-600 text-white rounded-lg font-medium hover:bg-violet-700 transition-colors flex items-center justify-center gap-2"
                                >
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                            d="M13 10V3L4 14h7v7l9-11h-7z" />
                                    </svg>
                                    Generate with Claude
                                </button>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}


// ── main component ────────────────────────────────────────────────────────────
export default function ConstituencyIntelligencePage() {
    const [profiles, setProfiles]       = useState([]);
    const [selected, setSelected]       = useState(null);
    const [profile, setProfile]         = useState(null);
    const [loading, setLoading]         = useState(false);
    const [tab, setTab]                 = useState('overview');
    const [showGenerate, setShowGenerate] = useState(false);

    function loadProfiles(selectSlug) {
        return apiGet('/api/admin/constituency-profiles')
            .then(d => {
                setProfiles(d.profiles || []);
                if (selectSlug) {
                    setSelected(selectSlug);
                } else if (d.profiles?.length) {
                    setSelected(d.profiles[0].slug);
                }
            })
            .catch(() => {});
    }

    useEffect(() => { loadProfiles(null); }, []);

    useEffect(() => {
        if (!selected) return;
        setLoading(true);
        setProfile(null);
        apiGet(`/api/admin/constituency-profiles/${selected}`)
            .then(d => { setProfile(d); setTab('overview'); })
            .catch(() => {})
            .finally(() => setLoading(false));
    }, [selected]);

    const TABS = [
        { id: 'overview',   label: 'Overview' },
        { id: 'political',  label: 'Political' },
        { id: 'assembly',   label: 'Assembly' },
        { id: 'economy',    label: 'Economy' },
        { id: 'social',     label: 'Social' },
        { id: 'culture',    label: 'Culture & Heritage' },
        { id: 'challenges', label: 'Challenges' },
    ];

    return (
        <div className="min-h-screen bg-gray-50">
            {showGenerate && (
                <GenerateModal
                    onClose={() => setShowGenerate(false)}
                    onGenerated={(slug) => {
                        setShowGenerate(false);
                        loadProfiles(slug);
                    }}
                />
            )}

            {/* Header row */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-xl font-bold text-gray-900">Constituency Intelligence</h1>
                    <p className="text-sm text-gray-500 mt-0.5">Deep political, demographic, economic and cultural profiles</p>
                </div>
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => setShowGenerate(true)}
                        className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700 transition-colors shadow-sm"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        Generate with AI
                    </button>
                    {profiles.length > 1 && (
                        <select
                            value={selected || ''}
                            onChange={e => setSelected(e.target.value)}
                            className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                        >
                            {profiles.map(p => (
                                <option key={p.slug} value={p.slug}>{p.name} ({p.state})</option>
                            ))}
                        </select>
                    )}
                </div>
            </div>

            {loading && (
                <div className="flex items-center justify-center py-24 text-gray-400 text-sm">Loading profile…</div>
            )}

            {!loading && !profile && (
                <div className="flex items-center justify-center py-24 text-gray-400 text-sm">No constituency profiles available.</div>
            )}

            {!loading && profile && (
                <>
                    {/* Hero card */}
                    <div className="bg-gradient-to-br from-emerald-700 to-emerald-900 rounded-2xl p-6 mb-6 text-white">
                        <div className="flex flex-wrap items-start justify-between gap-4">
                            <div>
                                <div className="flex items-center gap-3 mb-1">
                                    <h2 className="text-2xl font-bold">{profile.meta?.name}</h2>
                                    {profile.meta?.also_known_as?.length > 0 && (
                                        <span className="text-emerald-300 text-sm">
                                            aka {profile.meta.also_known_as.join(', ')}
                                        </span>
                                    )}
                                </div>
                                <p className="text-emerald-200 text-sm">
                                    {profile.meta?.type} Constituency · {profile.meta?.state} · {profile.meta?.reservation}
                                </p>
                                <p className="text-emerald-300 text-xs mt-1">{profile.geography?.coordinates}</p>
                            </div>
                            <div className="flex flex-wrap gap-6 text-right">
                                <div>
                                    <div className="text-2xl font-bold">{(profile.meta?.total_electors_2024 / 100000).toFixed(2)}L</div>
                                    <div className="text-emerald-300 text-xs">Registered Voters (2024)</div>
                                </div>
                                <div>
                                    <div className="text-2xl font-bold">{(profile.demographics?.total_population / 100000).toFixed(1)}L</div>
                                    <div className="text-emerald-300 text-xs">Population (Census 2011)</div>
                                </div>
                                <div>
                                    <div className="text-2xl font-bold">{profile.geography?.area_sq_km?.toLocaleString()} km²</div>
                                    <div className="text-emerald-300 text-xs">Area</div>
                                </div>
                            </div>
                        </div>

                        {/* Current MP strip */}
                        {profile.political_history?.current_mp && (
                            <div className="mt-4 pt-4 border-t border-emerald-600 flex flex-wrap items-center gap-4">
                                <div className="flex items-center gap-3">
                                    <div className="h-10 w-10 rounded-full bg-emerald-600 flex items-center justify-center text-base font-bold">
                                        {profile.political_history.current_mp.name?.charAt(0)}
                                    </div>
                                    <div>
                                        <div className="font-semibold text-sm">{profile.political_history.current_mp.name}</div>
                                        <div className="text-emerald-300 text-xs">
                                            {profile.political_history.current_mp.party} · MP since {profile.political_history.current_mp.elected_year}
                                        </div>
                                    </div>
                                </div>
                                <div className="ml-auto flex gap-6 text-sm">
                                    <div className="text-center">
                                        <div className="font-bold">{profile.political_history.current_mp.vote_share_percent}%</div>
                                        <div className="text-emerald-300 text-xs">Vote Share</div>
                                    </div>
                                    <div className="text-center">
                                        <div className="font-bold">{(profile.political_history.current_mp.winning_margin / 1000).toFixed(0)}K</div>
                                        <div className="text-emerald-300 text-xs">Margin</div>
                                    </div>
                                    <div className="text-center">
                                        <div className="font-bold">{profile.political_history.current_mp.voter_turnout_percent}%</div>
                                        <div className="text-emerald-300 text-xs">Turnout</div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Notable facts ticker */}
                    {profile.notable_facts?.length > 0 && (
                        <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-3 mb-6 flex gap-3 items-start">
                            <span className="text-amber-500 mt-0.5 shrink-0">★</span>
                            <div className="flex flex-wrap gap-2">
                                {profile.notable_facts.map((f, i) => (
                                    <span key={i} className="text-xs text-amber-800">{f}{i < profile.notable_facts.length - 1 ? ' ·' : ''}</span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Tab bar */}
                    <div className="flex gap-1 mb-5 border-b border-gray-200 overflow-x-auto pb-0.5">
                        {TABS.map(t => (
                            <button
                                key={t.id}
                                onClick={() => setTab(t.id)}
                                className={`px-4 py-2 text-sm font-medium whitespace-nowrap rounded-t-lg transition-colors
                                    ${tab === t.id
                                        ? 'bg-white border border-b-white border-gray-200 text-emerald-700 -mb-px'
                                        : 'text-gray-500 hover:text-gray-800'
                                    }`}
                            >
                                {t.label}
                            </button>
                        ))}
                    </div>

                    {/* ── OVERVIEW tab ─────────────────────────────────────────────── */}
                    {tab === 'overview' && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                            {/* Demographics snapshot */}
                            <SectionCard title="Demographics" icon="👥">
                                <div className="grid grid-cols-2 gap-4 mb-4">
                                    <Stat label="Population" value={`${(profile.demographics?.total_population / 100000).toFixed(1)}L`} sub="Census 2011" />
                                    <Stat label="Density" value={`${profile.demographics?.population_density_per_sq_km}/km²`} />
                                    <Stat label="Sex Ratio" value={`${profile.demographics?.sex_ratio_per_1000_males}/1000`} />
                                    <Stat label="Literacy" value={`${profile.demographics?.literacy?.overall_percent}%`} />
                                </div>
                                <div className="space-y-2">
                                    <div className="flex justify-between text-xs text-gray-600 mb-0.5">
                                        <span>Male literacy: {profile.demographics?.literacy?.male_percent}%</span>
                                        <span>Female literacy: {profile.demographics?.literacy?.female_percent}%</span>
                                    </div>
                                    <ProgressBar value={profile.demographics?.literacy?.male_percent} color="bg-blue-500" />
                                    <ProgressBar value={profile.demographics?.literacy?.female_percent} color="bg-pink-500" />
                                </div>
                                <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-2 gap-2 text-xs text-gray-600">
                                    <div>Urban: <strong>{profile.demographics?.urban_rural_split?.urban_percent}%</strong></div>
                                    <div>Rural: <strong>{profile.demographics?.urban_rural_split?.rural_percent}%</strong></div>
                                    <div>SC: <strong>{profile.demographics?.castes?.scheduled_caste_percent}%</strong></div>
                                    <div>ST: <strong>{profile.demographics?.castes?.scheduled_tribe_percent}%</strong></div>
                                </div>
                            </SectionCard>

                            {/* Religion breakdown */}
                            <SectionCard title="Religion & Language" icon="🕌">
                                <div className="space-y-2 mb-4">
                                    {[
                                        { label: 'Hindu', pct: profile.demographics?.religion?.hindu_percent, color: 'bg-orange-400' },
                                        { label: 'Muslim', pct: profile.demographics?.religion?.muslim_percent, color: 'bg-green-500' },
                                        { label: 'Jain', pct: profile.demographics?.religion?.jain_percent, color: 'bg-purple-500' },
                                        { label: 'Christian', pct: profile.demographics?.religion?.christian_percent, color: 'bg-blue-400' },
                                    ].filter(r => r.pct > 0).map(r => (
                                        <div key={r.label}>
                                            <div className="flex justify-between text-xs text-gray-600 mb-0.5">
                                                <span>{r.label}</span><span>{r.pct}%</span>
                                            </div>
                                            <ProgressBar value={r.pct} color={r.color} />
                                        </div>
                                    ))}
                                </div>
                                <div className="pt-3 border-t border-gray-100">
                                    <div className="text-xs font-medium text-gray-500 mb-2">Languages</div>
                                    <div className="flex flex-wrap gap-1.5">
                                        <Tag color="blue">Kannada {profile.demographics?.languages?.kannada_percent}%</Tag>
                                        <Tag color="orange">Marathi {profile.demographics?.languages?.marathi_percent}%</Tag>
                                        <Tag color="green">Urdu {profile.demographics?.languages?.urdu_percent}%</Tag>
                                        {profile.demographics?.languages?.other?.map(l => <Tag key={l}>{l}</Tag>)}
                                    </div>
                                    {profile.demographics?.languages?.language_politics && (
                                        <p className="text-xs text-gray-500 mt-2 italic">{profile.demographics.languages.language_politics}</p>
                                    )}
                                </div>
                            </SectionCard>

                            {/* Geography */}
                            <SectionCard title="Geography" icon="🗺️">
                                <p className="text-sm text-gray-700 mb-3 leading-relaxed">{profile.geography?.terrain}</p>
                                <div className="space-y-3">
                                    <div>
                                        <div className="text-xs font-medium text-gray-500 mb-1.5">Major Rivers</div>
                                        <div className="flex flex-wrap gap-1.5">
                                            {profile.geography?.rivers?.map(r => <Tag key={r.name} color="blue">{r.name}</Tag>)}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-xs font-medium text-gray-500 mb-1.5">Bordering States</div>
                                        <div className="flex flex-wrap gap-1.5">
                                            {profile.geography?.bordering_states?.map(s => <Tag key={s}>{s}</Tag>)}
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-3 gap-3 pt-2 border-t border-gray-100 text-center text-xs">
                                        <div><div className="font-semibold text-gray-800">{profile.geography?.climate?.avg_annual_rainfall_mm} mm</div><div className="text-gray-400">Rainfall</div></div>
                                        <div><div className="font-semibold text-gray-800">{profile.geography?.climate?.summer_temp_celsius}</div><div className="text-gray-400">Summer</div></div>
                                        <div><div className="font-semibold text-gray-800">{profile.geography?.talukas?.length}</div><div className="text-gray-400">Talukas</div></div>
                                    </div>
                                </div>
                            </SectionCard>

                            {/* Economy snapshot */}
                            <SectionCard title="Economy Snapshot" icon="🏭">
                                <p className="text-sm text-gray-700 mb-3">{profile.economy?.overview}</p>
                                <div className="space-y-1.5">
                                    {profile.economy?.industries?.slice(0, 4).map(ind => (
                                        <div key={ind.sector} className="flex gap-2">
                                            <span className="shrink-0 w-2 h-2 rounded-full bg-emerald-500 mt-1.5" />
                                            <div>
                                                <span className="text-xs font-semibold text-gray-800">{ind.sector}</span>
                                                <span className="text-xs text-gray-500 ml-1">— {ind.details?.slice(0, 90)}…</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </SectionCard>
                        </div>
                    )}

                    {/* ── POLITICAL tab ────────────────────────────────────────────── */}
                    {tab === 'political' && (
                        <div className="space-y-5">
                            {/* Current MP */}
                            {profile.political_history?.current_mp && (
                                <SectionCard title="Current MP — 2024 Lok Sabha" icon="🏛️">
                                    <div className="flex flex-wrap gap-6 mb-4">
                                        <div className="flex items-center gap-4">
                                            <div className="h-14 w-14 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-xl font-bold shrink-0">
                                                {profile.political_history.current_mp.name?.charAt(0)}
                                            </div>
                                            <div>
                                                <div className="text-lg font-bold text-gray-900">{profile.political_history.current_mp.name}</div>
                                                <PartyBadge party={profile.political_history.current_mp.party} />
                                                <div className="text-xs text-gray-500 mt-1">{profile.political_history.current_mp.bio}</div>
                                            </div>
                                        </div>
                                        <div className="ml-auto grid grid-cols-3 gap-6 text-center">
                                            <div>
                                                <div className="text-2xl font-bold text-gray-900">{profile.political_history.current_mp.vote_share_percent}%</div>
                                                <div className="text-xs text-gray-500">Vote Share</div>
                                            </div>
                                            <div>
                                                <div className="text-2xl font-bold text-emerald-700">{(profile.political_history.current_mp.winning_margin / 1000).toFixed(0)}K</div>
                                                <div className="text-xs text-gray-500">Win Margin</div>
                                            </div>
                                            <div>
                                                <div className="text-2xl font-bold text-gray-900">{profile.political_history.current_mp.voter_turnout_percent}%</div>
                                                <div className="text-xs text-gray-500">Turnout</div>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-600">
                                        Runner-up: <strong>{profile.political_history.current_mp.runner_up}</strong> with {(profile.political_history.current_mp.runner_up_votes / 1000).toFixed(0)}K votes
                                    </div>
                                </SectionCard>
                            )}

                            {/* Key political issues + border dispute */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                                <SectionCard title="Key Political Issues" icon="⚡">
                                    <ul className="space-y-2">
                                        {profile.political_history?.key_political_issues?.map((issue, i) => (
                                            <li key={i} className="flex gap-2 text-sm text-gray-700">
                                                <span className="text-emerald-500 shrink-0">›</span>{issue}
                                            </li>
                                        ))}
                                    </ul>
                                </SectionCard>

                                <SectionCard title="Political Character" icon="🗳️">
                                    <p className="text-sm text-gray-700 mb-3">{profile.political_history?.political_character}</p>
                                    <div>
                                        <div className="text-xs font-medium text-gray-500 mb-2">Party Dominance History</div>
                                        {Object.entries(profile.political_history?.party_dominance || {}).map(([party, desc]) => (
                                            <div key={party} className="flex gap-2 mb-1.5 text-xs">
                                                <PartyBadge party={party} />
                                                <span className="text-gray-600">{desc}</span>
                                            </div>
                                        ))}
                                    </div>
                                </SectionCard>
                            </div>

                            {/* Border dispute */}
                            {profile.political_history?.border_dispute && (
                                <SectionCard title="Maharashtra–Karnataka Border Dispute" icon="⚠️">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                                        <div className="space-y-2 text-sm text-gray-700">
                                            <p><strong>Origin:</strong> {profile.political_history.border_dispute.origin}</p>
                                            <p><strong>Maharashtra claims:</strong> {profile.political_history.border_dispute.maharashtra_claim}</p>
                                            <p><strong>Current status:</strong> {profile.political_history.border_dispute.current_status}</p>
                                        </div>
                                        <div>
                                            <div className="text-xs font-medium text-gray-500 mb-2">Mahajan Commission (1966–67)</div>
                                            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-900 space-y-1">
                                                <div>Chair: {profile.political_history.border_dispute.mahajan_commission?.chair}</div>
                                                <div>Recommendation: {profile.political_history.border_dispute.mahajan_commission?.recommendation}</div>
                                                <div className="font-semibold">Outcome: {profile.political_history.border_dispute.mahajan_commission?.outcome}</div>
                                            </div>
                                            <div className="mt-3 space-y-1">
                                                {profile.political_history.border_dispute.key_incidents?.map((inc, i) => (
                                                    <div key={i} className="text-xs text-gray-600 flex gap-2">
                                                        <span className="text-red-400">●</span>{inc}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                </SectionCard>
                            )}

                            {/* MP History table */}
                            <SectionCard title="MP Election History" icon="📜">
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="text-xs text-gray-500 border-b border-gray-100">
                                                <th className="text-left py-2 font-medium">Year</th>
                                                <th className="text-left py-2 font-medium">MP</th>
                                                <th className="text-left py-2 font-medium">Party</th>
                                                <th className="text-right py-2 font-medium">Margin</th>
                                                <th className="text-left py-2 font-medium">Notes</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-50">
                                            {profile.political_history?.past_mps?.map((mp, i) => (
                                                <tr key={i} className="hover:bg-gray-50 transition-colors">
                                                    <td className="py-2 text-gray-600 font-mono text-xs">{mp.year}</td>
                                                    <td className="py-2 font-medium text-gray-900">{mp.name}</td>
                                                    <td className="py-2"><PartyBadge party={mp.party} /></td>
                                                    <td className="py-2 text-right text-gray-600">{mp.margin ? `${(mp.margin/1000).toFixed(0)}K` : '—'}</td>
                                                    <td className="py-2 text-xs text-gray-500 max-w-xs">{mp.note || ''}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </SectionCard>
                        </div>
                    )}

                    {/* ── ASSEMBLY tab ─────────────────────────────────────────────── */}
                    {tab === 'assembly' && (
                        <div className="space-y-5">
                            {profile.assembly_summary_2023 && (
                                <div className="flex gap-4">
                                    <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-3 flex gap-4 items-center">
                                        <span className="text-2xl font-bold text-blue-700">{profile.assembly_summary_2023.INC}</span>
                                        <div className="text-xs text-blue-600"><div className="font-semibold">INC Seats</div><div>2023 Assembly</div></div>
                                    </div>
                                    <div className="bg-orange-50 border border-orange-200 rounded-xl px-5 py-3 flex gap-4 items-center">
                                        <span className="text-2xl font-bold text-orange-700">{profile.assembly_summary_2023.BJP}</span>
                                        <div className="text-xs text-orange-600"><div className="font-semibold">BJP Seats</div><div>2023 Assembly</div></div>
                                    </div>
                                    <div className="bg-gray-50 border border-gray-200 rounded-xl px-5 py-3 flex items-center">
                                        <p className="text-xs text-gray-600">{profile.assembly_summary_2023.note}</p>
                                    </div>
                                </div>
                            )}
                            <SectionCard title="Assembly Segments (2023 Results)" icon="🗺️">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    {profile.assembly_segments?.map((seg, i) => (
                                        <div key={i} className="border border-gray-200 rounded-lg p-3 hover:shadow-sm transition-shadow">
                                            <div className="flex items-center justify-between mb-1">
                                                <span className="font-semibold text-sm text-gray-900">{seg.name}</span>
                                                <PartyBadge party={seg.party} />
                                            </div>
                                            <div className="text-sm text-gray-700 mb-1">{seg.mla}</div>
                                            <div className="flex items-center justify-between">
                                                <span className="text-xs text-gray-400">{seg.district}</span>
                                                {seg.winning_margin && (
                                                    <span className="text-xs text-gray-500">Margin: <strong>{(seg.winning_margin/1000).toFixed(1)}K</strong></span>
                                                )}
                                            </div>
                                            {seg.note && <p className="text-xs text-gray-500 mt-1 italic">{seg.note}</p>}
                                        </div>
                                    ))}
                                </div>
                            </SectionCard>
                        </div>
                    )}

                    {/* ── ECONOMY tab ──────────────────────────────────────────────── */}
                    {tab === 'economy' && (
                        <div className="space-y-5">
                            <SectionCard title="Economic Overview" icon="🏭">
                                <p className="text-sm text-gray-700 mb-4">{profile.economy?.overview}</p>
                                <div className="grid grid-cols-3 gap-4 text-center py-3 bg-gray-50 rounded-xl">
                                    <div><div className="text-xl font-bold text-gray-900">{profile.economy?.large_medium_industries}</div><div className="text-xs text-gray-500">Large / Medium Industries</div></div>
                                    <div><div className="text-xl font-bold text-gray-900">{(profile.economy?.ssi_units/1000).toFixed(0)}K+</div><div className="text-xs text-gray-500">Small-Scale Units</div></div>
                                    <div><div className="text-xl font-bold text-gray-900">{profile.economy?.agriculture?.primary_crops?.length}</div><div className="text-xs text-gray-500">Major Crops</div></div>
                                </div>
                            </SectionCard>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                                <SectionCard title="Industries" icon="⚙️">
                                    <div className="space-y-4">
                                        {profile.economy?.industries?.map(ind => (
                                            <div key={ind.sector} className="border-l-2 border-emerald-400 pl-3">
                                                <div className="text-sm font-semibold text-gray-900">{ind.sector}</div>
                                                <div className="text-xs text-gray-600 mt-0.5">{ind.details}</div>
                                            </div>
                                        ))}
                                    </div>
                                </SectionCard>

                                <SectionCard title="Agriculture" icon="🌾">
                                    <div className="mb-3">
                                        <div className="text-xs font-medium text-gray-500 mb-2">Primary Crops</div>
                                        <div className="flex flex-wrap gap-1.5">
                                            {profile.economy?.agriculture?.primary_crops?.map(c => <Tag key={c} color="green">{c}</Tag>)}
                                        </div>
                                    </div>
                                    <div className="mb-3">
                                        <div className="text-xs font-medium text-gray-500 mb-2">Irrigation Sources</div>
                                        <div className="flex flex-wrap gap-1.5">
                                            {profile.economy?.agriculture?.irrigation_sources?.map(s => <Tag key={s} color="blue">{s}</Tag>)}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-xs font-medium text-gray-500 mb-2">Major Employers</div>
                                        <ul className="space-y-1">
                                            {profile.economy?.major_employers?.map((e, i) => (
                                                <li key={i} className="text-xs text-gray-700 flex gap-2">
                                                    <span className="text-emerald-500">›</span>{e}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                </SectionCard>
                            </div>

                            <SectionCard title="Infrastructure" icon="🛣️">
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                                    <div>
                                        <div className="text-xs font-semibold text-gray-500 mb-2 uppercase">National Highways</div>
                                        {profile.infrastructure?.roads?.national_highways?.map(h => (
                                            <div key={h.name} className="mb-2">
                                                <div className="text-xs font-semibold text-gray-800">{h.name}</div>
                                                <div className="text-xs text-gray-500">{h.route}</div>
                                            </div>
                                        ))}
                                    </div>
                                    <div>
                                        <div className="text-xs font-semibold text-gray-500 mb-2 uppercase">Railways</div>
                                        <div className="text-xs text-gray-700">{profile.infrastructure?.railways?.main_station}</div>
                                        <div className="text-xs text-gray-500 mt-1">{profile.infrastructure?.railways?.pending}</div>
                                    </div>
                                    <div>
                                        <div className="text-xs font-semibold text-gray-500 mb-2 uppercase">Airport</div>
                                        {profile.infrastructure?.airports?.map(a => (
                                            <div key={a.name}>
                                                <div className="text-xs font-semibold text-gray-800">{a.name} ({a.iata})</div>
                                                <div className="text-xs text-gray-500">{a.history}</div>
                                                <div className="text-xs text-gray-500">Routes: {a.connectivity}</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </SectionCard>
                        </div>
                    )}

                    {/* ── SOCIAL tab ───────────────────────────────────────────────── */}
                    {tab === 'social' && (
                        <div className="space-y-5">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                                <SectionCard title="Social Indicators" icon="📊">
                                    <div className="space-y-3 text-sm text-gray-700">
                                        <div className="flex justify-between border-b border-gray-100 pb-2">
                                            <span>Literacy vs National Avg</span>
                                            <span className="font-semibold">{profile.social_indicators?.literacy_vs_national}</span>
                                        </div>
                                        <div className="flex justify-between border-b border-gray-100 pb-2">
                                            <span>Gender Literacy Gap</span>
                                            <span className="font-semibold text-red-600">{profile.social_indicators?.female_literacy_gap}</span>
                                        </div>
                                        <div className="flex justify-between border-b border-gray-100 pb-2">
                                            <span>Child Sex Ratio (0–6)</span>
                                            <span className="font-semibold text-amber-600">{profile.social_indicators?.child_sex_ratio}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span>SC + ST Combined</span>
                                            <span className="font-semibold">{profile.social_indicators?.sc_st_combined_percent}%</span>
                                        </div>
                                    </div>
                                </SectionCard>

                                <SectionCard title="Education & Healthcare" icon="🏥">
                                    <div className="grid grid-cols-2 gap-4 mb-4">
                                        <Stat label="Colleges" value={profile.infrastructure?.education?.total_colleges} />
                                        <Stat label="Universities" value={profile.infrastructure?.education?.universities} />
                                        <Stat label="Govt Hospitals" value={profile.infrastructure?.healthcare?.government_hospitals} />
                                        <Stat label="PHCs" value={profile.infrastructure?.healthcare?.primary_health_centres} />
                                    </div>
                                    <div>
                                        <div className="text-xs font-medium text-gray-500 mb-1.5">Key Institutions</div>
                                        {profile.infrastructure?.education?.key_institutions?.slice(0, 4).map((inst, i) => (
                                            <div key={i} className="text-xs text-gray-600 flex gap-2 mb-1">
                                                <span className="text-emerald-500">›</span>{inst}
                                            </div>
                                        ))}
                                    </div>
                                </SectionCard>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                                <SectionCard title="Central Schemes Active" icon="🇮🇳">
                                    <ul className="space-y-1.5">
                                        {profile.social_indicators?.key_central_schemes?.map((s, i) => (
                                            <li key={i} className="text-sm text-gray-700 flex gap-2">
                                                <span className="text-blue-500 shrink-0">●</span>{s}
                                            </li>
                                        ))}
                                    </ul>
                                </SectionCard>
                                <SectionCard title="State Schemes Active" icon="🏛️">
                                    <ul className="space-y-1.5">
                                        {profile.social_indicators?.key_state_schemes?.map((s, i) => (
                                            <li key={i} className="text-sm text-gray-700 flex gap-2">
                                                <span className="text-emerald-500 shrink-0">●</span>{s}
                                            </li>
                                        ))}
                                    </ul>
                                </SectionCard>
                            </div>

                            <SectionCard title="Dominant Communities" icon="🫂">
                                <div className="flex flex-wrap gap-2">
                                    {profile.demographics?.castes?.dominant_communities?.map((c, i) => (
                                        <Tag key={i} color="purple">{c}</Tag>
                                    ))}
                                </div>
                                {profile.demographics?.castes?.note && (
                                    <p className="text-xs text-gray-500 mt-3 italic">{profile.demographics.castes.note}</p>
                                )}
                            </SectionCard>
                        </div>
                    )}

                    {/* ── CULTURE tab ──────────────────────────────────────────────── */}
                    {tab === 'culture' && (
                        <div className="space-y-5">
                            <SectionCard title="Heritage Sites" icon="🏰">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {profile.cultural_profile?.heritage_sites?.map((site, i) => (
                                        <div key={i} className="border border-gray-200 rounded-lg p-3">
                                            <div className="font-semibold text-sm text-gray-900 mb-1">{site.name}</div>
                                            {site.built && <div className="text-xs text-gray-500 mb-1">Built: {site.built}</div>}
                                            <p className="text-xs text-gray-700">{site.significance}</p>
                                            {site.museum && <p className="text-xs text-emerald-700 mt-1 font-medium">{site.museum}</p>}
                                        </div>
                                    ))}
                                </div>
                            </SectionCard>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                                <SectionCard title="Festivals" icon="🎊">
                                    {profile.cultural_profile?.festivals?.map((f, i) => (
                                        <div key={i} className="mb-3 pb-3 border-b border-gray-100 last:border-0 last:mb-0">
                                            <div className="font-semibold text-sm text-gray-900">{f.name}</div>
                                            {f.date && <div className="text-xs text-gray-500">{f.date}</div>}
                                            <div className="text-xs text-gray-600 mt-0.5">{f.significance || f.note}</div>
                                        </div>
                                    ))}
                                </SectionCard>

                                <SectionCard title="Arts, Crafts & Cuisine" icon="🎨">
                                    <div className="space-y-3">
                                        <div>
                                            <div className="text-xs font-medium text-gray-500 mb-1.5">Folk Arts</div>
                                            <div className="flex flex-wrap gap-1.5">
                                                {profile.cultural_profile?.arts_and_crafts?.folk_arts?.map(a => <Tag key={a} color="purple">{a}</Tag>)}
                                            </div>
                                        </div>
                                        <div>
                                            <div className="text-xs font-medium text-gray-500 mb-1">{profile.cultural_profile?.arts_and_crafts?.textiles}</div>
                                        </div>
                                        <div>
                                            <div className="text-xs font-medium text-gray-500 mb-1">Cuisine</div>
                                            <p className="text-xs text-gray-700">{profile.cultural_profile?.arts_and_crafts?.cuisine}</p>
                                        </div>
                                    </div>
                                </SectionCard>
                            </div>

                            <SectionCard title="Famous Personalities" icon="⭐">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    {profile.cultural_profile?.famous_personalities?.map((p, i) => (
                                        <div key={i} className="flex gap-3">
                                            <div className="h-9 w-9 rounded-full bg-gray-100 text-gray-600 flex items-center justify-center text-sm font-bold shrink-0">
                                                {p.name?.charAt(0)}
                                            </div>
                                            <div>
                                                <div className="text-sm font-semibold text-gray-900">{p.name}</div>
                                                <Tag color="blue">{p.field}</Tag>
                                                <p className="text-xs text-gray-500 mt-0.5">{p.note}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </SectionCard>

                            <SectionCard title="Tourist Attractions" icon="📸">
                                <div className="flex flex-wrap gap-2">
                                    {profile.cultural_profile?.tourist_attractions?.map((t, i) => (
                                        <Tag key={i} color="green">{t}</Tag>
                                    ))}
                                </div>
                            </SectionCard>
                        </div>
                    )}

                    {/* ── CHALLENGES tab ───────────────────────────────────────────── */}
                    {tab === 'challenges' && (
                        <div className="space-y-4">
                            {profile.key_challenges?.map((c, i) => (
                                <div key={i} className="bg-white border border-gray-200 rounded-xl p-5">
                                    <div className="flex items-start gap-3">
                                        <span className="h-7 w-7 rounded-full bg-red-100 text-red-700 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">{i + 1}</span>
                                        <div>
                                            <h4 className="text-sm font-bold text-gray-900 mb-1">{c.title}</h4>
                                            <p className="text-sm text-gray-700 leading-relaxed">{c.detail}</p>
                                        </div>
                                    </div>
                                </div>
                            ))}

                            <SectionCard title="Development Priorities" icon="🎯">
                                <ol className="space-y-2">
                                    {profile.development_priorities?.map((p, i) => (
                                        <li key={i} className="flex gap-3 text-sm text-gray-700">
                                            <span className="text-emerald-600 font-bold shrink-0">{i + 1}.</span>{p}
                                        </li>
                                    ))}
                                </ol>
                            </SectionCard>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
