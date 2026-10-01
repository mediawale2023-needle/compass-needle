'use client';

import { useEffect, useState } from 'react';
import { apiGet } from '@/lib/api';
import { AdminDataState, AdminMetricStrip, AdminPageHeader, AdminPanel, AdminTableWrap } from '@/components/admin-ui/AdminPrimitives';

const STATUS_STYLES = {
    active: { badgeClass: 'badge badge-green badge-dot', label: 'Active' },
    stale: { badgeClass: 'badge badge-amber badge-dot', label: 'Stale' },
    inactive: { badgeClass: 'badge badge-red badge-dot', label: 'Inactive' },
    no_data: { badgeClass: 'badge badge-slate badge-dot', label: 'No data' },
};

function formatDate(value) {
    return value ? new Date(value).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—';
}

export default function TenantHealthPage() {
    const [tenants, setTenants] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const load = async () => {
        setLoading(true);
        setError('');
        try {
            const data = await apiGet('/api/admin/tenant-health');
            setTenants(data.tenants || []);
        } catch (err) {
            setError(err.message || 'Tenant health could not be loaded.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, []);
    const normalizedTenants = tenants.map((tenant) => ({
        tenant_id: tenant.tenant_id ?? tenant.id,
        mp_name: tenant.mp_name ?? tenant.name,
        constituency: tenant.constituency,
        status: tenant.status ?? tenant.health ?? 'no_data',
        last_case_at: tenant.last_case_at ?? tenant.last_case,
        last_login_at: tenant.last_login_at ?? tenant.last_login,
        cases_last_30d: tenant.cases_last_30d ?? tenant.total_cases,
        total_cases: tenant.total_cases,
        open_cases: tenant.open_cases,
    }));
    const counts = { active: 0, stale: 0, inactive: 0, no_data: 0 };
    normalizedTenants.forEach((tenant) => { if (counts[tenant.status] !== undefined) counts[tenant.status] += 1; });

    return <div className="space-y-6">
        <AdminPageHeader context="Platform Operations / Health" title="Account health" description="Review account activity and identify stale or inactive customer environments before operational issues compound." actions={<button type="button" className="btn-secondary" onClick={load} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button>} />
        <AdminMetricStrip unavailable={Boolean(error)} items={[
            { label: 'Active', value: counts.active, tone: 'success' }, { label: 'Stale', value: counts.stale, tone: 'warning' },
            { label: 'Inactive', value: counts.inactive, tone: 'danger' }, { label: 'No data', value: counts.no_data },
        ]} />
        <AdminPanel title="Tenant activity registry" description="Health is derived from existing case and login activity; it is not a synthetic uptime score.">
            <AdminDataState loading={loading} error={error} empty={!loading && !error && normalizedTenants.length === 0} emptyTitle="No tenant health data" emptyDescription="Health records appear after customer accounts begin activity." onRetry={load}>
                <AdminTableWrap label="Tenant health"><table className="data-table">
                    <thead><tr><th>MP / tenant</th><th>Constituency</th><th>Status</th><th>Last case</th><th>Last login</th><th>Cases (30d)</th></tr></thead>
                    <tbody>{normalizedTenants.map((tenant) => { const style = STATUS_STYLES[tenant.status] || STATUS_STYLES.no_data; return <tr key={tenant.tenant_id}>
                        <td><strong>{tenant.mp_name || `Tenant #${tenant.tenant_id}`}</strong><small>Tenant #{tenant.tenant_id}</small></td><td>{tenant.constituency || '—'}</td>
                        <td><span className={style.badgeClass}>{style.label}</span></td><td>{formatDate(tenant.last_case_at)}</td><td>{formatDate(tenant.last_login_at)}</td>
                        <td><strong>{tenant.cases_last_30d ?? '—'}</strong><small>{tenant.open_cases ?? 0} open / {tenant.total_cases ?? 0} total</small></td>
                    </tr>; })}</tbody>
                </table></AdminTableWrap>
            </AdminDataState>
        </AdminPanel>
    </div>;
}
