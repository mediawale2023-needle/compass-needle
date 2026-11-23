'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { usePartnerSession } from '@/lib/partnerSession';
import { buildPartnerTheme } from '@/lib/partnerTheme';
import { BrandMark } from '@/components/partner/PartnerShell';
import { Badge, SectionHead, useCrumbs } from '@/components/partner/ui';

function Ratio({ label, value }) {
    const ok = value >= 4.5;
    return (
        <>
            <div>{label}</div>
            <div className="v num">{value.toFixed(2)} : 1</div>
            <div style={{ textAlign: 'right', fontWeight: 600, color: ok ? 'var(--go)' : 'var(--crit)' }}>{ok ? 'Passes AA' : 'Fails AA'}</div>
        </>
    );
}

/** Read-only view of the organisation's branding. Needle manages changes until partner self-service ships. */
export default function PartnerSettingsPage() {
    const router = useRouter();
    const { ready, token, partner, me, mustChangePassword } = usePartnerSession();
    useCrumbs([{ label: 'Settings' }]);
    useEffect(() => {
        if (ready && (!token || mustChangePassword)) router.replace('/partner');
    }, [ready, token, mustChangePassword, router]);
    if (!ready || !token || !partner) return null;

    const { report } = buildPartnerTheme(partner.brand_color);
    return (
        <div>
            <div className="pd-pagehead">
                <div>
                    <div className="pd-eyebrow">Organisation</div>
                    <h1 className="pd-title">Settings</h1>
                    <p className="pd-lede">How {partner.brand_name} appears to your team and in client reports. To change any of this, contact your Needle account manager.</p>
                </div>
            </div>
            <div className="pd-grid pd-g11">
                <section className="pd-panel pd-pad" aria-labelledby="pd-id-h">
                    <SectionHead id="pd-id-h" title="Identity" sub="Name, logo and colour" />
                    <div style={{ display: 'flex', gap: 16, alignItems: 'center', padding: 16, border: '1px dashed var(--line-strong)', borderRadius: 8 }}>
                        <BrandMark partner={partner} size={48} />
                        <div><div style={{ fontWeight: 600 }}>{partner.brand_name}</div><div className="pd-csub">{partner.brand_logo_url ? 'Logo from your organisation' : 'No logo yet — initials are shown instead'}</div></div>
                    </div>
                    <div className="pd-kv" style={{ marginTop: 16 }}>
                        <div>Brand colour</div><div className="v" style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'flex-end' }}><span style={{ width: 16, height: 16, borderRadius: 3, background: report.brand, display: 'inline-block' }} /><span className="num">{report.brand}</span></div>
                        <div>“Powered by Needle” line</div><div className="v">{partner.show_powered_by ? <Badge tone="info">Shown</Badge> : <Badge tone="neutral">Hidden</Badge>}</div>
                        <div>Signed in as</div><div className="v" style={{ fontWeight: 500 }}>{me?.email || '—'}</div>
                    </div>
                </section>
                <section className="pd-panel pd-pad" aria-labelledby="pd-ct-h2">
                    <SectionHead id="pd-ct-h2" title="Contrast check" sub="The workspace adjusts the brand colour so text stays readable" />
                    <div className="pd-kv c3">
                        <Ratio label="Text on brand buttons" value={report.fgOnBrand} />
                        <Ratio label="Brand colour as text" value={report.brandOnWhite} />
                        <Ratio label="Adjusted link colour" value={report.brandInkOnWhite} />
                    </div>
                    <p className="pd-note">
                        {report.brandOnWhite < 4.5
                            ? `${report.brand} is too light for text, so links use ${report.brandInk} and buttons use dark text.`
                            : `${report.brand} is dark enough for text and white button labels.`}{' '}
                        Status and chart colours never change with the brand.
                    </p>
                    <div style={{ display: 'flex', gap: 10, marginTop: 14, flexWrap: 'wrap', alignItems: 'center' }}>
                        <span className="pd-btn primary" aria-hidden="true">Primary action</span>
                        <span className="pd-btn" aria-hidden="true">Secondary</span>
                        <span className="pd-link" aria-hidden="true">Text link</span>
                    </div>
                </section>
            </div>
        </div>
    );
}
