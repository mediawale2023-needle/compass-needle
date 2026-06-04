import { redirect } from 'next/navigation';

export default async function SharedGeographyRulesRedirect({ searchParams }) {
    const resolvedSearchParams = await searchParams;
    const tenantId = resolvedSearchParams?.tenant_id;
    const query = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : '';
    redirect(`/dashboard/shared-geography/workspace${query}`);
}
