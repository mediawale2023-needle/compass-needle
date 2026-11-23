'use client';

import { useEffect, useState } from 'react';
import { partnerClientReport } from '@/lib/partnerApi';
import { BrandMark } from './PartnerShell';
import { Icon, SectionHead } from './ui';

/** Branded client report: generate, preview in a fully sandboxed frame, print to PDF or download. */
export default function ReportPanel({ seatId, days, clientLabel, partner }) {
    const [html, setHtml] = useState(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    // A report for another period or client is stale; drop it rather than show mismatched numbers.
    useEffect(() => { setHtml(null); setError(''); }, [seatId, days]);

    async function generate() {
        setBusy(true);
        setError('');
        try {
            setHtml(await partnerClientReport(seatId, days));
        } catch (err) {
            setError(err.message || 'The report could not be generated.');
        } finally {
            setBusy(false);
        }
    }

    const blobUrl = () => URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }));
    function openForPrint() {
        const url = blobUrl();
        window.open(url, '_blank', 'noopener');
        setTimeout(() => URL.revokeObjectURL(url), 60000);
    }
    function download() {
        const url = blobUrl();
        const a = document.createElement('a');
        a.href = url;
        a.download = `${String(clientLabel).replace(/[^a-z0-9]+/gi, '-').toLowerCase() || 'client'}-report-${days}d.html`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    return (
        <section className="pd-panel pd-pad" aria-labelledby="pd-rep-h">
            <SectionHead id="pd-rep-h" title="Client report"
                sub={`Branded as ${partner?.brand_name || 'your organisation'} · last ${days} days · aggregate figures only, no citizen details`} />
            <div className="pd-rep">
                <div className="pd-sheet" aria-hidden="true">
                    <div className="band" />
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><BrandMark partner={partner} size={18} /></div>
                    <div style={{ fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 600, lineHeight: 1.1 }}>{clientLabel}</div>
                    <div className="blk"><i /><i /><i /></div>
                    <div className="bars">{[5, 7, 6, 8, 7, 9, 8, 10].map((v, i) => <i key={i} style={{ height: `${v * 10}%` }} />)}</div>
                    <div className="l" style={{ width: '90%' }} /><div className="l" style={{ width: '70%' }} /><div className="l" style={{ width: '80%' }} />
                </div>
                <div>
                    <p style={{ margin: '0 0 6px', fontWeight: 600 }}>What the report contains</p>
                    <ul className="muted" style={{ margin: 0, paddingLeft: 18, fontSize: 13, lineHeight: 1.8 }}>
                        <li>Headline figures: received, resolved, still open, critical, time to resolve</li>
                        <li>Weekly volume for the last 8 weeks</li>
                        <li>Top issue categories and where complaints come from</li>
                    </ul>
                    <div style={{ display: 'flex', gap: 8, marginTop: 18, flexWrap: 'wrap' }}>
                        {!html ? (
                            <button type="button" className="pd-btn primary" onClick={generate} disabled={busy}>
                                <Icon name="report" size={16} /> {busy ? 'Generating…' : 'Generate report'}
                            </button>
                        ) : (
                            <>
                                <button type="button" className="pd-btn primary" onClick={openForPrint}><Icon name="external" size={16} /> Open to print or save PDF</button>
                                <button type="button" className="pd-btn" onClick={download}><Icon name="download" size={16} /> Download HTML</button>
                            </>
                        )}
                    </div>
                    {error ? <div role="alert" className="pd-alert" style={{ marginTop: 14 }}>{error}</div> : null}
                </div>
            </div>
            {html ? (
                // Fully sandboxed: no scripts, no same-origin access, even if report markup were ever wrong.
                <iframe title={`${clientLabel} report preview`} sandbox="" srcDoc={html} className="pd-frame" />
            ) : null}
        </section>
    );
}
