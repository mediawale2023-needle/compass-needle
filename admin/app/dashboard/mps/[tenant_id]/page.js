'use client';
import { useParams } from 'next/navigation';
import Account360Page from '@/components/admin-domains/accounts/account360/Account360Page';

export default function MpDetailPage() {
    const params = useParams();
    return <Account360Page tenantId={params.tenant_id} />;
}
